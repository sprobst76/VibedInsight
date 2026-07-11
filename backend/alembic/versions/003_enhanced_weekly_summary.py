"""Add enhanced fields to weekly_summaries table.

Revision ID: 003_enhanced_weekly_summary
Revises: 002_add_content_embeddings
Create Date: 2025-01-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_enhanced_weekly_summary"
down_revision: str | None = "002_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The base table historically came from init_db()/create_all and was
    # never created by a migration — create it here so the chain also works
    # on an empty database (pre-003 shape; the new columns are added below).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS weekly_summaries (
            id SERIAL PRIMARY KEY,
            week_start TIMESTAMP NOT NULL,
            week_end TIMESTAMP NOT NULL,
            summary TEXT,
            key_insights TEXT,
            top_topics TEXT,
            items_count INTEGER NOT NULL DEFAULT 0,
            items_processed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            generated_at TIMESTAMP
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_weekly_summaries_week_start "
        "ON weekly_summaries (week_start)"
    )

    # Add user_id column (nullable at first for existing rows)
    op.add_column(
        "weekly_summaries",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )

    # Add new summary fields
    op.add_column(
        "weekly_summaries",
        sa.Column("tldr", sa.Text(), nullable=True),
    )
    op.add_column(
        "weekly_summaries",
        sa.Column("topic_clusters", sa.Text(), nullable=True),
    )
    op.add_column(
        "weekly_summaries",
        sa.Column("connections", sa.Text(), nullable=True),
    )

    # Create index on user_id
    op.create_index(
        op.f("ix_weekly_summaries_user_id"),
        "weekly_summaries",
        ["user_id"],
        unique=False,
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_weekly_summaries_user_id",
        "weekly_summaries",
        "users",
        ["user_id"],
        ["id"],
    )


def downgrade() -> None:
    # Remove foreign key
    op.drop_constraint("fk_weekly_summaries_user_id", "weekly_summaries", type_="foreignkey")

    # Remove index
    op.drop_index(op.f("ix_weekly_summaries_user_id"), table_name="weekly_summaries")

    # Remove columns
    op.drop_column("weekly_summaries", "connections")
    op.drop_column("weekly_summaries", "topic_clusters")
    op.drop_column("weekly_summaries", "tldr")
    op.drop_column("weekly_summaries", "user_id")
