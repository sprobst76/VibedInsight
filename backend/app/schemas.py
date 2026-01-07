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


# Content Item schemas
class ContentItemBase(BaseModel):
    url: str | None = None
    title: str | None = None


class IngestURLRequest(BaseModel):
    url: HttpUrl


class IngestTextRequest(BaseModel):
    title: str
    text: str
    content_type: ContentType = ContentType.NOTE


class ContentItemCreate(ContentItemBase):
    content_type: ContentType = ContentType.LINK
    raw_text: str | None = None


class ContentItemUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    topic_ids: list[int] | None = None


class ContentItemResponse(ContentItemBase):
    id: int
    content_type: ContentType
    status: ProcessingStatus
    source: str | None
    raw_text: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    topics: list[TopicResponse]

    model_config = {"from_attributes": True}


class ContentItemListResponse(BaseModel):
    id: int
    content_type: ContentType
    status: ProcessingStatus
    url: str | None
    title: str | None
    source: str | None
    created_at: datetime
    topics: list[TopicResponse]

    model_config = {"from_attributes": True}


# Pagination
class PaginatedResponse(BaseModel):
    items: list[ContentItemListResponse]
    total: int
    page: int
    page_size: int
    pages: int
