"""Privacy-focused schema migration.

Revision ID: 001_privacy
Revises:
Create Date: 2026-01-11

This migration implements the privacy-focused architecture:
- ContentItem: Remove user relationship, add UUID id, url_hash, ref_count
- User: Add vault encryption support and recovery codes
- UserVaultEntry: New table for encrypted user-content references

WARNING: This migration drops and recreates content_items with a new schema.
         Existing content data will be lost!
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_privacy"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade to privacy-focused schema."""

    # =========================================================================
    # STEP 1: Drop dependent tables and content_items
    # =========================================================================

    # Drop content_topics (depends on content_items)
    op.drop_table("content_topics")

    # Drop item_relations (depends on content_items)
    op.drop_table("item_relations")

    # Drop old content_items table
    op.drop_table("content_items")

    # =========================================================================
    # STEP 2: Recreate content_items with UUID and new columns
    # =========================================================================

    # Use existing enum types (don't recreate)
    contenttype = postgresql.ENUM("link", "newsletter", "pdf", "note", name="contenttype", create_type=False)
    processingstatus = postgresql.ENUM("pending", "processing", "completed", "failed", name="processingstatus", create_type=False)

    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_type", contenttype, nullable=False),
        sa.Column("status", processingstatus, nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("url_hash", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("ref_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for content_items
    op.create_index("ix_content_items_url_hash", "content_items", ["url_hash"], unique=True)
    op.create_index("ix_content_items_ref_count", "content_items", ["ref_count"], unique=False)

    # =========================================================================
    # STEP 3: Recreate content_topics with UUID foreign key
    # =========================================================================

    op.create_table(
        "content_topics",
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id", "topic_id"),
    )

    # =========================================================================
    # STEP 4: Recreate item_relations with UUID foreign keys
    # =========================================================================

    # Use existing enum type for relation_type
    relationtype = postgresql.ENUM(
        "related", "extends", "contradicts", "similar", "references",
        name="relationtype", create_type=False
    )

    op.create_table(
        "item_relations",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation_type", relationtype, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["source_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_item_relations_source_id", "item_relations", ["source_id"])
    op.create_index("ix_item_relations_target_id", "item_relations", ["target_id"])

    # =========================================================================
    # STEP 5: Update users table
    # =========================================================================

    # Add new columns
    op.add_column(
        "users",
        sa.Column("vault_key_salt", sa.String(length=44), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("recovery_codes_hash", postgresql.ARRAY(sa.String(length=255)), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("recovery_codes_used", postgresql.ARRAY(sa.Boolean()), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("daily_submission_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column(
            "last_submission_reset",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("vault_entry_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # Remove old columns
    op.drop_column("users", "updated_at")

    # =========================================================================
    # STEP 6: Create user_vault_entries table
    # =========================================================================

    op.create_table(
        "user_vault_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_data", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("topic_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "content_hash", name="uq_user_content"),
    )

    op.create_index("ix_user_vault_entries_user_id", "user_vault_entries", ["user_id"])
    op.create_index("ix_user_vault_entries_created_at", "user_vault_entries", ["created_at"])

    # GIN index for topic_ids array (efficient containment queries)
    op.execute(
        "CREATE INDEX ix_user_vault_entries_topic_ids ON user_vault_entries USING GIN (topic_ids)"
    )


def downgrade() -> None:
    """Downgrade from privacy-focused schema (destructive!)."""

    # Drop new tables
    op.drop_index("ix_user_vault_entries_topic_ids", table_name="user_vault_entries")
    op.drop_index("ix_user_vault_entries_created_at", table_name="user_vault_entries")
    op.drop_index("ix_user_vault_entries_user_id", table_name="user_vault_entries")
    op.drop_table("user_vault_entries")

    # Restore users table
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.drop_column("users", "vault_entry_count")
    op.drop_column("users", "last_submission_reset")
    op.drop_column("users", "daily_submission_count")
    op.drop_column("users", "recovery_codes_used")
    op.drop_column("users", "recovery_codes_hash")
    op.drop_column("users", "vault_key_salt")

    # Drop new content tables
    op.drop_index("ix_item_relations_target_id", table_name="item_relations")
    op.drop_index("ix_item_relations_source_id", table_name="item_relations")
    op.drop_table("item_relations")
    op.drop_table("content_topics")
    op.drop_index("ix_content_items_ref_count", table_name="content_items")
    op.drop_index("ix_content_items_url_hash", table_name="content_items")
    op.drop_table("content_items")

    # Recreate old content_items (INTEGER id)
    op.create_table(
        "content_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content_type", sa.Enum("link", "newsletter", "pdf", "note", name="contenttype"), nullable=False),
        sa.Column("status", sa.Enum("pending", "processing", "completed", "failed", name="processingstatus"), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Recreate old content_topics
    op.create_table(
        "content_topics",
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("content_id", "topic_id"),
    )

    # Recreate old item_relations
    op.create_table(
        "item_relations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.Enum("related", "extends", "contradicts", "similar", "references", name="relationtype"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_relations_source_id", "item_relations", ["source_id"])
    op.create_index("ix_item_relations_target_id", "item_relations", ["target_id"])
