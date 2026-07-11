"""Add enhanced fields to weekly_summaries table.

Revision ID: 003_enhanced_weekly_summary
Revises: 002_add_content_embeddings
Create Date: 2025-01-15

"""

from collections.abc import Sequence

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

    # All additions use IF NOT EXISTS: legacy create_all-bootstrapped
    # databases already have these columns/indexes while being stamped at
    # an earlier revision.
    op.execute("ALTER TABLE weekly_summaries ADD COLUMN IF NOT EXISTS user_id INTEGER")
    op.execute("ALTER TABLE weekly_summaries ADD COLUMN IF NOT EXISTS tldr TEXT")
    op.execute("ALTER TABLE weekly_summaries ADD COLUMN IF NOT EXISTS topic_clusters TEXT")
    op.execute("ALTER TABLE weekly_summaries ADD COLUMN IF NOT EXISTS connections TEXT")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_weekly_summaries_user_id "
        "ON weekly_summaries (user_id)"
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_weekly_summaries_user_id'
            ) THEN
                ALTER TABLE weekly_summaries
                    ADD CONSTRAINT fk_weekly_summaries_user_id
                    FOREIGN KEY (user_id) REFERENCES users (id);
            END IF;
        END $$;
        """
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
