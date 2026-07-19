"""
Content processing pipeline.

Single place for the ingest → summary → topics → embedding → relations flow,
used by the ingest router, the admin batch endpoints, and the startup requeue.

Tasks run on the app's shared engine (no per-task engines) and are serialized
through a semaphore so parallel ingests don't overload Ollama.
"""

import asyncio
import logging
import traceback
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_maker
from app.models.content import (
    ContentEmbedding,
    ContentItem,
    ItemRelation,
    ProcessingStatus,
    RelationType,
    Topic,
    content_topics,
)
from app.services.embeddings import generate_embedding_for_content
from app.services.extractor import extract_from_url
from app.services.summarizer import extract_topics, generate_summary
from app.timeutils import utcnow

logger = logging.getLogger(__name__)

# At most N items talk to Ollama at the same time
_ollama_semaphore = asyncio.Semaphore(2)

# Keep references to background tasks so they aren't garbage-collected
_background_tasks: set[asyncio.Task] = set()


def schedule_processing(item_id: uuid.UUID) -> None:
    """Schedule background processing for a content item."""
    task = asyncio.create_task(process_item(item_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    logger.info(f"Scheduled background processing for item {item_id}")


async def process_item(item_id: uuid.UUID) -> None:
    """Process one item: summary, topics, embedding, relations."""
    async with _ollama_semaphore:
        async with async_session_maker() as db:
            query = (
                select(ContentItem)
                .options(selectinload(ContentItem.topics))
                .where(ContentItem.id == item_id)
            )
            result = await db.execute(query)
            item = result.scalar_one_or_none()

            if not item or not item.raw_text:
                logger.warning(f"Item {item_id} not found or has no text")
                return

            try:
                item.status = ProcessingStatus.PROCESSING
                await db.commit()

                item.summary = await generate_summary(item.raw_text)

                topic_names = await extract_topics(item.raw_text)
                logger.info(f"Item {item_id}: extracted topics: {topic_names}")
                await _attach_topics(item, topic_names, db)

                item.status = ProcessingStatus.COMPLETED
                item.processed_at = utcnow()
                # raw_text is kept on purpose: reprocessing and future
                # semantic features (RAG) need the original text.
                await db.commit()

                # Best-effort steps — failures must not mark the item FAILED
                await _embed_and_relate(item, db)

                logger.info(f"Item {item_id}: processing COMPLETED")

            except Exception as e:
                logger.error(f"Error processing item {item_id}: {e}")
                logger.error(traceback.format_exc())
                try:
                    await db.rollback()
                    result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
                    failed_item = result.scalar_one_or_none()
                    if failed_item:
                        failed_item.status = ProcessingStatus.FAILED
                        await db.commit()
                except Exception as inner_e:
                    logger.error(f"Failed to mark item {item_id} as FAILED: {inner_e}")


async def reprocess_item(item_id: uuid.UUID, db: AsyncSession) -> bool:
    """
    Prepare an item for reprocessing and schedule it.

    Items with a URL are re-fetched if raw_text is missing (older items
    deleted it after processing). Returns False if there is nothing to
    reprocess from (note without raw_text).
    """
    result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        return False

    if not item.raw_text:
        if not item.url:
            return False
        extracted = await extract_from_url(item.url)
        if not extracted["text"]:
            return False
        item.raw_text = extracted["text"]
        if extracted["title"] and not item.title:
            item.title = extracted["title"]

    item.status = ProcessingStatus.PENDING
    await db.commit()
    schedule_processing(item.id)
    return True


async def requeue_stuck_items() -> None:
    """
    Startup recovery: reschedule items that were PENDING/PROCESSING when the
    server stopped (background tasks don't survive restarts/deploys).
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(ContentItem).where(
                ContentItem.status.in_([ProcessingStatus.PENDING, ProcessingStatus.PROCESSING])
            )
        )
        stuck = result.scalars().all()

        requeued = 0
        for item in stuck:
            if item.raw_text:
                item.status = ProcessingStatus.PENDING
                requeued += 1
            elif item.url:
                # raw_text lost (e.g. crash after cleanup) — needs re-fetch
                item.status = ProcessingStatus.PENDING
                requeued += 1
            else:
                item.status = ProcessingStatus.FAILED
        await db.commit()

        for item in stuck:
            if item.status == ProcessingStatus.PENDING:
                if item.raw_text:
                    schedule_processing(item.id)
                else:
                    task = asyncio.create_task(_refetch_and_process(item.id))
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)

        if stuck:
            logger.info(f"Startup requeue: rescheduled {requeued} of {len(stuck)} stuck items")


async def _refetch_and_process(item_id: uuid.UUID) -> None:
    """Re-fetch a URL item that lost its raw_text, then process it."""
    try:
        async with async_session_maker() as db:
            ok = await reprocess_item(item_id, db)
            if not ok:
                logger.warning(f"Startup requeue: could not re-fetch item {item_id}")
    except Exception as e:
        logger.error(f"Startup requeue failed for item {item_id}: {e}")


async def _attach_topics(item: ContentItem, topic_names: list[str], db: AsyncSession) -> None:
    """Get-or-create topics by name and set them on the item.

    Replaces any existing topics — on reprocessing the old topics must be
    dropped, not accumulated (a fresh run may produce different/other-language
    topics).
    """
    item.topics.clear()
    attached_ids: set[int] = set()
    for topic_name in topic_names:
        topic_result = await db.execute(select(Topic).where(Topic.name == topic_name))
        topic = topic_result.scalar_one_or_none()

        if not topic:
            topic = Topic(name=topic_name)
            db.add(topic)
            await db.flush()

        if topic.id not in attached_ids:
            item.topics.append(topic)
            attached_ids.add(topic.id)


async def _embed_and_relate(item: ContentItem, db: AsyncSession) -> None:
    """Generate the embedding and rebuild relations for one item (best effort)."""
    try:
        await update_embedding(item, db)
        await db.commit()
    except Exception as e:
        logger.warning(f"Item {item.id}: embedding failed (non-fatal): {e}")
        await db.rollback()

    try:
        created = await rebuild_relations_for_item(item.id, db)
        await db.commit()
        logger.info(f"Item {item.id}: created {created} relations")
    except Exception as e:
        logger.warning(f"Item {item.id}: relation calculation failed (non-fatal): {e}")
        await db.rollback()


async def update_embedding(item: ContentItem, db: AsyncSession) -> bool:
    """Generate and store/update the embedding for an item."""
    if not item.title and not item.summary:
        return False

    embedding = await generate_embedding_for_content(item.title, item.summary)
    if not embedding:
        return False

    result = await db.execute(
        select(ContentEmbedding).where(ContentEmbedding.content_id == item.id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.embedding = embedding
        existing.model = settings.ollama_embedding_model
        existing.updated_at = utcnow()
    else:
        db.add(
            ContentEmbedding(
                content_id=item.id,
                embedding=embedding,
                model=settings.ollama_embedding_model,
            )
        )
    return True


async def rebuild_relations_for_item(item_id: uuid.UUID, db: AsyncSession) -> int:
    """
    Recompute relations for one item and replace its existing ones.

    Two sources, embedding similarity preferred:
    - SIMILAR: pgvector cosine similarity >= settings.similarity_threshold
    - RELATED: at least 2 shared topics (fallback signal)
    """
    await db.execute(
        delete(ItemRelation).where(
            (ItemRelation.source_id == item_id) | (ItemRelation.target_id == item_id)
        )
    )

    created = 0
    related_ids: set[uuid.UUID] = set()

    # Embedding similarity via pgvector (cosine_distance = 1 - similarity)
    emb_result = await db.execute(
        select(ContentEmbedding).where(ContentEmbedding.content_id == item_id)
    )
    item_embedding = emb_result.scalar_one_or_none()

    if item_embedding is not None:
        max_distance = 1.0 - settings.similarity_threshold
        distance = ContentEmbedding.embedding.cosine_distance(item_embedding.embedding)
        similar_result = await db.execute(
            select(ContentEmbedding.content_id, distance.label("distance"))
            .where(
                ContentEmbedding.content_id != item_id,
                ContentEmbedding.model == item_embedding.model,
                distance <= max_distance,
            )
            .order_by(distance)
            .limit(10)
        )
        for other_id, dist in similar_result.all():
            db.add(
                ItemRelation(
                    source_id=item_id,
                    target_id=other_id,
                    relation_type=RelationType.SIMILAR,
                    confidence=round(1.0 - dist, 4),
                )
            )
            related_ids.add(other_id)
            created += 1

    # Shared-topics fallback
    item_result = await db.execute(
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.id == item_id)
    )
    item = item_result.scalar_one_or_none()
    if item is None or not item.topics:
        return created

    from sqlalchemy import and_, func

    item_topic_ids = {t.id for t in item.topics}
    shared_result = await db.execute(
        select(
            content_topics.c.content_id,
            func.count(content_topics.c.topic_id).label("shared_count"),
        )
        .where(
            and_(
                content_topics.c.topic_id.in_(item_topic_ids),
                content_topics.c.content_id != item_id,
            )
        )
        .group_by(content_topics.c.content_id)
        .having(func.count(content_topics.c.topic_id) >= 2)
    )

    for other_id, shared_count in shared_result.all():
        if other_id in related_ids:
            continue
        db.add(
            ItemRelation(
                source_id=item_id,
                target_id=other_id,
                relation_type=RelationType.RELATED,
                confidence=min(shared_count / len(item_topic_ids), 1.0),
            )
        )
        created += 1

    return created
