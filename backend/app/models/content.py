"""
Content models.

ContentItem stores the article/note itself (deduplicated via url_hash);
per-user flags live in UserItem. Embeddings are pgvector columns used for
semantic similarity (knowledge graph, related items).
"""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _enum_values(enum_cls):
    return [member.value for member in enum_cls]


class ContentType(enum.StrEnum):
    LINK = "link"
    NEWSLETTER = "newsletter"
    PDF = "pdf"
    NOTE = "note"


class ProcessingStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RelationType(enum.StrEnum):
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
    """Shared content storage; per-user flags live in UserItem."""

    __tablename__ = "content_items"

    # UUID primary key (not incremental, prevents enumeration)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # values_callable: store the lowercase enum VALUES in Postgres (matching
    # the Alembic migrations), not the uppercase member names
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, values_callable=_enum_values), default=ContentType.LINK
    )
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, values_callable=_enum_values), default=ProcessingStatus.PENDING
    )

    # URL deduplication
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    url_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )  # SHA256 of normalized URL

    # Content metadata
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reference counting for garbage collection
    ref_count: Mapped[int] = mapped_column(Integer, default=1, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    topics: Mapped[list[Topic]] = relationship(secondary=content_topics, back_populates="items")

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
    """Weekly summary of content items."""

    __tablename__ = "weekly_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    week_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    week_end: Mapped[datetime] = mapped_column(DateTime)

    # Summary content - enhanced with topic clustering
    tldr: Mapped[str | None] = mapped_column(Text, nullable=True)  # 1-2 sentence summary
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_insights: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    top_topics: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    topic_clusters: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    connections: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string

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
        Enum(RelationType, values_callable=_enum_values), default=RelationType.RELATED
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


class ContentEmbedding(Base):
    """
    Embeddings for semantic similarity search.

    Stored separately from ContentItem to keep the main table lean
    and allow for easy embedding model updates.
    """

    __tablename__ = "content_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # pgvector column; dimension must match the Ollama embedding model
    # (mxbai-embed-large = 1024). Changing models requires re-embedding.
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)

    # Model used to generate embedding (for versioning)
    model: Mapped[str] = mapped_column(String(100), default="mxbai-embed-large")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
