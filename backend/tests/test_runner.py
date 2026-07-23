# backend/tests/test_runner.py
from unittest.mock import MagicMock

from app.db import SessionLocal
from app.models import PipelineRun, Recommendation, Repo, Snapshot, StageRun
from app.pipeline.base import PipelineContext, Stage
from app.pipeline.runner import PipelineRunner


class _BoomStage(Stage):
    name = "boom"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        raise RuntimeError("simulated failure")


class _SetsNormalizedStage(Stage):
    name = "sets_normalized"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.normalized = {"stars": 5, "forks": 1, "watchers": 5, "open_issues": 0, "views_14d": 0, "unique_views_14d": 0, "clones_14d": 0, "unique_clones_14d": 0}
        ctx.recommendations = [{"category": "x", "title": "t", "body": "b", "validated": True}]
        return ctx


class _DBIntegrityErrorStage(Stage):
    """Simulates a stage (like Preprocessor/Assembler) that shares the runner's
    db_session and hits a genuine DB-level constraint violation on commit."""

    name = "db_boom"

    def __init__(self, db_session):
        self.db = db_session

    def run(self, ctx: PipelineContext) -> PipelineContext:
        # category is a NOT NULL column on Recommendation (see app/models.py) -
        # inserting None and committing raises sqlalchemy.exc.IntegrityError
        # and leaves the shared session in a "pending rollback" state.
        self.db.add(Recommendation(user_id=ctx.repo.user_id, repo_id=ctx.repo.id, category=None, title="bad", body="b"))
        self.db.commit()
        return ctx


class _MarksContinuedStage(Stage):
    name = "marks_continued"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.raw["continued_after_db_failure"] = True
        return ctx


def _db(user_id):
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return db, repo


def test_runner_persists_run_and_stage_rows_even_on_stage_failure(seed_user):
    db, repo = _db(seed_user)
    from app.pipeline.assembler import Assembler
    runner = PipelineRunner(stages=[_BoomStage(), _SetsNormalizedStage(), Assembler(db_session=db)], db_session=db)

    ctx = runner.run_for_repo(repo)

    assert ctx.errors  # boom stage recorded an error, run continued
    run_row = db.query(PipelineRun).first()
    assert run_row.status == "degraded"
    stage_rows = db.query(StageRun).filter_by(pipeline_run_id=run_row.id).all()
    assert {s.stage_name for s in stage_rows} == {"boom", "sets_normalized", "assembler"}
    boom_row = next(s for s in stage_rows if s.stage_name == "boom")
    assert boom_row.status == "error"
    assert "simulated failure" in boom_row.error

    snapshot = db.query(Snapshot).filter_by(repo_id=repo.id).first()
    assert snapshot.stars == 5

    rec = db.query(Recommendation).filter_by(repo_id=repo.id).first()
    assert rec.title == "t"
    db.close()


def test_runner_rolls_back_shared_session_after_stage_db_integrity_error(seed_user):
    db, repo = _db(seed_user)
    runner = PipelineRunner(
        stages=[_DBIntegrityErrorStage(db), _MarksContinuedStage()],
        db_session=db,
    )

    # Must not raise (in particular, not sqlalchemy.exc.PendingRollbackError)
    ctx = runner.run_for_repo(repo)

    run_row = db.query(PipelineRun).first()
    assert run_row.status == "degraded"
    assert run_row.finished_at is not None

    stage_rows = db.query(StageRun).filter_by(pipeline_run_id=run_row.id).all()
    assert {s.stage_name for s in stage_rows} == {"db_boom", "marks_continued"}
    boom_row = next(s for s in stage_rows if s.stage_name == "db_boom")
    assert boom_row.status == "error"

    # Prove the pipeline truly continued past the DB failure.
    assert ctx.raw.get("continued_after_db_failure") is True
    marks_row = next(s for s in stage_rows if s.stage_name == "marks_continued")
    assert marks_row.status == "ok"

    db.close()


class _RecordsRepoStage(Stage):
    name = "records_repo"

    def run(self, ctx):
        ctx.raw["saw_repo_id"] = ctx.repo.id
        return ctx


def test_runner_defaults_to_analytics_pipeline_kind(seed_user):
    db, repo = _db(seed_user)
    runner = PipelineRunner(stages=[_RecordsRepoStage()], db_session=db)
    runner.run_for_repo(repo)

    run_row = db.query(PipelineRun).first()
    assert run_row.pipeline_kind == "analytics"
    db.close()


def test_runner_uses_custom_context_factory_and_pipeline_kind(seed_user):
    db, repo = _db(seed_user)

    class _FakeCtx:
        def __init__(self, repo):
            self.repo = repo
            self.raw = {}
            self.errors = []

    runner = PipelineRunner(
        stages=[_RecordsRepoStage()],
        db_session=db,
        context_factory=_FakeCtx,
        pipeline_kind="content",
    )
    ctx = runner.run_for_repo(repo)

    assert ctx.raw["saw_repo_id"] == repo.id
    run_row = db.query(PipelineRun).first()
    assert run_row.pipeline_kind == "content"
    db.close()
