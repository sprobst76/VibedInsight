"""
User models for the single-user deployment.

VibedInsight runs as a self-hosted, single-user service protected by an
API key (see app.main). The User table remains so existing data keeps its
owner and a future multi-user mode stays possible, but all auth machinery
(JWT, refresh tokens, encrypted vault) was removed — see git history and
PRIVACY_DESIGN_FINAL.md for the abandoned design.
"""

from __future__ import annotations

import uuid as uuid_module
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.timeutils import utcnow


class User(Base):
    """Owner of saved items. In practice there is exactly one row."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    items: Mapped[list[UserItem]] = relationship(
        "UserItem", back_populates="user", cascade="all, delete-orphan"
    )


class UserItem(Base):
    """
    User-Content junction: per-user flags and rating for a content item.

    Integer IDs because the Flutter frontend works with them.
    """

    __tablename__ = "user_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        index=True,
    )

    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, default=0)  # 0=unrated, 1-5=stars

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship("User", back_populates="items")
    content: Mapped[ContentItem] = relationship("ContentItem")

    __table_args__ = (UniqueConstraint("user_id", "content_id", name="uq_user_item_content"),)


if TYPE_CHECKING:
    from app.models.content import ContentItem
