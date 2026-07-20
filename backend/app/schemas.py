from datetime import datetime

from pydantic import BaseModel, HttpUrl

from app.models.content import ContentType, ProcessingStatus


# Topic schemas
class TopicBase(BaseModel):
    name: str


class TopicCreate(TopicBase):
    pass


class TopicResponse(TopicBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# Chat / RAG schemas
class ChatRequest(BaseModel):
    question: str
    top_k: int | None = None


class ChatSource(BaseModel):
    n: int
    id: str
    title: str
    url: str | None = None
    source: str | None = None
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    used_context: bool


# Ingest schemas
class IngestURLRequest(BaseModel):
    url: HttpUrl


class IngestTextRequest(BaseModel):
    title: str
    text: str
    content_type: ContentType = ContentType.NOTE


class ContentItemUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    topic_ids: list[int] | None = None


# Weekly Summary schemas
class TopicCluster(BaseModel):
    """A cluster of articles grouped by topic."""

    name: str
    article_count: int
    description: str


class WeeklySummaryResponse(BaseModel):
    id: int
    week_start: datetime
    week_end: datetime
    tldr: str | None
    summary: str | None
    key_insights: list[str]
    top_topics: list[str]
    topic_clusters: list[TopicCluster]
    connections: list[str]
    items_count: int
    items_processed: int
    created_at: datetime
    generated_at: datetime | None

    model_config = {"from_attributes": True}


class WeeklySummaryListResponse(BaseModel):
    id: int
    week_start: datetime
    week_end: datetime
    items_count: int
    items_processed: int
    has_summary: bool

    model_config = {"from_attributes": True}


# User item schemas (the shape the Flutter app works with)
class UserItemResponse(BaseModel):
    """Combines ContentItem data with the user's flags. Integer ID."""

    id: int
    content_type: ContentType
    status: ProcessingStatus
    url: str | None
    title: str | None
    source: str | None
    summary: str | None
    is_favorite: bool
    is_read: bool
    is_archived: bool
    rating: int = 0
    triage_score: float | None = None
    created_at: datetime
    updated_at: datetime | None
    processed_at: datetime | None
    topics: list[TopicResponse]

    model_config = {"from_attributes": True}


class ResurfaceResponse(BaseModel):
    """A resurfaced item to rediscover, or null when there is nothing to show."""

    item: UserItemResponse | None = None


class UserItemsListResponse(BaseModel):
    """Paginated list of user items."""

    items: list[UserItemResponse]
    total: int
    page: int
    page_size: int
    pages: int
