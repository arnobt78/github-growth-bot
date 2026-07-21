"""enforce user_id not null

Revision ID: 2d5539f16118
Revises: 9bb84cb18218
Create Date: 2026-07-22 00:21:32.472283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d5539f16118'
down_revision: Union[str, None] = '9bb84cb18218'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES_WITH_USER_ID = [
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
    # Run backend/scripts/backfill_owner_user.py against the target database
    # BEFORE applying this migration — it will fail with a NOT NULL violation
    # on any table that still has un-backfilled rows.
    for table in TABLES_WITH_USER_ID:
        op.alter_column(table, 'user_id', existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    for table in TABLES_WITH_USER_ID:
        op.alter_column(table, 'user_id', existing_type=sa.Integer(), nullable=True)
