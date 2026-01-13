"""
User model for authentication and encrypted vault.

Privacy Design:
- ContentItem has NO user_id - content is stored anonymously
- User-content mapping is stored encrypted in UserVaultEntry
- Only the user (with their password-derived key) can decrypt their vault
- Recovery codes allow account recovery without email (max security)

Security Features:
- Passwords are NEVER stored in plain text, only bcrypt hashes
- Vault key derived from password via PBKDF2 (100k iterations)
- Recovery codes are bcrypt hashed (like 2FA backup codes)
- Anti-flooding: daily submission limits and storage quotas
"""

from __future__ import annotations

import uuid as uuid_module
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """
    User account for authentication and vault access.

    IMPORTANT: Users do NOT have a direct relationship to ContentItem.
    The user-content mapping is stored encrypted in UserVaultEntry.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Vault encryption (salt for PBKDF2 key derivation)
    vault_key_salt: Mapped[str] = mapped_column(String(44))  # Base64 encoded 32 bytes

    # Recovery codes (hashed, like 2FA backup codes)
    # 10 codes in format XXXX-XXXX-XXXX, bcrypt hashed
    recovery_codes_hash: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)), nullable=True)
    recovery_codes_used: Mapped[list[bool] | None] = mapped_column(
        ARRAY(Boolean),
        nullable=True,
        default=lambda: [False] * 10,
    )

    # Anti-flooding: Rate limiting
    daily_submission_count: Mapped[int] = mapped_column(Integer, default=0)
    last_submission_reset: Mapped[date] = mapped_column(Date, default=date.today)

    # Anti-flooding: Storage quota
    vault_entry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    vault_entries: Mapped[list[UserVaultEntry]] = relationship(
        "UserVaultEntry", back_populates="user", cascade="all, delete-orphan"
    )
    items: Mapped[list[UserItem]] = relationship(
        "UserItem", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """
    Stored refresh tokens for secure logout/revocation.

    When a user logs out, we can invalidate their refresh token.
    This also allows us to revoke all sessions (e.g., "log out everywhere").
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Token metadata
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Optional: track device/client for "manage sessions" feature
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length

    # Revocation
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")


class UserVaultEntry(Base):
    """
    Encrypted user-content mapping.

    Privacy Design:
    - encrypted_data contains: content_id, is_favorite, is_read, is_archived, user_notes
    - Only the user can decrypt this (with their password-derived vault key)
    - topic_ids and created_at are unencrypted for filtering (acceptable trade-off)
    - content_hash prevents duplicate entries for the same content

    What an attacker with DB access sees:
    - User has X vault entries
    - Entries have certain topic IDs
    - But NOT which specific content items belong to the user
    """

    __tablename__ = "user_vault_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Encrypted payload (AES-256-GCM, client-side encrypted)
    # Contains: content_id, is_favorite, is_read, is_archived, user_notes, added_at
    encrypted_data: Mapped[str] = mapped_column(Text)

    # Unencrypted for filtering (privacy trade-off for usability)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    topic_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True, default=list)

    # Hash of content_id to prevent duplicates (not the ID itself!)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="vault_entries")

    # Unique constraint: one entry per content per user
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", name="uq_user_content"),
        # Note: GIN index for topic_ids array is created in migration
    )


class UserItem(Base):
    """
    User-Content junction table for backwards compatibility.

    This provides a simple user-content relationship with integer IDs
    that the existing Flutter frontend expects. It's a temporary solution
    until the full vault encryption is implemented in the client.

    Note: This is NOT encrypted - it's for development/transition only.
    In production, use UserVaultEntry with client-side encryption.
    """

    __tablename__ = "user_items"

    # Integer ID for frontend compatibility (not UUID)
    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_id: Mapped[uuid_module.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        index=True,
    )

    # User-specific flags
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="items")
    content: Mapped[ContentItem] = relationship("ContentItem")

    # Unique constraint: one entry per content per user
    __table_args__ = (UniqueConstraint("user_id", "content_id", name="uq_user_item_content"),)


if TYPE_CHECKING:
    from app.models.content import ContentItem
