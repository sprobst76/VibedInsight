"""add triage_score to user_items

Revision ID: 008_triage_score
Revises: 007_lowercase_enums
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_triage_score"
down_revision: str | Sequence[str] | None = "007_lowercase_enums"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_items", sa.Column("triage_score", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_items", "triage_score")
