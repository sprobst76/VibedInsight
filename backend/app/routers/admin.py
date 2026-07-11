"""
Admin Router - batch maintenance: reprocess everything, rebuild
embeddings/relations, stats. Protected by the API key like everything else.
"""

import asyncio
import logging
import uuid
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_maker, get_db
from app.dependencies import get_current_user
from app.models.content import (
    ContentEmbedding,
    ContentItem,
    ItemRelation,
    ProcessingStatus,
)
from app.models.user import User
from app.services.embeddings import check_embedding_model_available
from app.services.processing import (
    process_item,
    rebuild_relations_for_item,
    reprocess_item,
    update_embedding,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class BatchReprocessResponse(BaseModel):
    """Response for batch reprocess operation."""

    message: str
    total_items: int
    queued_items: int


# Status of recent batch runs, capped so it can't grow unboundedly
_MAX_TRACKED_BATCHES = 20
_batch_status: OrderedDict[str, dict] = OrderedDict()


def _new_batch(total: int) -> str:
    batch_id = str(uuid.uuid4())
    _batch_status[batch_id] = {"total": total, "done": 0, "failed": 0}
    while len(_batch_status) > _MAX_TRACKED_BATCHES:
        _batch_status.popitem(last=False)
    return batch_id


async def _run_batch_reprocess(item_ids: list[uuid.UUID], batch_id: str):
    """Reprocess items one after another (the pipeline serializes LLM calls)."""
    logger.info(f"Starting batch reprocess {batch_id} for {len(item_ids)} items")
    status = _batch_status.get(batch_id, {"total": len(item_ids), "done": 0, "failed": 0})

    for item_id in item_ids:
        try:
            async with async_session_maker() as db:
                ok = await reprocess_item(item_id, db)
            if ok:
                # reprocess_item schedules async processing; wait our turn
                # here to keep the batch roughly sequential
                await asyncio.sleep(1)
                status["done"] += 1
            else:
                status["failed"] += 1
        except Exception as e:
            logger.error(f"Batch reprocess failed for {item_id}: {e}")
            status["failed"] += 1

    logger.info(f"Batch reprocess {batch_id} completed")


@router.post("/reprocess-all", response_model=BatchReprocessResponse)
async def reprocess_all_items(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reprocess all content items (re-fetches URLs where raw_text is gone)."""
    result = await db.execute(select(ContentItem.id))
    item_ids = [row[0] for row in result.all()]

    if not item_ids:
        return BatchReprocessResponse(message="No items found", total_items=0, queued_items=0)

    batch_id = _new_batch(len(item_ids))
    task = asyncio.create_task(_run_batch_reprocess(item_ids, batch_id))
    task.add_done_callback(lambda t: t.exception())

    return BatchReprocessResponse(
        message=f"Batch reprocess started. Batch ID: {batch_id}",
        total_items=len(item_ids),
        queued_items=len(item_ids),
    )


@router.get("/reprocess-status/{batch_id}")
async def get_reprocess_status(
    batch_id: str,
    user: User = Depends(get_current_user),
):
    """Get status of a batch reprocess operation."""
    if batch_id not in _batch_status:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"batch_id": batch_id, **_batch_status[batch_id]}


@router.post("/reprocess/{content_id}")
async def reprocess_single(
    content_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reprocess a single content item by content UUID."""
    ok = await reprocess_item(content_id, db)
    if not ok:
        raise HTTPException(
            status_code=400, detail="Cannot reprocess: item missing or no text/URL"
        )
    return {"message": f"Reprocessing started for {content_id}"}


@router.post("/rebuild-relations")
async def rebuild_all_relations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Wipe and rebuild all relations (embedding similarity + shared topics)."""
    await db.execute(delete(ItemRelation))
    await db.commit()

    result = await db.execute(
        select(ContentItem.id).where(ContentItem.status == ProcessingStatus.COMPLETED)
    )
    item_ids = [row[0] for row in result.all()]

    total_relations = 0
    for item_id in item_ids:
        total_relations += await rebuild_relations_for_item(item_id, db)
    await db.commit()

    return {
        "message": f"Rebuilt relations for {len(item_ids)} items",
        "relations_created": total_relations,
    }


async def _run_embedding_backfill(item_ids: list[uuid.UUID], batch_id: str):
    """Generate embeddings item by item, committing each one."""
    status = _batch_status.get(batch_id, {"total": len(item_ids), "done": 0, "failed": 0})
    for item_id in item_ids:
        try:
            async with async_session_maker() as db:
                item = await db.get(ContentItem, item_id)
                if item and await update_embedding(item, db):
                    await db.commit()
                    status["done"] += 1
                else:
                    status["failed"] += 1
        except Exception as e:
            logger.error(f"Embedding failed for {item_id}: {e}")
            status["failed"] += 1
        await asyncio.sleep(0.2)
    logger.info(f"Embedding backfill {batch_id} finished: {status}")


@router.post("/embeddings/generate-all")
async def generate_all_embeddings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Backfill embeddings for completed items that don't have one yet.

    Runs as a background task (a synchronous request would exceed proxy
    timeouts for large libraries); check progress via /admin/reprocess-status.
    """
    if not await check_embedding_model_available():
        raise HTTPException(
            status_code=400,
            detail=(
                "Embedding model not available. "
                f"Pull with: ollama pull {settings.ollama_embedding_model}"
            ),
        )

    result = await db.execute(
        select(ContentItem.id)
        .outerjoin(ContentEmbedding, ContentEmbedding.content_id == ContentItem.id)
        .where(
            ContentItem.status == ProcessingStatus.COMPLETED,
            ContentEmbedding.id.is_(None),
        )
    )
    item_ids = [row[0] for row in result.all()]

    if not item_ids:
        return {"message": "All completed items already have embeddings", "total": 0}

    batch_id = _new_batch(len(item_ids))
    task = asyncio.create_task(_run_embedding_backfill(item_ids, batch_id))
    task.add_done_callback(lambda t: t.exception())

    return {
        "message": f"Embedding backfill started for {len(item_ids)} items",
        "batch_id": batch_id,
        "total": len(item_ids),
    }


@router.get("/embeddings/check")
async def check_embeddings_ready(user: User = Depends(get_current_user)):
    """Check if the embedding model is available in Ollama."""
    available = await check_embedding_model_available()
    model = settings.ollama_embedding_model
    return {
        "model": model,
        "available": available,
        "hint": None if available else f"Pull with: ollama pull {model}",
    }


@router.get("/ollama/check")
async def check_ollama(user: User = Depends(get_current_user)):
    """List Ollama models and whether the configured ones are available."""
    import httpx
    import ollama

    client = ollama.AsyncClient(
        host=settings.ollama_base_url, timeout=httpx.Timeout(10.0, connect=5.0)
    )
    try:
        response = await client.list()
        available = [m.model for m in response.models]
    except Exception as e:
        return {"error": f"Ollama unreachable: {e}", "base_url": settings.ollama_base_url}

    def has(name: str) -> bool:
        return name in available or f"{name}:latest" in available

    return {
        "available_models": available,
        "chat_model": settings.ollama_model,
        "chat_model_available": has(settings.ollama_model),
        "embedding_model": settings.ollama_embedding_model,
        "embedding_model_available": has(settings.ollama_embedding_model),
    }


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Item, embedding and relation statistics."""
    items_by_status_result = await db.execute(
        select(ContentItem.status, func.count(ContentItem.id)).group_by(ContentItem.status)
    )
    items_by_status = {row[0].value: row[1] for row in items_by_status_result.all()}

    total_embeddings = await db.scalar(select(func.count()).select_from(ContentEmbedding))

    relations_result = await db.execute(
        select(ItemRelation.relation_type, func.count(ItemRelation.id)).group_by(
            ItemRelation.relation_type
        )
    )
    relations_by_type = {row[0].value: row[1] for row in relations_result.all()}

    return {
        "items_by_status": items_by_status,
        "embeddings": total_embeddings,
        "relations_by_type": relations_by_type,
    }


@router.post("/process/{content_id}")
async def process_now(
    content_id: uuid.UUID,
    user: User = Depends(get_current_user),
):
    """Run the processing pipeline for one item synchronously (debugging aid)."""
    await process_item(content_id)
    return {"message": f"Processed {content_id}"}
