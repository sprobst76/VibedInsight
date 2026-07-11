"""Simplify to single-user: drop vault/auth tables and user auth columns.

Revision ID: 005_single_user
Revises: 004_rating
Create Date: 2026-07-11

The encrypted-vault / JWT-auth architecture (PRIVACY_DESIGN_FINAL.md) was
never wired to the app and has been removed from the codebase. The API is
now protected by a single API key. Users keep only id/email/created_at.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_single_user"
down_revision: str | Sequence[str] | None = "004_rating"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_COLUMNS_TO_DROP = [
    "password_hash",
    "vault_key_salt",
    "recovery_codes_hash",
    "recovery_codes_used",
    "daily_submission_count",
    "last_submission_reset",
    "vault_entry_count",
    "is_active",
    "last_login",
]


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_vault_entries CASCADE")
    op.execute("DROP TABLE IF EXISTS refresh_tokens CASCADE")
    op.execute("DROP INDEX IF EXISTS ix_users_is_active")
    for column in USER_COLUMNS_TO_DROP:
        op.execute(f"ALTER TABLE users DROP COLUMN IF EXISTS {column}")


def downgrade() -> None:
    raise NotImplementedError(
        "Single-user simplification is not reversible; restore from backup "
        "or re-create the auth schema from git history."
    )
