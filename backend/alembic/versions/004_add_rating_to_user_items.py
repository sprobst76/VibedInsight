"""add rating to user_items

Revision ID: 004_rating
Revises: 8a7e527e667f
Create Date: 2026-02-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_rating"
down_revision: Union[str, Sequence[str], None] = "003_enhanced_weekly_summary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add rating column to user_items (0=unrated, 1-5=stars)."""
    op.add_column(
        "user_items",
        sa.Column(
            "rating",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Remove rating column from user_items."""
    op.drop_column("user_items", "rating")
