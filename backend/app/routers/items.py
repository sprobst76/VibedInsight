from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.content import ContentItem, ItemRelation, RelationType
from app.schemas import (
    ContentItemListResponse,
    ContentItemResponse,
    ContentItemWithRelationsResponse,
    ItemRelationResponse,
    PaginatedResponse,
    RelatedItemResponse,
)

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


@router.get("/{item_id}/relations", response_model=ContentItemWithRelationsResponse)
async def get_item_with_relations(item_id: int, db: AsyncSession = Depends(get_db)):
    """Get a content item with all its related items."""
    # Get the item
    query = (
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.id == item_id)
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Get explicit relations (from item_relations table)
    outgoing_query = (
        select(ItemRelation)
        .options(selectinload(ItemRelation.target_item))
        .where(ItemRelation.source_id == item_id)
    )
    incoming_query = (
        select(ItemRelation)
        .options(selectinload(ItemRelation.source_item))
        .where(ItemRelation.target_id == item_id)
    )

    outgoing_result = await db.execute(outgoing_query)
    incoming_result = await db.execute(incoming_query)

    outgoing_relations = outgoing_result.scalars().all()
    incoming_relations = incoming_result.scalars().all()

    # Build related items list
    related_items = []

    # Add outgoing relations
    for rel in outgoing_relations:
        target = rel.target_item
        related_items.append(RelatedItemResponse(
            id=target.id,
            title=target.title,
            source=target.source,
            relation_type=rel.relation_type,
            confidence=rel.confidence,
        ))

    # Add incoming relations (reverse direction)
    for rel in incoming_relations:
        source = rel.source_item
        related_items.append(RelatedItemResponse(
            id=source.id,
            title=source.title,
            source=source.source,
            relation_type=rel.relation_type,
            confidence=rel.confidence,
        ))

    # Find items with shared topics (implicit relations)
    if item.topics:
        topic_ids = [t.id for t in item.topics]
        # Use OR condition to find items sharing any topic
        shared_topic_query = (
            select(ContentItem)
            .options(selectinload(ContentItem.topics))
            .where(ContentItem.id != item_id)
            .where(or_(*[ContentItem.topics.any(id=tid) for tid in topic_ids]))
            .limit(10)
        )

        shared_result = await db.execute(shared_topic_query)
        shared_items = shared_result.scalars().unique().all()

        # Add as implicit relations (lower confidence)
        existing_ids = {r.id for r in related_items}
        for shared_item in shared_items:
            if shared_item.id not in existing_ids:
                # Calculate confidence based on number of shared topics
                shared_topic_count = len(set(t.id for t in shared_item.topics) & set(topic_ids))
                confidence = min(0.3 + (shared_topic_count * 0.2), 0.9)

                related_items.append(RelatedItemResponse(
                    id=shared_item.id,
                    title=shared_item.title,
                    source=shared_item.source,
                    relation_type=RelationType.RELATED,
                    confidence=confidence,
                ))

    return ContentItemWithRelationsResponse(
        id=item.id,
        content_type=item.content_type,
        status=item.status,
        url=item.url,
        title=item.title,
        source=item.source,
        raw_text=item.raw_text,
        summary=item.summary,
        created_at=item.created_at,
        updated_at=item.updated_at,
        processed_at=item.processed_at,
        topics=item.topics,
        related_items=related_items,
    )


@router.post("/{item_id}/relations/{target_id}", response_model=ItemRelationResponse)
async def create_relation(
    item_id: int,
    target_id: int,
    relation_type: RelationType = RelationType.RELATED,
    confidence: float = Query(1.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """Create a relation between two items."""
    # Verify both items exist
    source_query = select(ContentItem).where(ContentItem.id == item_id)
    target_query = select(ContentItem).where(ContentItem.id == target_id)

    source_result = await db.execute(source_query)
    target_result = await db.execute(target_query)

    if not source_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Source item not found")
    if not target_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Target item not found")

    if item_id == target_id:
        raise HTTPException(status_code=400, detail="Cannot create self-relation")

    # Check if relation already exists
    existing_query = select(ItemRelation).where(
        ItemRelation.source_id == item_id,
        ItemRelation.target_id == target_id,
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Relation already exists")

    # Create relation
    relation = ItemRelation(
        source_id=item_id,
        target_id=target_id,
        relation_type=relation_type,
        confidence=confidence,
    )
    db.add(relation)
    await db.commit()
    await db.refresh(relation)

    return relation


@router.delete("/{item_id}/relations/{target_id}")
async def delete_relation(
    item_id: int,
    target_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a relation between two items."""
    query = select(ItemRelation).where(
        ItemRelation.source_id == item_id,
        ItemRelation.target_id == target_id,
    )
    result = await db.execute(query)
    relation = result.scalar_one_or_none()

    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")

    await db.delete(relation)
    await db.commit()

    return {"status": "deleted"}
