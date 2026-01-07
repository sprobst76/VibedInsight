import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String, Table, Text
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
    RELATED = "related"         # Allgemein verwandt
    EXTENDS = "extends"         # Erweitert/vertieft
    CONTRADICTS = "contradicts" # Widerspricht
    SIMILAR = "similar"         # Ähnlicher Inhalt
    REFERENCES = "references"   # Referenziert/zitiert


# Association table for many-to-many relationship
content_topics = Table(
    "content_topics",
    Base.metadata,
    Column("content_id", ForeignKey("content_items.id", ondelete="CASCADE"), primary_key=True),
    Column("topic_id", ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    items: Mapped[list["ContentItem"]] = relationship(
        secondary=content_topics, back_populates="topics"
    )


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType), default=ContentType.LINK)
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), default=ProcessingStatus.PENDING
    )

    # Source information
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Domain or source name

    # Content
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
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


class ItemRelation(Base):
    """Pseudo-Graph: Beziehungen zwischen Content Items."""

    __tablename__ = "item_relations"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[RelationType] = mapped_column(Enum(RelationType), default=RelationType.RELATED)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 - 1.0
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    source_item: Mapped["ContentItem"] = relationship(
        "ContentItem", foreign_keys=[source_id], back_populates="outgoing_relations"
    )
    target_item: Mapped["ContentItem"] = relationship(
        "ContentItem", foreign_keys=[target_id], back_populates="incoming_relations"
    )
