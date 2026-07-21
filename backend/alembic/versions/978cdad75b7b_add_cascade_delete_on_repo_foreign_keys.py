"""add cascade delete on repo foreign keys

Revision ID: 978cdad75b7b
Revises: fde87b33a416
Create Date: 2026-07-21 13:44:40.220122

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '978cdad75b7b'
down_revision: Union[str, None] = 'fde87b33a416'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DELETE /repos/{id} did a bare db.delete(repo) with no cascade, so it hit
    # IntegrityError on any repo with pipeline history. Add ON DELETE CASCADE
    # on every FK that points at repos/snapshots. stage_runs_pipeline_run_id_fkey
    # is intentionally untouched: PipelineRun/StageRun history is independent of
    # currently-tracked repos.
    op.drop_constraint('snapshots_repo_id_fkey', 'snapshots', type_='foreignkey')
    op.create_foreign_key(
        'snapshots_repo_id_fkey', 'snapshots', 'repos', ['repo_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('benchmark_repos_source_repo_id_fkey', 'benchmark_repos', type_='foreignkey')
    op.create_foreign_key(
        'benchmark_repos_source_repo_id_fkey', 'benchmark_repos', 'repos', ['source_repo_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('popular_paths_repo_id_fkey', 'popular_paths', type_='foreignkey')
    op.create_foreign_key(
        'popular_paths_repo_id_fkey', 'popular_paths', 'repos', ['repo_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('referrers_repo_id_fkey', 'referrers', type_='foreignkey')
    op.create_foreign_key(
        'referrers_repo_id_fkey', 'referrers', 'repos', ['repo_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('recommendations_repo_id_fkey', 'recommendations', type_='foreignkey')
    op.create_foreign_key(
        'recommendations_repo_id_fkey', 'recommendations', 'repos', ['repo_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('recommendations_snapshot_id_fkey', 'recommendations', type_='foreignkey')
    op.create_foreign_key(
        'recommendations_snapshot_id_fkey', 'recommendations', 'snapshots', ['snapshot_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('recommendations_snapshot_id_fkey', 'recommendations', type_='foreignkey')
    op.create_foreign_key(
        'recommendations_snapshot_id_fkey', 'recommendations', 'snapshots', ['snapshot_id'], ['id']
    )

    op.drop_constraint('recommendations_repo_id_fkey', 'recommendations', type_='foreignkey')
    op.create_foreign_key(
        'recommendations_repo_id_fkey', 'recommendations', 'repos', ['repo_id'], ['id']
    )

    op.drop_constraint('referrers_repo_id_fkey', 'referrers', type_='foreignkey')
    op.create_foreign_key(
        'referrers_repo_id_fkey', 'referrers', 'repos', ['repo_id'], ['id']
    )

    op.drop_constraint('popular_paths_repo_id_fkey', 'popular_paths', type_='foreignkey')
    op.create_foreign_key(
        'popular_paths_repo_id_fkey', 'popular_paths', 'repos', ['repo_id'], ['id']
    )

    op.drop_constraint('benchmark_repos_source_repo_id_fkey', 'benchmark_repos', type_='foreignkey')
    op.create_foreign_key(
        'benchmark_repos_source_repo_id_fkey', 'benchmark_repos', 'repos', ['source_repo_id'], ['id']
    )

    op.drop_constraint('snapshots_repo_id_fkey', 'snapshots', type_='foreignkey')
    op.create_foreign_key(
        'snapshots_repo_id_fkey', 'snapshots', 'repos', ['repo_id'], ['id']
    )
