"""One-time, manually-run script for the real deployed Postgres database only.

Run after: (1) migration 9bb84cb18218 (add users table and user_id fks) has
been applied, (2) the Product Owner has signed in once via the live app
(creating their User row through POST /users/upsert). This script assigns
every pre-existing row across the 8 tables in TABLES_GAINING_USER_ID to that
one account, so no history from before the multi-tenant migration is
orphaned or lost.

Usage: .venv/bin/python -m scripts.backfill_owner_user --github-id <id>
"""
import argparse

from app.db import SessionLocal
from app.models import (
    BenchmarkRepo,
    PipelineRun,
    PopularPath,
    Recommendation,
    Referrer,
    Repo,
    Snapshot,
    StageRun,
    User,
)

TABLES = [Repo, Snapshot, BenchmarkRepo, Referrer, PopularPath, PipelineRun, StageRun, Recommendation]


def backfill(github_id: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.github_id == github_id).one_or_none()
        if user is None:
            raise SystemExit(
                f"No User row with github_id={github_id!r} — sign in via the live app first."
            )

        for model in TABLES:
            updated = (
                db.query(model)
                .filter(model.user_id.is_(None))
                .update({"user_id": user.id}, synchronize_session=False)
            )
            print(f"{model.__tablename__}: backfilled {updated} row(s) to user_id={user.id}")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-id", required=True, help="GitHub numeric user id to assign orphaned rows to")
    args = parser.parse_args()
    backfill(args.github_id)
