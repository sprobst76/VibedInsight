"""Add enhanced fields to weekly_summaries table.

Revision ID: 003_enhanced_weekly_summary
Revises: 002_add_content_embeddings
Create Date: 2025-01-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003_enhanced_weekly_summary"
down_revision: Union[str, None] = "002_add_content_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
