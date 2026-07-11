"""Normalize enum labels to lowercase.

Revision ID: 007_lowercase_enums
Revises: 006_pgvector
Create Date: 2026-07-11

Databases bootstrapped by the old init_db()/create_all path got enum labels
from the Python member NAMES (uppercase: 'LINK', 'PENDING', ...), while the
Alembic chain creates lowercase labels ('link', 'pending', ...). The models
now always send lowercase values, so legacy labels are renamed here.
No-op on databases that already have lowercase labels.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_lowercase_enums"
down_revision: str | Sequence[str] | None = "006_pgvector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_LABELS = {
    "contenttype": ["link", "newsletter", "pdf", "note"],
    "processingstatus": ["pending", "processing", "completed", "failed"],
    "relationtype": ["related", "extends", "contradicts", "similar", "references"],
}


def upgrade() -> None:
    for enum_name, labels in ENUM_LABELS.items():
        for label in labels:
            upper = label.upper()
            op.execute(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_enum e
                        JOIN pg_type t ON t.oid = e.enumtypid
                        WHERE t.typname = '{enum_name}' AND e.enumlabel = '{upper}'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM pg_enum e
                        JOIN pg_type t ON t.oid = e.enumtypid
                        WHERE t.typname = '{enum_name}' AND e.enumlabel = '{label}'
                    ) THEN
                        ALTER TYPE {enum_name} RENAME VALUE '{upper}' TO '{label}';
                    END IF;
                END $$;
                """
            )


def downgrade() -> None:
    for enum_name, labels in ENUM_LABELS.items():
        for label in labels:
            upper = label.upper()
            op.execute(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_enum e
                        JOIN pg_type t ON t.oid = e.enumtypid
                        WHERE t.typname = '{enum_name}' AND e.enumlabel = '{label}'
                    ) THEN
                        ALTER TYPE {enum_name} RENAME VALUE '{label}' TO '{upper}';
                    END IF;
                END $$;
                """
            )
