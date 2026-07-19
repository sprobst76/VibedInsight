"""
Content Ingestion Router.

Creates ContentItems (deduplicated by url_hash) plus the owner's UserItem
link, then schedules background processing (see app.services.processing).
"""

import hashlib
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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

logger = logging.getLogger(__name__)

router = APIRouter()


def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent hashing.

    - Lowercase the scheme and host
    - Remove trailing slashes
    """
    parsed = urlparse(url)
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
    if normalized.endswith("/") and len(parsed.path) > 1:
        normalized = normalized[:-1]
    return normalized


def hash_url(url: str) -> str:
    """Generate SHA256 hash of normalized URL."""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()


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
        user_item_result = await db.execute(
            select(UserItem).where(
                UserItem.user_id == user.id,
                UserItem.content_id == existing.id,
            )
        )
        existing_user_item = user_item_result.scalar_one_or_none()

        if existing_user_item:
            return await load_user_item_response(existing_user_item.id, db)

        existing.ref_count += 1
        user_item = UserItem(user_id=user.id, content_id=existing.id)
        db.add(user_item)
        await db.flush()
        user_item_id = user_item.id
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

    item = ContentItem(
        content_type=ContentType.LINK,
        status=ProcessingStatus.PENDING,
        url=url,
        url_hash=url_hash,
        title=extracted["title"],
        source=extracted["source"],
        raw_text=extracted["text"],
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
