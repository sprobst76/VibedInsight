"""Switch content_embeddings to pgvector.

Revision ID: 006_pgvector
Revises: 005_single_user
Create Date: 2026-07-11

Replaces the ARRAY(Float) embedding column with a pgvector vector(1024)
column (mxbai-embed-large). Existing embeddings are dropped — they are
cheap to regenerate via POST /admin/embeddings/generate-all, and old rows
may contain vectors from different models/dimensions anyway.

Requires the pgvector extension (bundled in the pgvector/pgvector Docker
images).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_pgvector"
down_revision: str | Sequence[str] | None = "005_single_user"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("DROP TABLE IF EXISTS content_embeddings CASCADE")

    op.create_table(
        "content_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("model", sa.String(100), nullable=False, server_default="mxbai-embed-large"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_content_embeddings_content_id",
        "content_embeddings",
        ["content_id"],
        unique=True,
    )

    # The postgres image changed from alpine (musl) to pgvector/pgvector
    # (glibc); rebuild text btree indexes since collation order may differ.
    for table in ("topics", "content_items", "users"):
        op.execute(f"REINDEX TABLE {table}")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS content_embeddings CASCADE")
