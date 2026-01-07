import asyncio
import logging
import sys
import traceback
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.content import ContentItem, ContentType, ProcessingStatus, Topic
from app.schemas import ContentItemResponse, IngestTextRequest, IngestURLRequest
from app.services.extractor import extract_from_url
from app.services.summarizer import extract_topics, generate_summary

# Configure logging to flush immediately
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

router = APIRouter()


async def _process_item_async(item_id: int, db_url: str):
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
                await db.commit()
                logger.info(f"Item {item_id}: processing COMPLETED successfully")

            except Exception as e:
                logger.error(f"Error processing item {item_id}: {e}")
                logger.error(traceback.format_exc())
                # Try to update status to FAILED
                try:
                    await db.rollback()
                    # Re-fetch item to ensure clean state
                    result = await db.execute(
                        select(ContentItem).where(ContentItem.id == item_id)
                    )
                    item = result.scalar_one_or_none()
                    if item:
                        item.status = ProcessingStatus.FAILED
                        await db.commit()
                        logger.info(f"Item {item_id}: status set to FAILED")
                except Exception as inner_e:
                    logger.error(f"Failed to update item {item_id} status to FAILED: {inner_e}")

    except Exception as e:
        logger.error(f"Fatal error in background task for item {item_id}: {e}")
        logger.error(traceback.format_exc())
    finally:
        await engine.dispose()
        logger.info(f"Item {item_id}: engine disposed")


def _handle_task_result(task: asyncio.Task, item_id: int):
    """Callback to handle task completion and log any exceptions."""
    try:
        exc = task.exception()
        if exc:
            logger.error(f"Background task for item {item_id} failed with exception: {exc}")
    except asyncio.CancelledError:
        logger.warning(f"Background task for item {item_id} was cancelled")
    except asyncio.InvalidStateError:
        pass  # Task not done yet


async def schedule_processing(item_id: int, db_url: str):
    """Schedule async processing in background."""
    task = asyncio.create_task(_process_item_async(item_id, db_url))
    task.add_done_callback(lambda t: _handle_task_result(t, item_id))
    logger.info(f"Scheduled background processing for item {item_id}")


@router.post("/url", response_model=ContentItemResponse)
async def ingest_url(
    request: IngestURLRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest content from a URL."""
    url = str(request.url)

    # Check if URL already exists
    existing_query = select(ContentItem).where(ContentItem.url == url)
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="URL already ingested")

    # Extract content
    try:
        extracted = await extract_from_url(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract content: {str(e)}")

    if not extracted["text"]:
        raise HTTPException(status_code=400, detail="Could not extract text from URL")

    # Create item
    item = ContentItem(
        content_type=ContentType.LINK,
        status=ProcessingStatus.PENDING,
        url=url,
        title=extracted["title"],
        source=extracted["source"],
        raw_text=extracted["text"],
    )

    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Load relationships for response
    query = (
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.id == item.id)
    )
    result = await db.execute(query)
    item = result.scalar_one()

    # Schedule background processing
    from app.config import settings

    await schedule_processing(item.id, settings.database_url)

    return item


@router.post("/text", response_model=ContentItemResponse)
async def ingest_text(
    request: IngestTextRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest raw text/note."""
    item = ContentItem(
        content_type=request.content_type,
        status=ProcessingStatus.PENDING,
        title=request.title,
        raw_text=request.text,
    )

    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Load relationships
    query = (
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.id == item.id)
    )
    result = await db.execute(query)
    item = result.scalar_one()

    # Schedule background processing
    from app.config import settings

    await schedule_processing(item.id, settings.database_url)

    return item


@router.post("/{item_id}/reprocess", response_model=ContentItemResponse)
async def reprocess_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger reprocessing of an item."""
    query = (
        select(ContentItem)
        .options(selectinload(ContentItem.topics))
        .where(ContentItem.id == item_id)
    )
    result = await db.execute(query)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.status = ProcessingStatus.PENDING
    await db.commit()

    from app.config import settings

    await schedule_processing(item.id, settings.database_url)

    return item
