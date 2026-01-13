"""
User Vault Router - Encrypted content references.

Privacy Design:
- Vault entries contain encrypted_data (AES-256-GCM, client-encrypted)
- Server CANNOT read the content references
- topic_ids and created_at are unencrypted for filtering (acceptable trade-off)
- Each entry references anonymous ContentItem via encrypted content_id
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User, UserVaultEntry
from app.schemas import (
    MessageResponse,
    VaultEntryCreate,
    VaultEntryResponse,
    VaultEntryUpdate,
)

router = APIRouter()

# Anti-flooding limits
MAX_DAILY_SUBMISSIONS = 50
MAX_VAULT_ENTRIES = 10000


async def check_rate_limit(user: User, db: AsyncSession) -> None:
    """Check if user has exceeded daily submission limit."""
    today = date.today()

    # Reset counter if new day
    if user.last_submission_reset != today:
        user.daily_submission_count = 0
        user.last_submission_reset = today

    if user.daily_submission_count >= MAX_DAILY_SUBMISSIONS:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit of {MAX_DAILY_SUBMISSIONS} submissions reached.",
        )


async def check_storage_quota(user: User) -> None:
    """Check if user has exceeded storage quota."""
    if user.vault_entry_count >= MAX_VAULT_ENTRIES:
        raise HTTPException(
            status_code=402,
            detail=f"Storage quota of {MAX_VAULT_ENTRIES} entries exceeded.",
        )


@router.post("", response_model=VaultEntryResponse)
async def create_vault_entry(
    entry: VaultEntryCreate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new vault entry.

    The encrypted_data is created client-side and contains:
    - content_id: UUID of the anonymous ContentItem
    - is_favorite, is_read, is_archived: User flags
    - user_notes: Optional notes
    - added_at: Timestamp

    The server cannot read this data.
    """
    # Check rate limits
    await check_rate_limit(user, db)
    await check_storage_quota(user)

    # Check for duplicate (same content_hash for this user)
    if entry.content_hash:
        existing = await db.execute(
            select(UserVaultEntry).where(
                UserVaultEntry.user_id == user.id,
                UserVaultEntry.content_hash == entry.content_hash,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="Content already in vault",
            )

    # Create entry
    vault_entry = UserVaultEntry(
        user_id=user.id,
        encrypted_data=entry.encrypted_data,
        topic_ids=entry.topic_ids,
        content_hash=entry.content_hash,
    )

    db.add(vault_entry)

    # Update counters
    user.daily_submission_count += 1
    user.vault_entry_count += 1

    await db.commit()
    await db.refresh(vault_entry)

    return vault_entry


@router.get("", response_model=list[VaultEntryResponse])
async def list_vault_entries(
    topic_id: int | None = Query(None, description="Filter by topic ID"),
    from_date: date | None = Query(None, description="Filter entries from this date"),
    to_date: date | None = Query(None, description="Filter entries until this date"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all vault entries for the current user.

    Filtering is possible by:
    - topic_id: Entries that have this topic
    - from_date/to_date: Date range

    Note: The content_id and user flags are encrypted.
    Client must decrypt locally.
    """
    query = select(UserVaultEntry).where(UserVaultEntry.user_id == user.id)

    # Topic filter (using PostgreSQL array containment)
    if topic_id is not None:
        query = query.where(UserVaultEntry.topic_ids.contains([topic_id]))

    # Date filters
    if from_date:
        query = query.where(func.date(UserVaultEntry.created_at) >= from_date)
    if to_date:
        query = query.where(func.date(UserVaultEntry.created_at) <= to_date)

    # Order by created_at DESC (newest first)
    query = query.order_by(UserVaultEntry.created_at.desc())

    # Pagination
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    entries = result.scalars().all()

    return entries


@router.get("/count")
async def count_vault_entries(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the count of vault entries for the current user."""
    count = await db.scalar(select(func.count()).where(UserVaultEntry.user_id == user.id))
    return {
        "count": count or 0,
        "limit": MAX_VAULT_ENTRIES,
        "daily_used": user.daily_submission_count,
        "daily_limit": MAX_DAILY_SUBMISSIONS,
    }


@router.get("/{entry_id}", response_model=VaultEntryResponse)
async def get_vault_entry(
    entry_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single vault entry by ID."""
    result = await db.execute(
        select(UserVaultEntry).where(
            UserVaultEntry.id == entry_id,
            UserVaultEntry.user_id == user.id,
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Vault entry not found")

    return entry


@router.patch("/{entry_id}", response_model=VaultEntryResponse)
async def update_vault_entry(
    entry_id: int,
    update: VaultEntryUpdate,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a vault entry.

    Client re-encrypts the data with updated values and sends new encrypted_data.
    """
    result = await db.execute(
        select(UserVaultEntry).where(
            UserVaultEntry.id == entry_id,
            UserVaultEntry.user_id == user.id,
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Vault entry not found")

    # Update fields
    entry.encrypted_data = update.encrypted_data
    if update.topic_ids is not None:
        entry.topic_ids = update.topic_ids

    await db.commit()
    await db.refresh(entry)

    return entry


@router.delete("/{entry_id}", response_model=MessageResponse)
async def delete_vault_entry(
    entry_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a vault entry.

    Note: This should also decrement the ref_count on the associated ContentItem.
    However, since content_id is encrypted, the client must send a separate request
    to decrement the ref_count (or we implement a cleanup job).
    """
    result = await db.execute(
        select(UserVaultEntry).where(
            UserVaultEntry.id == entry_id,
            UserVaultEntry.user_id == user.id,
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Vault entry not found")

    await db.delete(entry)

    # Update counter
    user.vault_entry_count = max(0, user.vault_entry_count - 1)

    await db.commit()

    return MessageResponse(message="Vault entry deleted")


@router.delete("", response_model=MessageResponse)
async def delete_all_vault_entries(
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete ALL vault entries for the current user.

    This is a destructive operation and requires confirmation.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to delete all entries",
        )

    # Delete all entries
    result = await db.execute(select(UserVaultEntry).where(UserVaultEntry.user_id == user.id))
    entries = result.scalars().all()

    for entry in entries:
        await db.delete(entry)

    # Reset counter
    user.vault_entry_count = 0

    await db.commit()

    return MessageResponse(message=f"Deleted {len(entries)} vault entries")
