"""
Items Router - the API the Flutter frontend talks to.

UserItem = per-user flags (favorite/read/archived/rating) + link to the
shared ContentItem. Integer IDs.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.content import ContentItem, ItemRelation, ProcessingStatus, Topic
from app.models.user import User, UserItem
from app.schemas import (
    ContentItemUpdate,
    TopicResponse,
    UserItemResponse,
    UserItemsListResponse,
)
from app.services.processing import reprocess_item

router = APIRouter()


class BulkIdsRequest(BaseModel):
    ids: list[int]


class RatingRequest(BaseModel):
    rating: int  # 0=unrated, 1-5=stars


def _build_user_item_response(user_item: UserItem) -> UserItemResponse:
    """Build UserItemResponse from UserItem with loaded content."""
    content = user_item.content
    return UserItemResponse(
        id=user_item.id,
        content_type=content.content_type,
        status=content.status,
        url=content.url,
        title=content.title,
        source=content.source,
        summary=content.summary,
        is_favorite=user_item.is_favorite,
        is_read=user_item.is_read,
        is_archived=user_item.is_archived,
        rating=user_item.rating,
        triage_score=user_item.triage_score,
        created_at=user_item.created_at,
        updated_at=user_item.updated_at,
        processed_at=content.processed_at,
        topics=[TopicResponse.model_validate(t) for t in content.topics],
    )


async def _get_user_item(item_id: int, user: User, db: AsyncSession) -> UserItem:
    """Load a UserItem (with content+topics) owned by the user, or 404."""
    query = (
        select(UserItem)
        .options(selectinload(UserItem.content).selectinload(ContentItem.topics))
        .where(UserItem.id == item_id, UserItem.user_id == user.id)
    )
    result = await db.execute(query)
    user_item = result.scalar_one_or_none()

    if not user_item:
        raise HTTPException(status_code=404, detail="Item not found")

    return user_item


@router.get("/graph/data")
async def get_graph_data(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's content items and their relations as graph data."""
    items_query = (
        select(ContentItem)
        .join(UserItem, UserItem.content_id == ContentItem.id)
        .options(selectinload(ContentItem.topics))
        .where(
            UserItem.user_id == user.id,
            ContentItem.status == ProcessingStatus.COMPLETED,
        )
    )
    items_result = await db.execute(items_query)
    items = items_result.scalars().unique().all()
    item_ids = {item.id for item in items}

    relations_result = await db.execute(select(ItemRelation))
    relations = [
        rel
        for rel in relations_result.scalars().all()
        if rel.source_id in item_ids and rel.target_id in item_ids
    ]

    nodes = []
    for item in items:
        primary_topic = item.topics[0].name if item.topics else None
        nodes.append(
            {
                "id": str(item.id),
                "title": item.title or "Untitled",
                "source": item.source,
                "topic_count": len(item.topics),
                "primary_topic": primary_topic,
                "topics": [t.name for t in item.topics],
            }
        )

    edges = [
        {
            "source": str(rel.source_id),
            "target": str(rel.target_id),
            "weight": rel.confidence,
            "type": rel.relation_type.value,
        }
        for rel in relations
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


@router.get("", response_model=UserItemsListResponse)
async def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    topic_id: int | None = Query(None, description="Filter by topic"),
    search: str | None = Query(None, description="Search in title and summary"),
    favorites_only: bool = Query(False, description="Only show favorites"),
    unread_only: bool = Query(False, description="Only show unread items"),
    archived_only: bool = Query(False, description="Only show archived items"),
    sort_by: str = Query("date", pattern="^(date|title|status|triage)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the user's items with filtering, search, and pagination."""
    query = (
        select(UserItem)
        .options(selectinload(UserItem.content).selectinload(ContentItem.topics))
        .where(UserItem.user_id == user.id)
    )

    if favorites_only:
        query = query.where(UserItem.is_favorite.is_(True))

    if unread_only:
        query = query.where(UserItem.is_read.is_(False))

    if archived_only:
        query = query.where(UserItem.is_archived.is_(True))
    else:
        query = query.where(UserItem.is_archived.is_(False))

    needs_content_join = topic_id is not None or search or sort_by in ("title", "status")
    if needs_content_join:
        query = query.join(UserItem.content)

    if topic_id is not None:
        query = query.where(ContentItem.topics.any(Topic.id == topic_id))

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                ContentItem.title.ilike(search_pattern),
                ContentItem.summary.ilike(search_pattern),
            )
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery()))

    if sort_by == "date":
        order_col = UserItem.created_at
    elif sort_by == "title":
        order_col = ContentItem.title
    elif sort_by == "triage":
        order_col = UserItem.triage_score
    else:
        order_col = ContentItem.status

    ordered = order_col.desc() if sort_order == "desc" else order_col.asc()
    # Keep unscored items at the bottom when sorting by triage.
    if sort_by == "triage":
        ordered = ordered.nullslast()
    query = query.order_by(ordered)

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    user_items = result.scalars().unique().all()

    return UserItemsListResponse(
        items=[_build_user_item_response(ui) for ui in user_items],
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=math.ceil((total or 0) / page_size) if total else 0,
    )


# NOTE: bulk routes must be declared before the /{item_id} routes,
# otherwise "bulk" is captured as item_id and the request 422s.
@router.post("/bulk/delete")
async def bulk_delete(
    request: BulkIdsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple user items."""
    query = select(UserItem).where(UserItem.id.in_(request.ids), UserItem.user_id == user.id)
    result = await db.execute(query)
    user_items = result.scalars().all()

    deleted_ids = []
    for user_item in user_items:
        content = await db.get(ContentItem, user_item.content_id)
        if content:
            content.ref_count = max(0, content.ref_count - 1)

        deleted_ids.append(user_item.id)
        await db.delete(user_item)

    await db.commit()

    return {"deleted_ids": deleted_ids}


@router.post("/bulk/read", response_model=list[UserItemResponse])
async def bulk_mark_read(
    request: BulkIdsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark multiple items as read."""
    query = (
        select(UserItem)
        .options(selectinload(UserItem.content).selectinload(ContentItem.topics))
        .where(UserItem.id.in_(request.ids), UserItem.user_id == user.id)
    )
    result = await db.execute(query)
    user_items = result.scalars().unique().all()

    for user_item in user_items:
        user_item.is_read = True

    await db.commit()

    return [_build_user_item_response(ui) for ui in user_items]


@router.post("/bulk/archive", response_model=list[UserItemResponse])
async def bulk_archive(
    request: BulkIdsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive multiple items."""
    query = (
        select(UserItem)
        .options(selectinload(UserItem.content).selectinload(ContentItem.topics))
        .where(UserItem.id.in_(request.ids), UserItem.user_id == user.id)
    )
    result = await db.execute(query)
    user_items = result.scalars().unique().all()

    for user_item in user_items:
        user_item.is_archived = True

    await db.commit()

    return [_build_user_item_response(ui) for ui in user_items]


@router.get("/{item_id}", response_model=UserItemResponse)
async def get_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single user item by ID."""
    user_item = await _get_user_item(item_id, user, db)
    return _build_user_item_response(user_item)


@router.get("/{item_id}/relations")
async def get_item_with_relations(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a user item with related content items."""
    user_item = await _get_user_item(item_id, user, db)
    content = user_item.content

    relations_query = (
        select(ItemRelation)
        .options(
            selectinload(ItemRelation.source_item),
            selectinload(ItemRelation.target_item),
        )
        .where(
            or_(
                ItemRelation.source_id == content.id,
                ItemRelation.target_id == content.id,
            )
        )
        .order_by(ItemRelation.confidence.desc())
    )
    relations_result = await db.execute(relations_query)
    relations = relations_result.scalars().unique().all()

    related_items = []
    for rel in relations:
        related = rel.target_item if rel.source_id == content.id else rel.source_item
        related_items.append(
            {
                "id": str(related.id),
                "title": related.title,
                "source": related.source,
                "relation_type": rel.relation_type.value,
                "confidence": rel.confidence,
            }
        )

    base_response = _build_user_item_response(user_item)
    return {
        **base_response.model_dump(),
        "related_items": related_items,
    }


@router.patch("/{item_id}", response_model=UserItemResponse)
async def update_item(
    item_id: int,
    request: ContentItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update title, summary, or topics of an item's content."""
    user_item = await _get_user_item(item_id, user, db)
    content = user_item.content

    if request.title is not None:
        content.title = request.title
    if request.summary is not None:
        content.summary = request.summary
    if request.topic_ids is not None:
        topics_result = await db.execute(select(Topic).where(Topic.id.in_(request.topic_ids)))
        content.topics = list(topics_result.scalars().all())

    await db.commit()
    await db.refresh(user_item)

    return _build_user_item_response(user_item)


@router.post("/{item_id}/reprocess", response_model=UserItemResponse)
async def reprocess(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-run the AI pipeline for an item (re-fetches the URL if needed)."""
    user_item = await _get_user_item(item_id, user, db)

    ok = await reprocess_item(user_item.content_id, db)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Cannot reprocess: no stored text and no URL to re-fetch",
        )

    await db.refresh(user_item)
    return _build_user_item_response(user_item)


@router.post("/{item_id}/favorite", response_model=UserItemResponse)
async def toggle_favorite(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle favorite status for an item."""
    user_item = await _get_user_item(item_id, user, db)
    user_item.is_favorite = not user_item.is_favorite
    await db.commit()
    await db.refresh(user_item)
    return _build_user_item_response(user_item)


@router.post("/{item_id}/read", response_model=UserItemResponse)
async def toggle_read(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle read status for an item."""
    user_item = await _get_user_item(item_id, user, db)
    user_item.is_read = not user_item.is_read
    await db.commit()
    await db.refresh(user_item)
    return _build_user_item_response(user_item)


@router.post("/{item_id}/archive", response_model=UserItemResponse)
async def toggle_archive(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle archive status for an item."""
    user_item = await _get_user_item(item_id, user, db)
    user_item.is_archived = not user_item.is_archived
    await db.commit()
    await db.refresh(user_item)
    return _build_user_item_response(user_item)


@router.post("/{item_id}/rating", response_model=UserItemResponse)
async def set_rating(
    item_id: int,
    request: RatingRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set rating (0-5) for an item. 0 means unrated."""
    user_item = await _get_user_item(item_id, user, db)
    user_item.rating = max(0, min(5, request.rating))
    await db.commit()
    await db.refresh(user_item)
    return _build_user_item_response(user_item)


@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user item (removes the user-content link, not the content itself)."""
    query = select(UserItem).where(UserItem.id == item_id, UserItem.user_id == user.id)
    result = await db.execute(query)
    user_item = result.scalar_one_or_none()

    if not user_item:
        raise HTTPException(status_code=404, detail="Item not found")

    content = await db.get(ContentItem, user_item.content_id)
    if content:
        content.ref_count = max(0, content.ref_count - 1)

    await db.delete(user_item)
    await db.commit()

    return {"status": "deleted"}
