"""
Resurfacing router — "Wiederentdeckt": surface an old, unread item.

The app calls this on launch; there is no server push (single-user, self-hosted),
so the app turns the result into a banner + a local notification.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.routers.user_items import _build_user_item_response
from app.schemas import ResurfaceResponse
from app.services.resurfacing import pick_resurfacing_item

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=ResurfaceResponse)
async def resurface(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResurfaceResponse:
    """Return one old, unread item to rediscover (or null)."""
    item = await pick_resurfacing_item(db, user)
    if item is None:
        return ResurfaceResponse(item=None)
    return ResurfaceResponse(item=_build_user_item_response(item))
