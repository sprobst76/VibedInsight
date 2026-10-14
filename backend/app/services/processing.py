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
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
from app.services.fetcher import FetchError, PrivateAddressError
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


# Retry policy: backoff = RETRY_BASE * 2^attempts (attempts before this failure), capped.
RETRY_BASE = timedelta(minutes=5)
RETRY_MAX_BACKOFF = timedelta(hours=12)
MAX_ERROR_LEN = 300


def retry_backoff(attempts: int) -> timedelta:
    """Delay before the next automatic retry, given the attempts made so far."""
    return min(RETRY_BASE * (2 ** max(attempts, 0)), RETRY_MAX_BACKOFF)


def safe_error_message(exc: BaseException) -> str:
    """Short, user-presentable error text without internals (no tracebacks/paths)."""
    if isinstance(exc, FetchError):
        text = str(exc)  # fetcher messages are written for users
    else:
        text = f"Processing failed ({type(exc).__name__})"
    return text[:MAX_ERROR_LEN]


async def _record_failure(
    db: AsyncSession, item_id: uuid.UUID, error: str, *, retryable: bool = True
) -> None:
    """Mark an item FAILED: attempts+1, last_error, and when to retry next."""
    result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        return
    item.status = ProcessingStatus.FAILED
    item.last_error = error[:MAX_ERROR_LEN]
    item.next_retry_at = (
        datetime.now(UTC) + retry_backoff(item.attempts or 0) if retryable else None
    )
    item.attempts = (item.attempts or 0) + 1
    await db.commit()


async def _ensure_raw_text(item_id: uuid.UUID) -> bool:
    """
    Make sure the item has text to process; fetches the URL if it has none yet
    (asynchronous URL ingest creates items without text). Failures are recorded
    on the item (FAILED + last_error + attempts) and return False.
    """
    async with async_session_maker() as db:
        result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
        item = result.scalar_one_or_none()
        if item is None:
            logger.warning(f"Item {item_id} not found")
            return False
        if item.raw_text:
            return True
        if not item.url:
            await _record_failure(db, item_id, "No text to process", retryable=False)
            return False

        try:
            extracted = await extract_from_url(item.url)
        except Exception as e:
            logger.warning(f"Item {item_id}: fetch/extract failed: {e}")
            await db.rollback()
            retryable = not isinstance(e, PrivateAddressError)
            await _record_failure(db, item_id, safe_error_message(e), retryable=retryable)
            return False

        if not extracted["text"]:
            await _record_failure(db, item_id, "Could not extract text from URL")
            return False

        item.raw_text = extracted["text"]
        # Replace the provisional title (the URL) but never a user-edited one
        if extracted["title"] and (not item.title or item.title == item.url):
            item.title = extracted["title"][:500]
        if extracted["source"]:
            item.source = extracted["source"][:255]
        await db.commit()
        return True


async def process_item(item_id: uuid.UUID) -> None:
    """Process one item: (fetch if needed), summary, topics, embedding, relations."""
    # Fetching does not need an Ollama slot, so it happens before the semaphore
    if not await _ensure_raw_text(item_id):
        return

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

                item.summary = await generate_summary(item.raw_text, context=f"item {item_id}")

                topic_names = await extract_topics(item.raw_text, context=f"item {item_id}")
                logger.info(f"Item {item_id}: extracted topics: {topic_names}")
                await _attach_topics(item, topic_names, db)

                item.status = ProcessingStatus.COMPLETED
                item.processed_at = utcnow()
                item.last_error = None
                item.next_retry_at = None
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
                    await _record_failure(db, item_id, safe_error_message(e))
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

    process_item fetches the URL itself when raw_text is missing, so URL items
    created by the asynchronous ingest are picked up here as well.
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(ContentItem).where(
                ContentItem.status.in_([ProcessingStatus.PENDING, ProcessingStatus.PROCESSING])
            )
        )
        stuck = result.scalars().all()

        to_schedule: list[uuid.UUID] = []
        for item in stuck:
            if item.raw_text or item.url:
                item.status = ProcessingStatus.PENDING
                to_schedule.append(item.id)
            else:
                item.status = ProcessingStatus.FAILED
                item.last_error = "No text to process"
        await db.commit()

    for item_id in to_schedule:
        schedule_processing(item_id)

    if stuck:
        logger.info(f"Startup requeue: rescheduled {len(to_schedule)} of {len(stuck)} stuck items")


async def _get_or_create_topic(name: str, db: AsyncSession) -> Topic:
    """Race-safe get-or-create: INSERT .. ON CONFLICT DO NOTHING, then SELECT.

    Two items processed in parallel may produce the same new topic; a plain
    SELECT-then-INSERT would hit the unique index and fail one of them.
    """
    await db.execute(
        pg_insert(Topic)
        .values(name=name, created_at=utcnow())
        .on_conflict_do_nothing(index_elements=["name"])
    )
    result = await db.execute(select(Topic).where(Topic.name == name))
    return result.scalar_one()


async def _attach_topics(item: ContentItem, topic_names: list[str], db: AsyncSession) -> None:
    """Get-or-create topics by name and set them on the item.

    Replaces any existing topics — on reprocessing the old topics must be
    dropped, not accumulated (a fresh run may produce different/other-language
    topics).
    """
    item.topics.clear()
    # Create in sorted order so two transactions never take the row locks of
    # the same topics in opposite order (deadlock); attach in original order.
    by_name: dict[str, Topic] = {}
    for name in sorted(set(topic_names)):
        by_name[name] = await _get_or_create_topic(name, db)

    attached_ids: set[int] = set()
    for name in topic_names:
        topic = by_name[name]
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

    try:
        from app.services.triage import update_triage_for_content

        await update_triage_for_content(db, item.id)
    except Exception as e:
        logger.warning(f"Item {item.id}: triage scoring failed (non-fatal): {e}")
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
