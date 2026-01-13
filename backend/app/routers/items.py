"""
Content Items Router - Anonymous content operations.

Privacy Design:
- Content items are stored WITHOUT user_id (anonymous)
- User-content relationships are in the encrypted vault
- This router provides public content operations

Note: Most operations moved to vault.py (user-specific) or ingest.py (content creation).
This router handles content updates and relations.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.content import ContentItem, ItemRelation, RelationType, Topic
from app.models.user import User
from app.schemas import (
    ContentItemResponse,
    ContentItemUpdate,
    ContentItemWithRelationsResponse,
    ItemRelationResponse,
    RelatedItemResponse,
    TopicResponse,
)

router = APIRouter()


@router.get("/{item_id}", response_model=ContentItemResponse)
async def get_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single content item by ID.

    Content is anonymous - anyone can access content by its UUID.
    """
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


@router.patch("/{item_id}", response_model=ContentItemResponse)
async def update_item(
    item_id: uuid.UUID,
    update_data: ContentItemUpdate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a content item's title, summary, or topics.

    Note: Since content is anonymous, any authenticated user can update content.
    This is a design trade-off for privacy.
    """
    query = (
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.id == item_id)
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Update title if provided
    if update_data.title is not None:
        item.title = update_data.title

    # Update summary if provided
    if update_data.summary is not None:
        item.summary = update_data.summary

    # Update topics if provided
    if update_data.topic_ids is not None:
        topics_query = select(Topic).where(Topic.id.in_(update_data.topic_ids))
        topics_result = await db.execute(topics_query)
        topics = topics_result.scalars().all()

        if len(topics) != len(update_data.topic_ids):
            raise HTTPException(status_code=400, detail="One or more topic IDs not found")

        item.topics = list(topics)

    await db.commit()
    await db.refresh(item)

    return item


@router.get("/{item_id}/relations", response_model=ContentItemWithRelationsResponse)
async def get_item_with_relations(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a content item with all its related items.

    Relations are public - they connect anonymous content items.
    """
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
        related_items.append(
            RelatedItemResponse(
                id=target.id,
                title=target.title,
                source=target.source,
                relation_type=rel.relation_type,
                confidence=rel.confidence,
            )
        )

    # Add incoming relations (reverse direction)
    for rel in incoming_relations:
        source = rel.source_item
        related_items.append(
            RelatedItemResponse(
                id=source.id,
                title=source.title,
                source=source.source,
                relation_type=rel.relation_type,
                confidence=rel.confidence,
            )
        )

    # Find items with shared topics (implicit relations)
    if item.topics:
        topic_ids = [t.id for t in item.topics]
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
                shared_topic_count = len(set(t.id for t in shared_item.topics) & set(topic_ids))
                confidence = min(0.3 + (shared_topic_count * 0.2), 0.9)

                related_items.append(
                    RelatedItemResponse(
                        id=shared_item.id,
                        title=shared_item.title,
                        source=shared_item.source,
                        relation_type=RelationType.RELATED,
                        confidence=confidence,
                    )
                )

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
        processed_at=item.processed_at,
        topics=[TopicResponse.model_validate(t) for t in item.topics],
        related_items=related_items,
    )


@router.post("/{item_id}/relations/{target_id}", response_model=ItemRelationResponse)
async def create_relation(
    item_id: uuid.UUID,
    target_id: uuid.UUID,
    relation_type: RelationType = RelationType.RELATED,
    confidence: float = Query(1.0, ge=0.0, le=1.0),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a relation between two content items.

    Since content is anonymous, any authenticated user can create relations.
    """
    # Verify both items exist
    source_result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
    target_result = await db.execute(select(ContentItem).where(ContentItem.id == target_id))

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
    item_id: uuid.UUID,
    target_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a relation between two content items.
    """
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
