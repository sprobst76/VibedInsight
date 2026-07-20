"""
KI-Triage — score items by similarity to the user's highly-rated items.

triage_score = max cosine similarity between an item's embedding and the
embeddings of the user's highly-rated items (rating >= triage_min_rating).
"Looks like something you loved." Null when the user has no highly-rated items
with embeddings yet.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.content import ContentEmbedding
from app.models.user import User, UserItem

logger = logging.getLogger(__name__)


async def _score_for_embedding(
    db: AsyncSession,
    user_id: int,
    exclude_content_id,
    embedding,
    min_rating: int,
) -> float | None:
    """Max similarity of `embedding` to the user's highly-rated items."""
    distance = ContentEmbedding.embedding.cosine_distance(embedding)
    stmt = (
        select(func.min(distance))
        .join(UserItem, UserItem.content_id == ContentEmbedding.content_id)
        .where(
            UserItem.user_id == user_id,
            UserItem.rating >= min_rating,
            ContentEmbedding.content_id != exclude_content_id,
        )
    )
    min_distance = await db.scalar(stmt)
    if min_distance is None:
        return None
    return round(1.0 - float(min_distance), 4)


async def update_triage_for_content(db: AsyncSession, content_id) -> None:
    """Recompute triage_score for every UserItem of a content (after ingest)."""
    embedding = await db.scalar(
        select(ContentEmbedding.embedding).where(
            ContentEmbedding.content_id == content_id
        )
    )
    if embedding is None:
        return

    user_items = (
        (await db.execute(select(UserItem).where(UserItem.content_id == content_id)))
        .scalars()
        .all()
    )
    for ui in user_items:
        ui.triage_score = await _score_for_embedding(
            db, ui.user_id, content_id, embedding, settings.triage_min_rating
        )
    await db.commit()


async def retriage_user(db: AsyncSession, user: User) -> int:
    """Recompute triage_score for all the user's items that have embeddings."""
    rows = (
        await db.execute(
            select(UserItem, ContentEmbedding.embedding).join(
                ContentEmbedding, ContentEmbedding.content_id == UserItem.content_id
            ).where(UserItem.user_id == user.id)
        )
    ).all()

    for ui, embedding in rows:
        ui.triage_score = await _score_for_embedding(
            db, user.id, ui.content_id, embedding, settings.triage_min_rating
        )
    await db.commit()
    return len(rows)
