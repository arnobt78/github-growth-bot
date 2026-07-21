from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import BenchmarkRepo, PopularPath, Recommendation, Referrer, Snapshot
from app.pipeline.base import PipelineContext, Stage


class Assembler(Stage):
    name = "assembler"

    def __init__(self, db_session: Session):
        self.db = db_session

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.normalized:
            return ctx

        snapshot_date = datetime.now(timezone.utc).date()

        snapshot = Snapshot(
            user_id=ctx.repo.user_id,
            repo_id=ctx.repo.id,
            date=snapshot_date,
            stars=ctx.normalized.get("stars", 0),
            forks=ctx.normalized.get("forks", 0),
            watchers=ctx.normalized.get("watchers", 0),
            open_issues=ctx.normalized.get("open_issues", 0),
            views_14d=ctx.normalized.get("views_14d", 0),
            unique_views_14d=ctx.normalized.get("unique_views_14d", 0),
            clones_14d=ctx.normalized.get("clones_14d", 0),
            unique_clones_14d=ctx.normalized.get("unique_clones_14d", 0),
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        ctx.raw["snapshot_id"] = snapshot.id

        for benchmark in ctx.normalized.get("benchmarks", []):
            self.db.add(BenchmarkRepo(
                user_id=ctx.repo.user_id,
                source_repo_id=ctx.repo.id,
                full_name=benchmark.get("full_name", ""),
                stars=benchmark.get("stargazers_count", 0),
                forks=benchmark.get("forks_count", 0),
                topics=benchmark.get("topics", []),
            ))

        for referrer in ctx.normalized.get("referrers", []):
            self.db.add(Referrer(
                user_id=ctx.repo.user_id,
                repo_id=ctx.repo.id,
                date=snapshot_date,
                referrer=referrer.get("referrer", ""),
                count=referrer.get("count", 0),
                uniques=referrer.get("uniques", 0),
            ))

        for popular_path in ctx.normalized.get("popular_paths", []):
            self.db.add(PopularPath(
                user_id=ctx.repo.user_id,
                repo_id=ctx.repo.id,
                date=snapshot_date,
                path=popular_path.get("path", ""),
                count=popular_path.get("count", 0),
                uniques=popular_path.get("uniques", 0),
            ))

        for rec in ctx.recommendations:
            if not rec.get("validated", False):
                continue
            self.db.add(Recommendation(
                user_id=ctx.repo.user_id,
                repo_id=ctx.repo.id,
                snapshot_id=snapshot.id,
                category=rec.get("category", "general"),
                title=rec.get("title", ""),
                body=rec.get("body", ""),
                validated=True,
            ))
        self.db.commit()
        return ctx
