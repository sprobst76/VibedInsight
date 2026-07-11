"""add rating to user_items

Revision ID: 004_rating
Revises: 003_enhanced_weekly_summary
Create Date: 2026-02-26

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_rating"
down_revision: str | Sequence[str] | None = "003_enhanced_weekly_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add rating column to user_items (0=unrated, 1-5=stars).

    IF NOT EXISTS: legacy deployments already got this column from the old
    init_db() ad-hoc ALTER while being stamped at an earlier revision.
    """
    op.execute(
        "ALTER TABLE user_items ADD COLUMN IF NOT EXISTS rating INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    """Remove rating column from user_items."""
    op.execute("ALTER TABLE user_items DROP COLUMN IF EXISTS rating")
