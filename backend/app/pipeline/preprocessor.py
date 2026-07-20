from datetime import date, timezone, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Snapshot
from app.pipeline.base import PipelineContext, Stage


class Preprocessor(Stage):
    name = "preprocessor"

    def __init__(self, db_session: Session):
        self.db = db_session

    def run(self, ctx: PipelineContext) -> PipelineContext:
        repo_data = ctx.raw["repo"]
        stars = repo_data.get("stargazers_count", 0)
        forks = repo_data.get("forks_count", 0)
        watchers = repo_data.get("subscribers_count", 0)
        open_issues = repo_data.get("open_issues_count", 0)

        previous = (
            self.db.execute(
                select(Snapshot)
                .where(Snapshot.repo_id == ctx.repo.id)
                .order_by(Snapshot.date.desc())
            )
            .scalars()
            .first()
        )

        ctx.normalized = {
            "date": datetime.now(timezone.utc).date(),
            "stars": stars,
            "forks": forks,
            "watchers": watchers,
            "open_issues": open_issues,
            "stars_delta": stars - previous.stars if previous else 0,
            "forks_delta": forks - previous.forks if previous else 0,
            "views_14d": ctx.raw["traffic_views"].get("count", 0),
            "unique_views_14d": ctx.raw["traffic_views"].get("uniques", 0),
            "clones_14d": ctx.raw["traffic_clones"].get("count", 0),
            "unique_clones_14d": ctx.raw["traffic_clones"].get("uniques", 0),
            "referrers": ctx.raw["referrers"],
            "popular_paths": ctx.raw["popular_paths"],
            "benchmarks": ctx.raw["benchmarks"],
            "has_license": ctx.raw["has_license"],
            "has_contributing": ctx.raw["has_contributing"],
            "readme": ctx.raw["readme"],
            "topics": ctx.raw["topics"],
        }
        return ctx
