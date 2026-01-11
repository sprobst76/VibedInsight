"""add user_items junction table

Revision ID: 8a7e527e667f
Revises: 001_privacy
Create Date: 2026-01-11 11:04:11.392293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a7e527e667f'
down_revision: Union[str, Sequence[str], None] = '001_privacy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('user_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content_id', sa.UUID(), nullable=False),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['content_id'], ['content_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'content_id', name='uq_user_item_content')
    )
    op.create_index('ix_user_items_content_id', 'user_items', ['content_id'], unique=False)
    op.create_index('ix_user_items_is_archived', 'user_items', ['is_archived'], unique=False)
    op.create_index('ix_user_items_is_favorite', 'user_items', ['is_favorite'], unique=False)
    op.create_index('ix_user_items_is_read', 'user_items', ['is_read'], unique=False)
    op.create_index('ix_user_items_user_id', 'user_items', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_user_items_user_id', table_name='user_items')
    op.drop_index('ix_user_items_is_read', table_name='user_items')
    op.drop_index('ix_user_items_is_favorite', table_name='user_items')
    op.drop_index('ix_user_items_is_archived', table_name='user_items')
    op.drop_index('ix_user_items_content_id', table_name='user_items')
    op.drop_table('user_items')
