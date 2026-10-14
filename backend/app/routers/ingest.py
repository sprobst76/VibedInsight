"""
Content Ingestion Router.

Creates ContentItems (deduplicated by url_hash) plus the owner's UserItem
link, then schedules background processing (see app.services.processing).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.content import ContentItem, ContentType, ProcessingStatus
from app.models.user import User, UserItem
from app.schemas import (
    IngestTextRequest,
    IngestURLRequest,
    TopicResponse,
    UserItemResponse,
)
from app.services.extractor import PrivateAddressError, extract_from_url
from app.services.processing import schedule_processing
from app.services.urlnorm import hash_url
from app.timeutils import utcnow

logger = logging.getLogger(__name__)

router = APIRouter()


async def load_user_item_response(user_item_id: int, db: AsyncSession) -> UserItemResponse:
    """Load a UserItem with its content and topics, then build the response."""
    query = (
        select(UserItem)
        .options(selectinload(UserItem.content).selectinload(ContentItem.topics))
        .where(UserItem.id == user_item_id)
    )
    result = await db.execute(query)
    ui = result.scalar_one()
    content = ui.content
    return UserItemResponse(
        id=ui.id,
        content_type=content.content_type,
        status=content.status,
        url=content.url,
        title=content.title,
        source=content.source,
        summary=content.summary,
        is_favorite=ui.is_favorite,
        is_read=ui.is_read,
        is_archived=ui.is_archived,
        rating=ui.rating,
        created_at=ui.created_at,
        updated_at=ui.updated_at,
        processed_at=content.processed_at,
        topics=[TopicResponse.model_validate(t) for t in content.topics],
    )


async def _link_user_to_item(
    user: User, content_id: uuid.UUID, db: AsyncSession
) -> tuple[int, bool]:
    """Ensure the user has a UserItem for the content; returns (id, newly_linked)."""
    result = await db.execute(
        select(UserItem.id).where(UserItem.user_id == user.id, UserItem.content_id == content_id)
    )
    existing_id = result.scalar_one_or_none()
    if existing_id is not None:
        return existing_id, False

    # ON CONFLICT guards against a concurrent identical request for the same user
    inserted = await db.execute(
        pg_insert(UserItem)
        .values(user_id=user.id, content_id=content_id, created_at=utcnow(), updated_at=utcnow())
        .on_conflict_do_nothing(constraint="uq_user_item_content")
        .returning(UserItem.id)
    )
    new_id = inserted.scalar_one_or_none()
    if new_id is None:
        result = await db.execute(
            select(UserItem.id).where(
                UserItem.user_id == user.id, UserItem.content_id == content_id
            )
        )
        return result.scalar_one(), False

    await db.execute(
        update(ContentItem)
        .where(ContentItem.id == content_id)
        .values(ref_count=ContentItem.ref_count + 1)
    )
    return new_id, True


@router.post("/url", response_model=UserItemResponse)
async def ingest_url(
    request: IngestURLRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest content from a URL (deduplicated via url_hash)."""
    url = str(request.url)
    url_hash = hash_url(url)

    # Check if URL already exists
    existing_result = await db.execute(select(ContentItem).where(ContentItem.url_hash == url_hash))
    existing = existing_result.scalar_one_or_none()

    if existing:
        user_item_id, _ = await _link_user_to_item(user, existing.id, db)
        await db.commit()
        return await load_user_item_response(user_item_id, db)

    # Extract content from URL
    try:
        extracted = await extract_from_url(url)
    except PrivateAddressError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract content: {e}")

    if not extracted["text"]:
        raise HTTPException(status_code=400, detail="Could not extract text from URL")

    # INSERT .. ON CONFLICT DO NOTHING: a parallel identical request may have
    # created the item while we were fetching; then we link to theirs instead
    # of failing on the unique url_hash index.
    new_id = uuid.uuid4()
    inserted = await db.execute(
        pg_insert(ContentItem)
        .values(
            id=new_id,
            content_type=ContentType.LINK,
            status=ProcessingStatus.PENDING,
            url=url,
            url_hash=url_hash,
            title=extracted["title"],
            source=extracted["source"],
            raw_text=extracted["text"],
            ref_count=0,
            created_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["url_hash"])
        .returning(ContentItem.id)
    )
    created = inserted.scalar_one_or_none() is not None
    if created:
        content_id = new_id
    else:
        content_id = (
            await db.execute(select(ContentItem.id).where(ContentItem.url_hash == url_hash))
        ).scalar_one()

    user_item_id, _ = await _link_user_to_item(user, content_id, db)
    await db.commit()

    if created:
        schedule_processing(content_id)

    return await load_user_item_response(user_item_id, db)


@router.post("/text", response_model=UserItemResponse)
async def ingest_text(
    request: IngestTextRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest raw text/note. Notes are not deduplicated."""
    item = ContentItem(
        content_type=request.content_type,
        status=ProcessingStatus.PENDING,
        title=request.title,
        raw_text=request.text,
        ref_count=1,
    )

    db.add(item)
    await db.flush()

    user_item = UserItem(user_id=user.id, content_id=item.id)
    db.add(user_item)
    await db.flush()
    user_item_id = user_item.id

    await db.commit()

    schedule_processing(item.id)

    return await load_user_item_response(user_item_id, db)
