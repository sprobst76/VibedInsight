"""
FastAPI dependencies.

Single-user deployment: the whole API is protected by the X-API-Key
middleware (see app.main). Route handlers resolve the one and only user
via get_current_user, which creates it on first use.

The email stays "dev@vibedinsight.local" because existing databases have
their items attached to that user.
"""

import logging

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

OWNER_EMAIL = "dev@vibedinsight.local"


async def get_or_create_owner(db: AsyncSession) -> User:
    """Get or create the single owner user."""
    result = await db.execute(select(User).where(User.email == OWNER_EMAIL))
    user = result.scalar_one_or_none()

    if user:
        return user

    logger.info(f"Creating owner user: {OWNER_EMAIL}")
    user = User(email=OWNER_EMAIL)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    """Resolve the single owner user (API-key check happens in middleware)."""
    return await get_or_create_owner(db)
