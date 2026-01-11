"""
User Items Router - User-specific content operations.

This provides a backwards-compatible API for the Flutter frontend that expects:
- Integer IDs
- User-specific flags (is_favorite, is_read, is_archived)
- GET /items with search, topic filter, pagination

Note: This is a compatibility layer. The privacy-focused architecture uses
encrypted vault entries. This router uses the unencrypted user_items table
for development and transition purposes.
"""

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.content import ContentItem, ItemRelation, Topic
from app.models.user import User, UserItem
from app.schemas import (
    TopicResponse,
    UserItemResponse,
    UserItemsListResponse,
)


class BulkIdsRequest(BaseModel):
    ids: list[int]

router = APIRouter()


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
        created_at=user_item.created_at,
        updated_at=user_item.updated_at,
        processed_at=content.processed_at,
        topics=[TopicResponse.model_validate(t) for t in content.topics],
    )


@router.get("", response_model=UserItemsListResponse)
async def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    topic_id: int | None = Query(None, description="Filter by topic"),
    search: str | None = Query(None, description="Search in title and summary"),
    favorites_only: bool = Query(False, description="Only show favorites"),
    unread_only: bool = Query(False, description="Only show unread items"),
    archived_only: bool = Query(False, description="Only show archived items"),
    sort_by: str = Query("date", pattern="^(date|title|status)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List user's items with filtering, search, and pagination.

    This endpoint combines ContentItem data with user-specific flags
    from the user_items junction table.
    """
    # Base query: user's items with content loaded
    query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
        .where(UserItem.user_id == user.id)
    )

    # Apply filters
    if favorites_only:
        query = query.where(UserItem.is_favorite == True)  # noqa: E712

    if unread_only:
        query = query.where(UserItem.is_read == False)  # noqa: E712

    if archived_only:
        query = query.where(UserItem.is_archived == True)  # noqa: E712
    else:
        # By default, don't show archived items
        query = query.where(UserItem.is_archived == False)  # noqa: E712

    # Topic filter - need to join through content
    if topic_id is not None:
        query = query.join(UserItem.content).where(
            ContentItem.topics.any(Topic.id == topic_id)
        )

    # Search filter
    if search:
        search_pattern = f"%{search}%"
        # Need to join content if not already joined
        if topic_id is None:
            query = query.join(UserItem.content)
        query = query.where(
            or_(
                ContentItem.title.ilike(search_pattern),
                ContentItem.summary.ilike(search_pattern),
            )
        )

    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Sorting
    if sort_by == "date":
        order_col = UserItem.created_at
    elif sort_by == "title":
        # Need to sort by content.title
        if topic_id is None and search is None:
            query = query.join(UserItem.content)
        order_col = ContentItem.title
    else:  # status
        if topic_id is None and search is None:
            query = query.join(UserItem.content)
        order_col = ContentItem.status

    if sort_order == "desc":
        query = query.order_by(order_col.desc())
    else:
        query = query.order_by(order_col.asc())

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await db.execute(query)
    user_items = result.scalars().unique().all()

    # Build response
    items = [_build_user_item_response(ui) for ui in user_items]

    return UserItemsListResponse(
        items=items,
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=math.ceil((total or 0) / page_size) if total else 0,
    )


@router.get("/{item_id}", response_model=UserItemResponse)
async def get_item(
    item_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single user item by ID."""
    query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
        .where(UserItem.id == item_id, UserItem.user_id == user.id)
    )
    result = await db.execute(query)
    user_item = result.scalar_one_or_none()

    if not user_item:
        raise HTTPException(status_code=404, detail="Item not found")

    return _build_user_item_response(user_item)


@router.get("/{item_id}/relations")
async def get_item_with_relations(
    item_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a user item with related content items.

    This proxies to the content relations endpoint while adding user-specific data.
    """
    query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
        .where(UserItem.id == item_id, UserItem.user_id == user.id)
    )
    result = await db.execute(query)
    user_item = result.scalar_one_or_none()

    if not user_item:
        raise HTTPException(status_code=404, detail="Item not found")

    content = user_item.content

    # Get relations
    from sqlalchemy import or_
    relations_query = (
        select(ItemRelation)
        .options(
            selectinload(ItemRelation.source_item).selectinload(ContentItem.topics),
            selectinload(ItemRelation.target_item).selectinload(ContentItem.topics),
        )
        .where(
            or_(
                ItemRelation.source_id == content.id,
                ItemRelation.target_id == content.id,
            )
        )
    )
    relations_result = await db.execute(relations_query)
    relations = relations_result.scalars().unique().all()

    related_items = []
    for rel in relations:
        if rel.source_id == content.id:
            related = rel.target_item
        else:
            related = rel.source_item

        related_items.append({
            "id": str(related.id),  # UUID as string for frontend
            "title": related.title,
            "source": related.source,
            "relation_type": rel.relation_type.value,
            "confidence": rel.confidence,
        })

    # Build response with relations
    base_response = _build_user_item_response(user_item)
    return {
        **base_response.model_dump(),
        "related_items": related_items,
    }


@router.post("/{item_id}/favorite", response_model=UserItemResponse)
async def toggle_favorite(
    item_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle favorite status for an item."""
    query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
        .where(UserItem.id == item_id, UserItem.user_id == user.id)
    )
    result = await db.execute(query)
    user_item = result.scalar_one_or_none()

    if not user_item:
        raise HTTPException(status_code=404, detail="Item not found")

    user_item.is_favorite = not user_item.is_favorite
    await db.commit()
    await db.refresh(user_item)

    return _build_user_item_response(user_item)


@router.post("/{item_id}/read", response_model=UserItemResponse)
async def toggle_read(
    item_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle read status for an item."""
    query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
        .where(UserItem.id == item_id, UserItem.user_id == user.id)
    )
    result = await db.execute(query)
    user_item = result.scalar_one_or_none()

    if not user_item:
        raise HTTPException(status_code=404, detail="Item not found")

    user_item.is_read = not user_item.is_read
    await db.commit()
    await db.refresh(user_item)

    return _build_user_item_response(user_item)


@router.post("/{item_id}/archive", response_model=UserItemResponse)
async def toggle_archive(
    item_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle archive status for an item."""
    query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
        .where(UserItem.id == item_id, UserItem.user_id == user.id)
    )
    result = await db.execute(query)
    user_item = result.scalar_one_or_none()

    if not user_item:
        raise HTTPException(status_code=404, detail="Item not found")

    user_item.is_archived = not user_item.is_archived
    await db.commit()
    await db.refresh(user_item)

    return _build_user_item_response(user_item)


@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user item (removes the user-content link, not the content itself)."""
    query = select(UserItem).where(
        UserItem.id == item_id, UserItem.user_id == user.id
    )
    result = await db.execute(query)
    user_item = result.scalar_one_or_none()

    if not user_item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Decrement ref_count on content
    content = await db.get(ContentItem, user_item.content_id)
    if content:
        content.ref_count = max(0, content.ref_count - 1)

    await db.delete(user_item)
    await db.commit()

    return {"status": "deleted"}


# Bulk Operations
@router.post("/bulk/delete")
async def bulk_delete(
    request: BulkIdsRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple user items."""
    query = select(UserItem).where(
        UserItem.id.in_(request.ids), UserItem.user_id == user.id
    )
    result = await db.execute(query)
    user_items = result.scalars().all()

    deleted_ids = []
    for user_item in user_items:
        # Decrement ref_count
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
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark multiple items as read."""
    query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
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
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive multiple items."""
    query = (
        select(UserItem)
        .options(
            selectinload(UserItem.content).selectinload(ContentItem.topics)
        )
        .where(UserItem.id.in_(request.ids), UserItem.user_id == user.id)
    )
    result = await db.execute(query)
    user_items = result.scalars().unique().all()

    for user_item in user_items:
        user_item.is_archived = True

    await db.commit()

    return [_build_user_item_response(ui) for ui in user_items]
