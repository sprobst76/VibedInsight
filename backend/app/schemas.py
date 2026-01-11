import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl

from app.models.content import ContentType, ProcessingStatus, RelationType


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


class BulkItemsRequest(BaseModel):
    ids: list[uuid.UUID]


class BulkDeleteResponse(BaseModel):
    deleted_count: int
    deleted_ids: list[uuid.UUID]


class BulkReprocessResponse(BaseModel):
    reprocessed_count: int
    reprocessed_ids: list[uuid.UUID]


class ContentItemResponse(ContentItemBase):
    """
    Anonymous content response.

    Note: is_favorite, is_read, is_archived are NOT here - they're in the
    encrypted UserVaultEntry. The client decrypts them locally.
    """

    id: uuid.UUID
    content_type: ContentType
    status: ProcessingStatus
    source: str | None
    raw_text: str | None
    summary: str | None
    created_at: datetime
    processed_at: datetime | None
    topics: list[TopicResponse]

    model_config = {"from_attributes": True}


class ContentItemListResponse(BaseModel):
    """
    Lightweight content response for lists.

    Note: User-specific fields (favorite, read, archived) are in the vault.
    """

    id: uuid.UUID
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


# Item Relations (Knowledge Graph)
class RelatedItemResponse(BaseModel):
    """Ein verwandtes Item mit Beziehungsinfo."""

    id: uuid.UUID
    title: str | None
    source: str | None
    relation_type: RelationType
    confidence: float

    model_config = {"from_attributes": True}


class ItemRelationResponse(BaseModel):
    """Vollständige Beziehungsinformation."""

    id: int  # Relation ID is still int
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: RelationType
    confidence: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentItemWithRelationsResponse(ContentItemResponse):
    """Content Item mit verwandten Items."""
    related_items: list[RelatedItemResponse] = []


# Weekly Summary schemas
class WeeklySummaryResponse(BaseModel):
    id: int
    week_start: datetime
    week_end: datetime
    summary: str | None
    key_insights: list[str]  # Parsed from JSON
    top_topics: list[str]  # Parsed from JSON
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


# ============================================================================
# Authentication Schemas
# ============================================================================


class UserRegister(BaseModel):
    """Registration request - minimal data for privacy."""

    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 characters")


class UserLogin(BaseModel):
    """Login request."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User info response - never includes password."""

    id: int
    email: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Request to change password."""

    current_password: str
    new_password: str = Field(min_length=8, description="Minimum 8 characters")


class AccountDeleteRequest(BaseModel):
    """Request to delete account (GDPR compliance)."""

    password: str  # Require password confirmation for security
    confirm: bool = Field(description="Must be true to confirm deletion")


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


# ============================================================================
# Registration with Recovery Codes
# ============================================================================


class RegistrationResponse(BaseModel):
    """
    Registration response with recovery codes.

    IMPORTANT: recovery_codes are shown ONCE and never again!
    The user MUST save them securely.
    """

    user: UserResponse
    tokens: TokenResponse
    vault_key_salt: str  # Client uses this with password to derive vault key
    recovery_codes: list[str]  # 10 codes in format XXXX-XXXX-XXXX


class LoginResponse(BaseModel):
    """Login response with vault key salt."""

    user: UserResponse
    tokens: TokenResponse
    vault_key_salt: str  # Client needs this to derive vault key


# ============================================================================
# Recovery Codes
# ============================================================================


class RecoveryRequest(BaseModel):
    """Request to recover account with recovery code."""

    email: EmailStr
    recovery_code: str = Field(
        pattern=r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$",
        description="Recovery code in format XXXX-XXXX-XXXX",
    )
    new_password: str = Field(min_length=8)


class RecoveryResponse(BaseModel):
    """Response after successful recovery."""

    message: str
    vault_key_salt: str  # New salt for the new password
    # Note: encrypted_vault_key is returned if stored (for re-encryption)


# ============================================================================
# User Vault Schemas
# ============================================================================


class VaultEntryCreate(BaseModel):
    """
    Create a new vault entry.

    encrypted_data is created client-side using AES-256-GCM.
    It contains: content_id, is_favorite, is_read, is_archived, user_notes, added_at
    """

    encrypted_data: str  # Base64 encoded AES-256-GCM ciphertext
    topic_ids: list[int] = []  # For filtering (unencrypted trade-off)
    content_hash: str | None = None  # SHA256 of content_id to prevent duplicates


class VaultEntryResponse(BaseModel):
    """
    Vault entry response.

    Client decrypts encrypted_data locally to get content_id and user flags.
    """

    id: int
    encrypted_data: str
    created_at: datetime
    topic_ids: list[int]

    model_config = {"from_attributes": True}


class VaultEntryUpdate(BaseModel):
    """Update a vault entry (e.g., change favorite status)."""

    encrypted_data: str  # Client re-encrypts with updated data
    topic_ids: list[int] | None = None


# ============================================================================
# Content Ingestion (Anonymous)
# ============================================================================


class IngestContentResponse(BaseModel):
    """
    Response after ingesting content.

    Returns content_id which the client encrypts into their vault entry.
    """

    content_id: uuid.UUID
    title: str | None
    status: ProcessingStatus
    is_duplicate: bool = False  # True if content already existed (ref_count incremented)


# ============================================================================
# User Items (Backwards Compatibility)
# ============================================================================


class UserItemResponse(BaseModel):
    """
    User item response with integer ID for frontend compatibility.

    This combines ContentItem data with user-specific flags.
    """

    id: int  # UserItem.id (integer for frontend compatibility)
    content_type: ContentType
    status: ProcessingStatus
    url: str | None
    title: str | None
    source: str | None
    summary: str | None
    is_favorite: bool
    is_read: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime | None
    processed_at: datetime | None
    topics: list[TopicResponse]

    model_config = {"from_attributes": True}


class UserItemsListResponse(BaseModel):
    """Paginated list of user items."""

    items: list[UserItemResponse]
    total: int
    page: int
    page_size: int
    pages: int
