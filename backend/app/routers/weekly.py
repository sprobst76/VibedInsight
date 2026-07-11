"""
Weekly summary router.

The generation logic lives in one helper (generate_summary_for) that both
endpoints and the Sunday-evening scheduler (app.services.scheduler) share.
"""

import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.content import ContentItem, ItemRelation, ProcessingStatus, WeeklySummary
from app.models.user import User, UserItem
from app.schemas import TopicCluster, WeeklySummaryListResponse, WeeklySummaryResponse
from app.services.summarizer import generate_weekly_summary

logger = logging.getLogger(__name__)

router = APIRouter()


class NoItemsError(Exception):
    """No completed, summarized items in the requested week."""


def get_week_bounds(date: datetime | None = None) -> tuple[datetime, datetime]:
    """Get Monday 00:00 and Sunday 23:59 for the given date's week."""
    if date is None:
        date = datetime.utcnow()

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
        raise NoItemsError(
            f"No completed items with summaries in week {summary.week_start.date()}"
        )

    items_content = [
        {"title": item.title or "Untitled", "summary": item.summary or ""} for item in items
    ]
    topics_by_item = {
        item.title or "Untitled": [t.name for t in item.topics] for item in items
    }

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
    summary.generated_at = datetime.utcnow()
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


@router.post("/generate-current", response_model=WeeklySummaryResponse)
async def generate_current_week_summary(
    topic_id: int | None = Query(None, description="Filter by topic ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create and generate summary for the current week in one call."""
    summary = await get_or_create_week_summary(user, db)
    return await _generate_or_http_error(summary, user, db, topic_id)


@router.get("/{summary_id}", response_model=WeeklySummaryResponse)
async def get_weekly_summary(
    summary_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific weekly summary."""
    summary = await _get_owned_summary(summary_id, user, db)
    return _summary_to_response(summary)


@router.post("/{summary_id}/generate", response_model=WeeklySummaryResponse)
async def generate_summary(
    summary_id: int,
    topic_id: int | None = Query(None, description="Filter by topic ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate or regenerate a weekly summary using AI."""
    summary = await _get_owned_summary(summary_id, user, db)
    return await _generate_or_http_error(summary, user, db, topic_id)


async def _get_owned_summary(summary_id: int, user: User, db: AsyncSession) -> WeeklySummary:
    result = await db.execute(select(WeeklySummary).where(WeeklySummary.id == summary_id))
    summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Weekly summary not found")
    if summary.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return summary


async def _generate_or_http_error(
    summary: WeeklySummary, user: User, db: AsyncSession, topic_id: int | None
) -> WeeklySummaryResponse:
    try:
        summary = await generate_summary_for(summary, user, db, topic_id)
    except NoItemsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Weekly summary generation failed")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {e}")

    return _summary_to_response(summary)


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
