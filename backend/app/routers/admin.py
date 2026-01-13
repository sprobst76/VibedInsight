"""
Admin Router - Batch operations and maintenance tasks.

These endpoints are for administrative tasks like reprocessing content,
cleaning up data, etc.
"""

import asyncio
import logging
import sys
import traceback
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_dev_or_current_user
from app.models.content import (
    ContentEmbedding,
    ContentItem,
    ItemRelation,
    ProcessingStatus,
    RelationType,
    Topic,
    content_topics,
)
from app.models.user import User
from app.services.embeddings import (
    check_embedding_model_available,
    cosine_similarity,
    generate_embedding_for_content,
)
from app.services.extractor import extract_from_url
from app.services.summarizer import extract_topics, generate_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

router = APIRouter()


class BatchReprocessResponse(BaseModel):
    """Response for batch reprocess operation."""

    message: str
    total_items: int
    queued_items: int


class ReprocessStatus(BaseModel):
    """Status of a reprocess operation."""

    item_id: str
    status: str
    title: str | None
    error: str | None = None


# Track batch processing status
_batch_status: dict[str, list[ReprocessStatus]] = {}


async def _calculate_relations_for_item(item: ContentItem, db: AsyncSession):
    """Calculate relations to other items based on shared topics."""
    if not item.topics:
        return 0

    item_topic_ids = {t.id for t in item.topics}
    if not item_topic_ids:
        return 0

    from sqlalchemy import and_

    # Query for items sharing topics (excluding self)
    shared_items_query = (
        select(
            content_topics.c.content_id, func.count(content_topics.c.topic_id).label("shared_count")
        )
        .where(
            and_(
                content_topics.c.topic_id.in_(item_topic_ids),
                content_topics.c.content_id != item.id,
            )
        )
        .group_by(content_topics.c.content_id)
        .having(func.count(content_topics.c.topic_id) >= 2)
    )

    result = await db.execute(shared_items_query)
    shared_items = result.all()

    relations_created = 0
    for related_id, shared_count in shared_items:
        # Check if relation already exists
        existing = await db.execute(
            select(ItemRelation).where(
                ((ItemRelation.source_id == item.id) & (ItemRelation.target_id == related_id))
                | ((ItemRelation.source_id == related_id) & (ItemRelation.target_id == item.id))
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Calculate confidence based on topic overlap
        confidence = min(shared_count / len(item_topic_ids), 1.0)

        relation = ItemRelation(
            source_id=item.id,
            target_id=related_id,
            relation_type=RelationType.RELATED,
            confidence=confidence,
        )
        db.add(relation)
        relations_created += 1

    return relations_created


async def _reprocess_single_item(item_id: uuid.UUID, db_url: str, batch_id: str):
    """Reprocess a single content item: re-fetch URL, regenerate topics."""
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    status = ReprocessStatus(
        item_id=str(item_id),
        status="processing",
        title=None,
    )

    try:
        async with async_session() as db:
            # Get item
            query = (
                select(ContentItem)
                .options(selectinload(ContentItem.topics))
                .where(ContentItem.id == item_id)
            )
            result = await db.execute(query)
            item = result.scalar_one_or_none()

            if not item:
                status.status = "failed"
                status.error = "Item not found"
                _batch_status[batch_id].append(status)
                return

            status.title = item.title

            # Only process items with URLs
            if not item.url:
                status.status = "skipped"
                status.error = "No URL"
                _batch_status[batch_id].append(status)
                return

            try:
                # Re-fetch content from URL
                logger.info(f"Reprocessing item {item_id}: fetching {item.url}")
                extracted = await extract_from_url(item.url)

                if not extracted["text"]:
                    status.status = "failed"
                    status.error = "Could not extract text"
                    _batch_status[batch_id].append(status)
                    return

                # Update title if we got a better one
                if extracted["title"] and not item.title:
                    item.title = extracted["title"]

                # Clear existing topics
                item.topics.clear()
                await db.flush()

                # Generate new summary
                logger.info(f"Item {item_id}: generating summary...")
                summary = await generate_summary(extracted["text"])
                item.summary = summary

                # Extract new topics
                logger.info(f"Item {item_id}: extracting topics...")
                existing_query = select(Topic.name)
                existing_result = await db.execute(existing_query)
                existing_topics = [t[0] for t in existing_result.all()]

                topic_names = await extract_topics(extracted["text"], existing_topics)
                logger.info(f"Item {item_id}: extracted topics: {topic_names}")

                # Add topics
                for topic_name in topic_names:
                    topic_query = select(Topic).where(Topic.name == topic_name)
                    topic_result = await db.execute(topic_query)
                    topic = topic_result.scalar_one_or_none()

                    if not topic:
                        topic = Topic(name=topic_name)
                        db.add(topic)
                        await db.flush()

                    if topic not in item.topics:
                        item.topics.append(topic)

                item.status = ProcessingStatus.COMPLETED
                item.processed_at = datetime.utcnow()

                await db.commit()

                # Calculate relations
                async with async_session() as db2:
                    query2 = (
                        select(ContentItem)
                        .options(selectinload(ContentItem.topics))
                        .where(ContentItem.id == item_id)
                    )
                    result2 = await db2.execute(query2)
                    item2 = result2.scalar_one_or_none()

                    if item2:
                        relations = await _calculate_relations_for_item(item2, db2)
                        await db2.commit()
                        logger.info(f"Item {item_id}: created {relations} relations")

                status.status = "completed"
                logger.info(f"Item {item_id}: reprocessing COMPLETED")

            except Exception as e:
                logger.error(f"Error reprocessing item {item_id}: {e}")
                logger.error(traceback.format_exc())
                status.status = "failed"
                status.error = str(e)[:200]
                await db.rollback()

    except Exception as e:
        logger.error(f"Fatal error for item {item_id}: {e}")
        status.status = "failed"
        status.error = str(e)[:200]
    finally:
        await engine.dispose()
        _batch_status[batch_id].append(status)


async def _run_batch_reprocess(item_ids: list[uuid.UUID], db_url: str, batch_id: str):
    """Run batch reprocess for multiple items."""
    logger.info(f"Starting batch reprocess {batch_id} for {len(item_ids)} items")

    for item_id in item_ids:
        await _reprocess_single_item(item_id, db_url, batch_id)
        # Small delay to avoid overwhelming the LLM service
        await asyncio.sleep(2)

    logger.info(f"Batch reprocess {batch_id} completed")


@router.post("/reprocess-all", response_model=BatchReprocessResponse)
async def reprocess_all_items(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Reprocess all content items with URLs.

    This will:
    1. Re-fetch content from stored URLs
    2. Regenerate summaries
    3. Re-extract topics
    4. Recalculate relations
    """
    # Get all items with URLs
    query = select(ContentItem).where(ContentItem.url.isnot(None))
    result = await db.execute(query)
    items = result.scalars().all()

    if not items:
        return BatchReprocessResponse(
            message="No items with URLs found",
            total_items=0,
            queued_items=0,
        )

    # Create batch ID for tracking
    batch_id = str(uuid.uuid4())
    _batch_status[batch_id] = []

    # Get database URL
    from app.config import settings

    db_url = settings.database_url

    # Queue background task
    item_ids = [item.id for item in items]
    background_tasks.add_task(_run_batch_reprocess, item_ids, db_url, batch_id)

    return BatchReprocessResponse(
        message=f"Batch reprocess started. Batch ID: {batch_id}",
        total_items=len(items),
        queued_items=len(items),
    )


@router.post("/reprocess/{content_id}")
async def reprocess_single(
    content_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reprocess a single content item."""
    # Check item exists
    query = select(ContentItem).where(ContentItem.id == content_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Content not found")

    if not item.url:
        raise HTTPException(status_code=400, detail="Item has no URL to reprocess")

    # Create batch ID for tracking
    batch_id = str(uuid.uuid4())
    _batch_status[batch_id] = []

    from app.config import settings

    background_tasks.add_task(_reprocess_single_item, content_id, settings.database_url, batch_id)

    return {
        "message": f"Reprocessing started for {content_id}",
        "batch_id": batch_id,
    }


@router.get("/reprocess-status/{batch_id}")
async def get_reprocess_status(
    batch_id: str,
    user: User = Depends(get_dev_or_current_user),
):
    """Get status of a batch reprocess operation."""
    if batch_id not in _batch_status:
        raise HTTPException(status_code=404, detail="Batch not found")

    statuses = _batch_status[batch_id]
    completed = sum(1 for s in statuses if s.status == "completed")
    failed = sum(1 for s in statuses if s.status == "failed")
    skipped = sum(1 for s in statuses if s.status == "skipped")

    return {
        "batch_id": batch_id,
        "processed": len(statuses),
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "items": [s.model_dump() for s in statuses],
    }


@router.delete("/relations")
async def clear_all_relations(
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear all item relations (for rebuilding)."""
    from sqlalchemy import delete

    result = await db.execute(delete(ItemRelation))
    await db.commit()

    return {"message": f"Deleted {result.rowcount} relations"}


@router.post("/rebuild-relations")
async def rebuild_all_relations(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rebuild all relations based on shared topics."""
    # Clear existing relations
    from sqlalchemy import delete

    await db.execute(delete(ItemRelation))
    await db.commit()

    # Get all items with topics
    query = (
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.status == ProcessingStatus.COMPLETED)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    total_relations = 0
    for item in items:
        relations = await _calculate_relations_for_item(item, db)
        total_relations += relations

    await db.commit()

    return {
        "message": f"Rebuilt relations for {len(items)} items",
        "relations_created": total_relations,
    }


# ============================================================================
# Embedding Endpoints
# ============================================================================

SIMILARITY_THRESHOLD = 0.7  # Minimum similarity to create a relation


async def _generate_embedding_for_item(
    item_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    """Generate embedding for a single item."""
    # Get item
    query = select(ContentItem).where(ContentItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        logger.warning(f"Item {item_id} not found for embedding")
        return False

    if not item.title and not item.summary:
        logger.warning(f"Item {item_id} has no title or summary for embedding")
        return False

    # Generate embedding
    embedding = await generate_embedding_for_content(item.title, item.summary)

    if not embedding:
        logger.error(f"Failed to generate embedding for item {item_id}")
        return False

    # Store or update embedding
    existing_query = select(ContentEmbedding).where(ContentEmbedding.content_id == item_id)
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    from app.config import settings

    if existing:
        existing.embedding = embedding
        existing.model = settings.ollama_embedding_model
        existing.updated_at = datetime.utcnow()
    else:
        new_embedding = ContentEmbedding(
            content_id=item_id,
            embedding=embedding,
            model=settings.ollama_embedding_model,
        )
        db.add(new_embedding)

    await db.commit()
    logger.info(f"Embedding generated for item {item_id}")
    return True


async def _calculate_similarity_relations(
    item_id: uuid.UUID,
    db: AsyncSession,
    threshold: float = SIMILARITY_THRESHOLD,
) -> int:
    """Calculate relations based on embedding similarity."""
    # Get item's embedding
    query = select(ContentEmbedding).where(ContentEmbedding.content_id == item_id)
    result = await db.execute(query)
    item_embedding = result.scalar_one_or_none()

    if not item_embedding:
        return 0

    # Get all other embeddings
    others_query = select(ContentEmbedding).where(ContentEmbedding.content_id != item_id)
    others_result = await db.execute(others_query)
    other_embeddings = others_result.scalars().all()

    relations_created = 0
    for other in other_embeddings:
        # Calculate cosine similarity
        similarity = cosine_similarity(item_embedding.embedding, other.embedding)

        if similarity < threshold:
            continue

        # Check if relation already exists
        src_to_tgt = (ItemRelation.source_id == item_id) & (
            ItemRelation.target_id == other.content_id
        )
        tgt_to_src = (ItemRelation.source_id == other.content_id) & (
            ItemRelation.target_id == item_id
        )
        existing = await db.execute(select(ItemRelation).where(src_to_tgt | tgt_to_src))
        if existing.scalar_one_or_none():
            continue

        # Create relation with SIMILAR type
        relation = ItemRelation(
            source_id=item_id,
            target_id=other.content_id,
            relation_type=RelationType.SIMILAR,
            confidence=similarity,
        )
        db.add(relation)
        relations_created += 1
        logger.info(
            f"Created SIMILAR relation: {item_id} <-> {other.content_id} (score: {similarity:.3f})"
        )

    return relations_created


@router.get("/embeddings/check")
async def check_embeddings_ready(
    user: User = Depends(get_dev_or_current_user),
):
    """Check if embedding model is available."""
    available = await check_embedding_model_available()
    from app.config import settings

    model = settings.ollama_embedding_model
    hint = f"Pull with: ollama pull {model}" if not available else None
    return {
        "model": model,
        "available": available,
        "hint": hint,
    }


@router.post("/embeddings/generate-all")
async def generate_all_embeddings(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate embeddings for all completed items."""
    # Check model availability
    available = await check_embedding_model_available()
    if not available:
        from app.config import settings

        model = settings.ollama_embedding_model
        raise HTTPException(
            status_code=400,
            detail=f"Embedding model not available. Pull with: ollama pull {model}",
        )

    # Get all completed items
    query = select(ContentItem).where(ContentItem.status == ProcessingStatus.COMPLETED)
    result = await db.execute(query)
    items = result.scalars().all()

    if not items:
        return {"message": "No completed items found", "total": 0}

    # Generate embeddings synchronously (to track progress)
    success = 0
    failed = 0
    for item in items:
        try:
            if await _generate_embedding_for_item(item.id, db):
                success += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Embedding failed for {item.id}: {e}")
            failed += 1
        # Small delay to avoid overwhelming Ollama
        await asyncio.sleep(0.5)

    return {
        "message": f"Generated embeddings for {success} items ({failed} failed)",
        "success": success,
        "failed": failed,
        "total": len(items),
    }


@router.post("/embeddings/generate/{content_id}")
async def generate_single_embedding(
    content_id: uuid.UUID,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate embedding for a single item."""
    success = await _generate_embedding_for_item(content_id, db)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to generate embedding")

    return {"message": f"Embedding generated for {content_id}"}


@router.post("/relations/rebuild-from-embeddings")
async def rebuild_relations_from_embeddings(
    threshold: float = SIMILARITY_THRESHOLD,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Rebuild relations based on embedding similarity.

    This creates SIMILAR-type relations between items with
    high semantic similarity.
    """
    # Clear existing SIMILAR relations
    from sqlalchemy import delete

    await db.execute(delete(ItemRelation).where(ItemRelation.relation_type == RelationType.SIMILAR))
    await db.commit()

    # Get all embeddings
    query = select(ContentEmbedding)
    result = await db.execute(query)
    embeddings = result.scalars().all()

    if not embeddings:
        return {"message": "No embeddings found. Generate them first.", "relations": 0}

    total_relations = 0
    for emb in embeddings:
        relations = await _calculate_similarity_relations(emb.content_id, db, threshold)
        total_relations += relations

    await db.commit()

    return {
        "message": f"Created {total_relations} similarity-based relations",
        "relations": total_relations,
        "threshold": threshold,
        "items_processed": len(embeddings),
    }


@router.get("/embeddings/stats")
async def get_embedding_stats(
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics about embeddings."""
    # Count embeddings
    emb_count = await db.execute(select(func.count()).select_from(ContentEmbedding))
    total_embeddings = emb_count.scalar()

    # Count completed items
    item_count = await db.execute(
        select(func.count())
        .select_from(ContentItem)
        .where(ContentItem.status == ProcessingStatus.COMPLETED)
    )
    total_items = item_count.scalar()

    # Count relations by type
    rel_query = select(ItemRelation.relation_type, func.count(ItemRelation.id)).group_by(
        ItemRelation.relation_type
    )
    rel_result = await db.execute(rel_query)
    relations_by_type = {str(r[0].value): r[1] for r in rel_result.all()}

    return {
        "embeddings": total_embeddings,
        "completed_items": total_items,
        "coverage": f"{total_embeddings}/{total_items}" if total_items else "0/0",
        "relations_by_type": relations_by_type,
    }
