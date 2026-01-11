"""
Content models for anonymous content storage.

Privacy Design:
- ContentItem has NO user_id - content is anonymous
- User-content mapping is in encrypted UserVaultEntry
- url_hash enables deduplication without exposing URLs
- ref_count tracks how many users reference this content
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ContentType(str, enum.Enum):
    LINK = "link"
    NEWSLETTER = "newsletter"
    PDF = "pdf"
    NOTE = "note"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RelationType(str, enum.Enum):
    RELATED = "related"
    EXTENDS = "extends"
    CONTRADICTS = "contradicts"
    SIMILAR = "similar"
    REFERENCES = "references"


# Association table for many-to-many relationship
content_topics = Table(
    "content_topics",
    Base.metadata,
    Column(
        "content_id",
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "topic_id",
        Integer,
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Topic(Base):
    """Global topics shared across all users."""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    items: Mapped[list["ContentItem"]] = relationship(
        secondary=content_topics, back_populates="topics"
    )


class ContentItem(Base):
    """
    Anonymous content storage.

    IMPORTANT: This table has NO user_id!
    User-content mapping is stored encrypted in user_vault_entries.
    """

    __tablename__ = "content_items"

    # UUID primary key (not incremental, prevents enumeration)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType), default=ContentType.LINK
    )
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), default=ProcessingStatus.PENDING
    )

    # URL deduplication
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    url_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )  # SHA256 of normalized URL

    # Content metadata
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Content (raw_text is deleted after processing!)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reference counting for garbage collection
    ref_count: Mapped[int] = mapped_column(Integer, default=1, index=True)

    # Timestamps (NO updated_at - would reveal access patterns)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    topics: Mapped[list[Topic]] = relationship(
        secondary=content_topics, back_populates="items"
    )

    # Graph relations (outgoing)
    outgoing_relations: Mapped[list["ItemRelation"]] = relationship(
        "ItemRelation",
        foreign_keys="ItemRelation.source_id",
        back_populates="source_item",
        cascade="all, delete-orphan",
    )

    # Graph relations (incoming)
    incoming_relations: Mapped[list["ItemRelation"]] = relationship(
        "ItemRelation",
        foreign_keys="ItemRelation.target_id",
        back_populates="target_item",
        cascade="all, delete-orphan",
    )


class WeeklySummary(Base):
    """
    Weekly summary of content items.

    Note: In the privacy-focused architecture, this is kept for backwards
    compatibility but may need redesign since content is now anonymous.
    """

    __tablename__ = "weekly_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    week_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    week_end: Mapped[datetime] = mapped_column(DateTime)

    # Summary content
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_insights: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    top_topics: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string

    # Stats
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    items_processed: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ItemRelation(Base):
    """Pseudo-Graph: Relations between content items."""

    __tablename__ = "item_relations"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        index=True,
    )
    relation_type: Mapped[RelationType] = mapped_column(
        Enum(RelationType), default=RelationType.RELATED
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    source_item: Mapped["ContentItem"] = relationship(
        "ContentItem", foreign_keys=[source_id], back_populates="outgoing_relations"
    )
    target_item: Mapped["ContentItem"] = relationship(
        "ContentItem", foreign_keys=[target_id], back_populates="incoming_relations"
    )
