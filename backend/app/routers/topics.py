from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.content import Topic
from app.models.user import User
from app.schemas import TopicCreate, TopicResponse

router = APIRouter()


@router.get("", response_model=list[TopicResponse])
async def list_topics(
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all topics (shared across users)."""
    query = select(Topic).order_by(Topic.name)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=TopicResponse)
async def create_topic(
    topic: TopicCreate,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new topic (shared across users)."""
    # Check if topic already exists
    query = select(Topic).where(Topic.name == topic.name)
    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Topic already exists")

    db_topic = Topic(name=topic.name)
    db.add(db_topic)
    await db.commit()
    await db.refresh(db_topic)

    return db_topic


@router.delete("/{topic_id}")
async def delete_topic(
    topic_id: int,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a topic (shared across users)."""
    query = select(Topic).where(Topic.id == topic_id)
    result = await db.execute(query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    await db.delete(topic)
    await db.commit()

    return {"status": "deleted", "id": topic_id}
