"""
Content Ingestion Router - Anonymous content creation.

Privacy Design:
- Content is stored WITHOUT user_id (anonymous)
- url_hash enables deduplication across all users
- ref_count tracks how many users reference this content
- User-content mapping is handled by the vault (encrypted)
"""

import asyncio
import hashlib
import logging
import sys
import traceback
import uuid
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_dev_or_current_user
from app.models.content import ContentItem, ContentType, ProcessingStatus, Topic
from app.models.user import User, UserItem
from app.schemas import (
    ContentItemResponse,
    IngestContentResponse,
    IngestTextRequest,
    IngestURLRequest,
)
from app.services.extractor import extract_from_url
from app.services.summarizer import extract_topics, generate_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

router = APIRouter()


def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent hashing.

    - Lowercase the scheme and host
    - Remove trailing slashes
    - Remove common tracking parameters
    """
    parsed = urlparse(url)
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
    # Remove trailing slash unless it's the root
    if normalized.endswith("/") and len(parsed.path) > 1:
        normalized = normalized[:-1]
    return normalized


def hash_url(url: str) -> str:
    """Generate SHA256 hash of normalized URL."""
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()


async def _process_item_async(item_id: uuid.UUID, db_url: str):
    """Async background task to process a content item."""
    logger.info(f"Starting processing for item {item_id}")
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as db:
            # Get item with topics eagerly loaded
            query = (
                select(ContentItem)
                .options(selectinload(ContentItem.topics))
                .where(ContentItem.id == item_id)
            )
            result = await db.execute(query)
            item = result.scalar_one_or_none()

            if not item or not item.raw_text:
                logger.warning(f"Item {item_id} not found or has no text")
                return

            try:
                item.status = ProcessingStatus.PROCESSING
                await db.commit()
                logger.info(f"Item {item_id}: status set to PROCESSING")

                # Generate summary
                logger.info(f"Item {item_id}: generating summary...")
                summary = await generate_summary(item.raw_text)
                item.summary = summary
                logger.info(f"Item {item_id}: summary generated")

                # Extract topics
                logger.info(f"Item {item_id}: extracting topics...")
                existing_query = select(Topic.name)
                existing_result = await db.execute(existing_query)
                existing_topics = [t[0] for t in existing_result.all()]

                topic_names = await extract_topics(item.raw_text, existing_topics)
                logger.info(f"Item {item_id}: extracted topics: {topic_names}")

                # Get or create topics and add to item
                current_topic_ids = {t.id for t in item.topics}
                for topic_name in topic_names:
                    topic_query = select(Topic).where(Topic.name == topic_name)
                    topic_result = await db.execute(topic_query)
                    topic = topic_result.scalar_one_or_none()

                    if not topic:
                        topic = Topic(name=topic_name)
                        db.add(topic)
                        await db.flush()

                    if topic.id not in current_topic_ids:
                        item.topics.append(topic)
                        current_topic_ids.add(topic.id)

                item.status = ProcessingStatus.COMPLETED
                item.processed_at = datetime.utcnow()

                # Delete raw_text after processing (privacy: minimal data retention)
                item.raw_text = None

                await db.commit()
                logger.info(f"Item {item_id}: processing COMPLETED successfully")

            except Exception as e:
                logger.error(f"Error processing item {item_id}: {e}")
                logger.error(traceback.format_exc())
                try:
                    await db.rollback()
                    result = await db.execute(
                        select(ContentItem).where(ContentItem.id == item_id)
                    )
                    item = result.scalar_one_or_none()
                    if item:
                        item.status = ProcessingStatus.FAILED
                        await db.commit()
                        logger.info(f"Item {item_id}: status set to FAILED")
                except Exception as inner_e:
                    logger.error(f"Failed to update item {item_id} status: {inner_e}")

    except Exception as e:
        logger.error(f"Fatal error in background task for item {item_id}: {e}")
        logger.error(traceback.format_exc())
    finally:
        await engine.dispose()
        logger.info(f"Item {item_id}: engine disposed")


def _handle_task_result(task: asyncio.Task, item_id: uuid.UUID):
    """Callback to handle task completion and log any exceptions."""
    try:
        exc = task.exception()
        if exc:
            logger.error(f"Task for item {item_id} failed: {exc}")
    except asyncio.CancelledError:
        logger.warning(f"Task for item {item_id} was cancelled")
    except asyncio.InvalidStateError:
        pass


async def schedule_processing(item_id: uuid.UUID, db_url: str):
    """Schedule async processing in background."""
    task = asyncio.create_task(_process_item_async(item_id, db_url))
    task.add_done_callback(lambda t: _handle_task_result(t, item_id))
    logger.info(f"Scheduled background processing for item {item_id}")


@router.post("/url", response_model=IngestContentResponse)
async def ingest_url(
    request: IngestURLRequest,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest content from a URL.

    Returns content_id which the client should encrypt into their vault entry.

    Privacy:
    - Content is stored WITHOUT user_id (anonymous)
    - Deduplication via url_hash (if URL exists, ref_count is incremented)
    - User-content mapping is handled separately via encrypted vault
    """
    url = str(request.url)
    url_hash = hash_url(url)

    # Check if URL already exists (global deduplication)
    existing_query = select(ContentItem).where(ContentItem.url_hash == url_hash)
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Content exists - check if user already has it
        user_item_query = select(UserItem).where(
            UserItem.user_id == user.id,
            UserItem.content_id == existing.id,
        )
        user_item_result = await db.execute(user_item_query)
        existing_user_item = user_item_result.scalar_one_or_none()

        if existing_user_item:
            # User already has this content
            return IngestContentResponse(
                content_id=existing.id,
                title=existing.title,
                status=existing.status,
                is_duplicate=True,
            )

        # Create user_item entry for existing content
        existing.ref_count += 1
        user_item = UserItem(user_id=user.id, content_id=existing.id)
        db.add(user_item)
        await db.commit()

        return IngestContentResponse(
            content_id=existing.id,
            title=existing.title,
            status=existing.status,
            is_duplicate=True,
        )

    # Extract content from URL
    try:
        extracted = await extract_from_url(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract content: {e}")

    if not extracted["text"]:
        raise HTTPException(status_code=400, detail="Could not extract text from URL")

    # Create anonymous content item
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
    await db.flush()  # Get the item.id

    # Create user_item entry
    user_item = UserItem(user_id=user.id, content_id=item.id)
    db.add(user_item)

    await db.commit()
    await db.refresh(item)

    # Schedule background processing
    from app.config import settings

    await schedule_processing(item.id, settings.database_url)

    return IngestContentResponse(
        content_id=item.id,
        title=item.title,
        status=item.status,
        is_duplicate=False,
    )


@router.post("/text", response_model=IngestContentResponse)
async def ingest_text(
    request: IngestTextRequest,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest raw text/note.

    Returns content_id which the client should encrypt into their vault entry.

    Notes don't have URL deduplication - each note creates a new content item.
    """
    # Create anonymous content item (no url_hash for notes)
    item = ContentItem(
        content_type=request.content_type,
        status=ProcessingStatus.PENDING,
        title=request.title,
        raw_text=request.text,
        ref_count=1,
    )

    db.add(item)
    await db.flush()  # Get the item.id

    # Create user_item entry
    user_item = UserItem(user_id=user.id, content_id=item.id)
    db.add(user_item)

    await db.commit()
    await db.refresh(item)

    # Schedule background processing
    from app.config import settings

    await schedule_processing(item.id, settings.database_url)

    return IngestContentResponse(
        content_id=item.id,
        title=item.title,
        status=item.status,
        is_duplicate=False,
    )


@router.get("/{content_id}", response_model=ContentItemResponse)
async def get_content(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get content by ID.

    This endpoint is public - content is anonymous and can be accessed by anyone
    who knows the content_id (which is a UUID, so not guessable).
    """
    query = (
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.id == content_id)
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Content not found")

    return item


@router.post("/{content_id}/reprocess", response_model=ContentItemResponse)
async def reprocess_content(
    content_id: uuid.UUID,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger reprocessing of content.

    Note: Since content is anonymous, any authenticated user can trigger
    reprocessing. In production, you might want to add additional checks.
    """
    query = (
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.id == content_id)
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Content not found")

    if not item.raw_text:
        raise HTTPException(
            status_code=400,
            detail="Cannot reprocess: raw text was deleted after processing",
        )

    item.status = ProcessingStatus.PENDING
    await db.commit()

    from app.config import settings

    await schedule_processing(item.id, settings.database_url)

    return item


@router.delete("/{content_id}/decrement")
async def decrement_ref_count(
    content_id: uuid.UUID,
    user: User = Depends(get_dev_or_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Decrement the reference count for content.

    Call this when removing content from a user's vault.
    If ref_count reaches 0, the content becomes eligible for garbage collection.
    """
    result = await db.execute(
        select(ContentItem).where(ContentItem.id == content_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Content not found")

    item.ref_count = max(0, item.ref_count - 1)
    await db.commit()

    return {"content_id": content_id, "ref_count": item.ref_count}
