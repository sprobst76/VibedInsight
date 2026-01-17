import json
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_dev_or_current_user
from app.models.content import ContentItem, ItemRelation, ProcessingStatus, WeeklySummary
from app.models.user import User, UserItem
from app.schemas import TopicCluster, WeeklySummaryListResponse, WeeklySummaryResponse
from app.services.summarizer import generate_weekly_summary

router = APIRouter()


def get_week_bounds(date: datetime | None = None) -> tuple[datetime, datetime]:
    """Get Monday 00:00 and Sunday 23:59 for the given date's week."""
    if date is None:
        date = datetime.utcnow()

    # Find Monday of the week
    monday = date - timedelta(days=date.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

    # Find Sunday of the week
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)

    return monday, sunday


@router.get("", response_model=list[WeeklySummaryListResponse])
async def list_weekly_summaries(
    limit: int = 10,
    user: User = Depends(get_dev_or_current_user),
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
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get or create summary for the current week."""
    week_start, week_end = get_week_bounds()

    # Check if summary exists for this user
    query = select(WeeklySummary).where(
        WeeklySummary.week_start == week_start,
        WeeklySummary.user_id == user.id,
    )
    result = await db.execute(query)
    summary = result.scalar_one_or_none()

    if not summary:
        # Create a new summary entry (without generating yet)
        # Query through UserItem junction table
        items_query = (
            select(UserItem)
            .options(selectinload(UserItem.content))
            .where(
                UserItem.user_id == user.id,
                UserItem.created_at >= week_start,
                UserItem.created_at <= week_end,
            )
        )
        items_result = await db.execute(items_query)
        user_items = items_result.scalars().all()

        processed_items = [ui for ui in user_items if ui.content.status == ProcessingStatus.COMPLETED]

        summary = WeeklySummary(
            user_id=user.id,
            week_start=week_start,
            week_end=week_end,
            items_count=len(user_items),
            items_processed=len(processed_items),
        )
        db.add(summary)
        await db.commit()
        await db.refresh(summary)

    return _summary_to_response(summary)


@router.get("/{summary_id}", response_model=WeeklySummaryResponse)
async def get_weekly_summary(
    summary_id: int,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific weekly summary."""
    query = select(WeeklySummary).where(WeeklySummary.id == summary_id)
    result = await db.execute(query)
    summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Weekly summary not found")

    # Verify ownership
    if summary.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return _summary_to_response(summary)


@router.post("/{summary_id}/generate", response_model=WeeklySummaryResponse)
async def generate_summary(
    summary_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate or regenerate a weekly summary using AI."""
    query = select(WeeklySummary).where(WeeklySummary.id == summary_id)
    result = await db.execute(query)
    summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Weekly summary not found")

    # Verify ownership
    if summary.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get items for this week belonging to the user WITH topics
    # Query through UserItem junction table
    user_items_query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
        .where(
            UserItem.user_id == user.id,
            UserItem.created_at >= summary.week_start,
            UserItem.created_at <= summary.week_end,
        )
    )
    user_items_result = await db.execute(user_items_query)
    user_items = user_items_result.scalars().all()

    # Filter to completed items
    items = [ui.content for ui in user_items if ui.content.status == ProcessingStatus.COMPLETED]

    if not items:
        raise HTTPException(status_code=400, detail="No processed items found for this week")

    # Prepare content for summarization
    items_content = [
        {"title": item.title or "Untitled", "summary": item.summary or ""}
        for item in items
        if item.summary
    ]

    if not items_content:
        raise HTTPException(status_code=400, detail="No items with summaries found for this week")

    # Build topics by item
    topics_by_item = {
        item.title or "Untitled": [t.name for t in item.topics]
        for item in items
        if item.summary
    }

    # Load relations between items
    item_ids = [item.id for item in items]
    relations_query = select(ItemRelation).where(
        or_(
            ItemRelation.source_id.in_(item_ids),
            ItemRelation.target_id.in_(item_ids),
        )
    )
    relations_result = await db.execute(relations_query)
    relations_raw = relations_result.scalars().all()

    # Build item ID to title map
    id_to_title = {item.id: item.title or "Untitled" for item in items}

    # Build relations list with titles
    relations = [
        {
            "source_title": id_to_title.get(rel.source_id, "Unbekannt"),
            "target_title": id_to_title.get(rel.target_id, "Unbekannt"),
            "relation_type": rel.relation_type.value,
        }
        for rel in relations_raw
        if rel.source_id in id_to_title and rel.target_id in id_to_title
    ]

    # Generate summary
    try:
        result = await generate_weekly_summary(items_content, topics_by_item, relations)

        summary.tldr = result.get("tldr", "")
        summary.summary = result["summary"]
        summary.key_insights = json.dumps(result["key_insights"])
        summary.top_topics = json.dumps(result["top_topics"])
        summary.topic_clusters = json.dumps(result.get("topic_clusters", []))
        summary.connections = json.dumps(result.get("connections", []))
        summary.generated_at = datetime.utcnow()
        summary.items_processed = len(items_content)

        await db.commit()
        await db.refresh(summary)

        return _summary_to_response(summary)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")


@router.post("/generate-current", response_model=WeeklySummaryResponse)
async def generate_current_week_summary(
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create and generate summary for the current week in one call."""
    # First get or create the current week summary for this user
    week_start, week_end = get_week_bounds()

    query = select(WeeklySummary).where(
        WeeklySummary.week_start == week_start,
        WeeklySummary.user_id == user.id,
    )
    result = await db.execute(query)
    summary = result.scalar_one_or_none()

    if not summary:
        # Get items for counting (user's items only) via UserItem
        user_items_query = (
            select(UserItem)
            .options(selectinload(UserItem.content))
            .where(
                UserItem.user_id == user.id,
                UserItem.created_at >= week_start,
                UserItem.created_at <= week_end,
            )
        )
        user_items_result = await db.execute(user_items_query)
        user_items = user_items_result.scalars().all()

        summary = WeeklySummary(
            user_id=user.id,
            week_start=week_start,
            week_end=week_end,
            items_count=len(user_items),
        )
        db.add(summary)
        await db.commit()
        await db.refresh(summary)

    # Get processed items for this week (user's items only) WITH topics
    # Query through UserItem junction table
    user_items_query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
        .where(
            UserItem.user_id == user.id,
            UserItem.created_at >= summary.week_start,
            UserItem.created_at <= summary.week_end,
        )
    )
    user_items_result = await db.execute(user_items_query)
    user_items = user_items_result.scalars().all()

    # Filter to completed items
    items = [ui.content for ui in user_items if ui.content.status == ProcessingStatus.COMPLETED]

    if not items:
        return _summary_to_response(summary)

    items_content = [
        {"title": item.title or "Untitled", "summary": item.summary or ""}
        for item in items
        if item.summary
    ]

    if not items_content:
        return _summary_to_response(summary)

    # Build topics by item
    topics_by_item = {
        item.title or "Untitled": [t.name for t in item.topics]
        for item in items
        if item.summary
    }

    # Load relations between items
    item_ids = [item.id for item in items]
    relations_query = select(ItemRelation).where(
        or_(
            ItemRelation.source_id.in_(item_ids),
            ItemRelation.target_id.in_(item_ids),
        )
    )
    relations_result = await db.execute(relations_query)
    relations_raw = relations_result.scalars().all()

    # Build item ID to title map
    id_to_title = {item.id: item.title or "Untitled" for item in items}

    # Build relations list with titles
    relations = [
        {
            "source_title": id_to_title.get(rel.source_id, "Unbekannt"),
            "target_title": id_to_title.get(rel.target_id, "Unbekannt"),
            "relation_type": rel.relation_type.value,
        }
        for rel in relations_raw
        if rel.source_id in id_to_title and rel.target_id in id_to_title
    ]

    # Generate summary
    try:
        result = await generate_weekly_summary(items_content, topics_by_item, relations)

        summary.tldr = result.get("tldr", "")
        summary.summary = result["summary"]
        summary.key_insights = json.dumps(result["key_insights"])
        summary.top_topics = json.dumps(result["top_topics"])
        summary.topic_clusters = json.dumps(result.get("topic_clusters", []))
        summary.connections = json.dumps(result.get("connections", []))
        summary.generated_at = datetime.utcnow()
        summary.items_processed = len(items_content)

        await db.commit()
        await db.refresh(summary)

    except Exception as e:
        # Log the error and store in summary for debugging
        import logging
        logging.getLogger(__name__).error(f"Weekly summary generation failed: {e}")
        summary.summary = f"Generation failed: {str(e)}"
        await db.commit()
        await db.refresh(summary)

    return _summary_to_response(summary)


def _summary_to_response(summary: WeeklySummary) -> WeeklySummaryResponse:
    """Convert WeeklySummary model to response schema."""
    # Parse topic clusters
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
