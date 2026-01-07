from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.content import ContentItem
from app.schemas import ContentItemListResponse, ContentItemResponse, PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
async def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    topic_id: int | None = None,
    search: str | None = Query(None, min_length=1, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    """List all content items with pagination, filtering, and search."""
    query = select(ContentItem).options(selectinload(ContentItem.topics))

    # Topic filter
    if topic_id:
        query = query.filter(ContentItem.topics.any(id=topic_id))

    # Search filter (title and summary)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                ContentItem.title.ilike(search_pattern),
                ContentItem.summary.ilike(search_pattern),
            )
        )

    # Count total with filters
    count_query = select(func.count()).select_from(ContentItem)
    if topic_id:
        count_query = count_query.filter(ContentItem.topics.any(id=topic_id))
    if search:
        search_pattern = f"%{search}%"
        count_query = count_query.filter(
            or_(
                ContentItem.title.ilike(search_pattern),
                ContentItem.summary.ilike(search_pattern),
            )
        )
    total = await db.scalar(count_query)

    # Paginate
    query = query.order_by(ContentItem.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[ContentItemListResponse.model_validate(item) for item in items],
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=(total or 0 + page_size - 1) // page_size if total else 0,
    )


@router.get("/{item_id}", response_model=ContentItemResponse)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single content item by ID."""
    query = (
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.id == item_id)
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


@router.delete("/{item_id}")
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a content item."""
    query = select(ContentItem).where(ContentItem.id == item_id)
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)
    await db.commit()

    return {"status": "deleted", "id": item_id}
