"""
Serendipity resurfacing — pick an old, unread item to rediscover.

Weighted-random by age (older items are more likely), so the same item doesn't
resurface every time but forgotten older saves get a nudge.
"""

import logging
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.content import ContentItem, ProcessingStatus
from app.models.user import User, UserItem
from app.timeutils import utcnow

logger = logging.getLogger(__name__)

# Cap how many candidates we weight in Python.
_CANDIDATE_LIMIT = 50


async def pick_resurfacing_item(
    db: AsyncSession,
    user: User,
    min_age_days: int | None = None,
) -> UserItem | None:
    """Weighted-random old, unread, non-archived, completed item (or None)."""
    if not settings.resurfacing_enabled:
        return None

    min_age_days = (
        min_age_days if min_age_days is not None else settings.resurfacing_min_age_days
    )
    from datetime import timedelta

    cutoff = utcnow() - timedelta(days=min_age_days)

    query = (
        select(UserItem)
        .join(ContentItem, ContentItem.id == UserItem.content_id)
        .options(selectinload(UserItem.content).selectinload(ContentItem.topics))
        .where(
            UserItem.user_id == user.id,
            UserItem.is_read.is_(False),
            UserItem.is_archived.is_(False),
            UserItem.created_at <= cutoff,
            ContentItem.status == ProcessingStatus.COMPLETED,
        )
        .order_by(UserItem.created_at.asc())
        .limit(_CANDIDATE_LIMIT)
    )
    candidates = (await db.execute(query)).scalars().unique().all()
    if not candidates:
        return None

    now = utcnow()
    # Weight by age in days (at least 1 so nothing has zero probability).
    weights = [max(1, (now - item.created_at).days) for item in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]
