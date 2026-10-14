"""add processing retry fields to content_items

Revision ID: 009_processing_retry
Revises: 008_triage_score
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009_processing_retry"
down_revision: str | Sequence[str] | None = "008_triage_score"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "content_items",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("content_items", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "content_items",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_content_items_next_retry_at", "content_items", ["next_retry_at"])


def downgrade() -> None:
    op.drop_index("ix_content_items_next_retry_at", table_name="content_items")
    op.drop_column("content_items", "next_retry_at")
    op.drop_column("content_items", "last_error")
    op.drop_column("content_items", "attempts")
