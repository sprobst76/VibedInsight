"""
Weekly summary router.

The generation logic lives in one helper (generate_summary_for) that both
endpoints and the Sunday-evening scheduler (app.services.scheduler) share.
"""

import asyncio
import json
import logging
from collections import OrderedDict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session_maker, get_db
from app.dependencies import get_current_user
from app.models.content import ContentItem, ItemRelation, ProcessingStatus, WeeklySummary
from app.models.user import User, UserItem
from app.schemas import (
    TopicCluster,
    WeeklyGenerationResponse,
    WeeklySummaryListResponse,
    WeeklySummaryResponse,
)
from app.services.summarizer import generate_weekly_summary
from app.timeutils import utcnow

logger = logging.getLogger(__name__)

router = APIRouter()


class NoItemsError(Exception):
    """No completed, summarized items in the requested week."""


# Digest generation is slow on the CPU VPS (minutes for a heavy week), so it
# runs as a background task and the app polls for status. State is in-memory
# (single-user); a process restart drops the task and its status together.
_MAX_TRACKED = 32
_generation_status: OrderedDict[int, dict] = OrderedDict()


def _set_status(summary_id: int, status: str, error: str | None = None) -> None:
    _generation_status[summary_id] = {"status": status, "error": error}
    _generation_status.move_to_end(summary_id)
    while len(_generation_status) > _MAX_TRACKED:
        _generation_status.popitem(last=False)


async def _run_generation(summary_id: int, user_id: int, topic_id: int | None) -> None:
    """Background worker: generate the digest in its own DB session."""
    try:
        async with async_session_maker() as db:
            summary = await db.get(WeeklySummary, summary_id)
            user = await db.get(User, user_id)
            if summary is None or user is None:
                raise NoItemsError("Summary or user no longer exists")
            await generate_summary_for(summary, user, db, topic_id)
        _set_status(summary_id, "completed")
    except NoItemsError as e:
        _set_status(summary_id, "failed", str(e))
    except Exception as e:
        logger.exception("Async weekly generation failed for summary %s", summary_id)
        _set_status(summary_id, "failed", str(e))


def _start_generation(summary_id: int, user_id: int, topic_id: int | None) -> None:
    _set_status(summary_id, "processing")
    task = asyncio.create_task(_run_generation(summary_id, user_id, topic_id))
    task.add_done_callback(lambda t: t.exception())


def get_week_bounds(date: datetime | None = None) -> tuple[datetime, datetime]:
    """Get Monday 00:00 and Sunday 23:59 for the given date's week."""
    if date is None:
        date = utcnow()

    monday = date - timedelta(days=date.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

    return monday, sunday


async def get_or_create_week_summary(
    user: User, db: AsyncSession, date: datetime | None = None
) -> WeeklySummary:
    """Get or create the WeeklySummary row for the week containing `date`."""
    week_start, week_end = get_week_bounds(date)

    result = await db.execute(
        select(WeeklySummary).where(
            WeeklySummary.week_start == week_start,
            WeeklySummary.user_id == user.id,
        )
    )
    summary = result.scalar_one_or_none()
    if summary:
        return summary

    items_result = await db.execute(
        select(UserItem).where(
            UserItem.user_id == user.id,
            UserItem.created_at >= week_start,
            UserItem.created_at <= week_end,
        )
    )
    user_items = items_result.scalars().all()

    summary = WeeklySummary(
        user_id=user.id,
        week_start=week_start,
        week_end=week_end,
        items_count=len(user_items),
    )
    db.add(summary)
    await db.commit()
    await db.refresh(summary)
    return summary


async def generate_summary_for(
    summary: WeeklySummary,
    user: User,
    db: AsyncSession,
    topic_id: int | None = None,
) -> WeeklySummary:
    """
    Generate (or regenerate) the AI digest for a WeeklySummary row.

    Raises NoItemsError if the week has no completed items with summaries.
    """
    user_items_result = await db.execute(
        select(UserItem)
        .options(selectinload(UserItem.content).selectinload(ContentItem.topics))
        .where(
            UserItem.user_id == user.id,
            UserItem.created_at >= summary.week_start,
            UserItem.created_at <= summary.week_end,
        )
    )
    user_items = user_items_result.scalars().all()

    items = [
        ui.content
        for ui in user_items
        if ui.content.status == ProcessingStatus.COMPLETED and ui.content.summary
    ]

    if topic_id is not None:
        items = [i for i in items if any(t.id == topic_id for t in i.topics)]

    if not items:
        raise NoItemsError(f"No completed items with summaries in week {summary.week_start.date()}")

    items_content = [
        {"title": item.title or "Untitled", "summary": item.summary or ""} for item in items
    ]
    topics_by_item = {item.title or "Untitled": [t.name for t in item.topics] for item in items}

    item_ids = [item.id for item in items]
    relations_result = await db.execute(
        select(ItemRelation).where(
            or_(
                ItemRelation.source_id.in_(item_ids),
                ItemRelation.target_id.in_(item_ids),
            )
        )
    )
    id_to_title = {item.id: item.title or "Untitled" for item in items}
    relations = [
        {
            "source_title": id_to_title[rel.source_id],
            "target_title": id_to_title[rel.target_id],
            "relation_type": rel.relation_type.value,
        }
        for rel in relations_result.scalars().all()
        if rel.source_id in id_to_title and rel.target_id in id_to_title
    ]

    result = await generate_weekly_summary(items_content, topics_by_item, relations)

    summary.tldr = result["tldr"]
    summary.summary = result["summary"]
    summary.key_insights = json.dumps(result["key_insights"])
    summary.top_topics = json.dumps(result["top_topics"])
    summary.topic_clusters = json.dumps(result["topic_clusters"])
    summary.connections = json.dumps(result["connections"])
    summary.generated_at = utcnow()
    summary.items_processed = len(items_content)

    await db.commit()
    await db.refresh(summary)
    return summary


@router.get("", response_model=list[WeeklySummaryListResponse])
async def list_weekly_summaries(
    limit: int = 10,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all weekly summaries for the current user, most recent first."""
    query = (
        select(WeeklySummary)
        .where(WeeklySummary.user_id == user.id)
        .order_by(WeeklySummary.week_start.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    summaries = result.scalars().all()

    return [
        WeeklySummaryListResponse(
            id=s.id,
            week_start=s.week_start,
            week_end=s.week_end,
            items_count=s.items_count,
            items_processed=s.items_processed,
            has_summary=s.summary is not None,
        )
        for s in summaries
    ]


@router.get("/current", response_model=WeeklySummaryResponse)
async def get_current_week_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get or create summary for the current week."""
    summary = await get_or_create_week_summary(user, db)
    return _summary_to_response(summary)


@router.post("/generate-current", response_model=WeeklyGenerationResponse)
async def generate_current_week_summary(
    topic_id: int | None = Query(None, description="Filter by topic ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kick off async generation of the current week's digest; poll for status."""
    summary = await get_or_create_week_summary(user, db)
    _start_generation(summary.id, user.id, topic_id)
    return WeeklyGenerationResponse(summary_id=summary.id, status="processing")


@router.get("/{summary_id}", response_model=WeeklySummaryResponse)
async def get_weekly_summary(
    summary_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific weekly summary."""
    summary = await _get_owned_summary(summary_id, user, db)
    return _summary_to_response(summary)


@router.post("/{summary_id}/generate", response_model=WeeklyGenerationResponse)
async def generate_summary(
    summary_id: int,
    topic_id: int | None = Query(None, description="Filter by topic ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kick off async (re)generation of a weekly digest; poll for status."""
    summary = await _get_owned_summary(summary_id, user, db)
    _start_generation(summary.id, user.id, topic_id)
    return WeeklyGenerationResponse(summary_id=summary.id, status="processing")


@router.get("/{summary_id}/generation-status", response_model=WeeklyGenerationResponse)
async def generation_status(
    summary_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll the state of an async digest generation."""
    summary = await _get_owned_summary(summary_id, user, db)
    tracked = _generation_status.get(summary_id)
    if tracked:
        return WeeklyGenerationResponse(
            summary_id=summary_id, status=tracked["status"], error=tracked["error"]
        )
    # Nothing tracked (e.g. after a restart): infer from the stored digest.
    status = "completed" if summary.summary else "idle"
    return WeeklyGenerationResponse(summary_id=summary_id, status=status)


async def _get_owned_summary(summary_id: int, user: User, db: AsyncSession) -> WeeklySummary:
    result = await db.execute(select(WeeklySummary).where(WeeklySummary.id == summary_id))
    summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Weekly summary not found")
    if summary.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return summary


def _summary_to_response(summary: WeeklySummary) -> WeeklySummaryResponse:
    """Convert WeeklySummary model to response schema."""
    topic_clusters_raw = json.loads(summary.topic_clusters) if summary.topic_clusters else []
    topic_clusters = [
        TopicCluster(
            name=c.get("name", ""),
            article_count=c.get("article_count", 0),
            description=c.get("description", ""),
        )
        for c in topic_clusters_raw
    ]

    return WeeklySummaryResponse(
        id=summary.id,
        week_start=summary.week_start,
        week_end=summary.week_end,
        tldr=summary.tldr,
        summary=summary.summary,
        key_insights=json.loads(summary.key_insights) if summary.key_insights else [],
        top_topics=json.loads(summary.top_topics) if summary.top_topics else [],
        topic_clusters=topic_clusters,
        connections=json.loads(summary.connections) if summary.connections else [],
        items_count=summary.items_count,
        items_processed=summary.items_processed,
        created_at=summary.created_at,
        generated_at=summary.generated_at,
    )
