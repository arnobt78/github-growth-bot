"""add users table and user_id fks

Revision ID: 9bb84cb18218
Revises: 978cdad75b7b
Create Date: 2026-07-22 00:20:44.627883

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bb84cb18218'
down_revision: Union[str, None] = '978cdad75b7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES_GAINING_USER_ID = [
    "repos",
    "snapshots",
    "benchmark_repos",
    "referrers",
    "popular_paths",
    "pipeline_runs",
    "stage_runs",
    "recommendations",
]


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('github_id', sa.String(length=64), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('avatar_url', sa.String(length=500), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('access_token_encrypted', sa.Text(), nullable=False),
        sa.Column('plan', sa.String(length=50), nullable=False, server_default='free'),
        sa.Column('max_tracked_repos', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_github_id', 'users', ['github_id'], unique=True)

    # Nullable for now — existing rows (if any, on a real deployed DB) have no
    # owning user yet. backend/scripts/backfill_owner_user.py assigns them to
    # one designated account; a follow-up migration then enforces NOT NULL.
    for table in TABLES_GAINING_USER_ID:
        op.add_column(table, sa.Column('user_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            f'{table}_user_id_fkey', table, 'users', ['user_id'], ['id'], ondelete='CASCADE'
        )


def downgrade() -> None:
    for table in TABLES_GAINING_USER_ID:
        op.drop_constraint(f'{table}_user_id_fkey', table, type_='foreignkey')
        op.drop_column(table, 'user_id')
    op.drop_index('ix_users_github_id', table_name='users')
    op.drop_table('users')
