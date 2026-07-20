# backend/tests/test_runner.py
from unittest.mock import MagicMock

from app.db import Base, SessionLocal, engine
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
        self.db.add(Recommendation(repo_id=ctx.repo.id, category=None, title="bad", body="b"))
        self.db.commit()
        return ctx


class _MarksContinuedStage(Stage):
    name = "marks_continued"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.raw["continued_after_db_failure"] = True
        return ctx


def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return db, repo


def test_runner_persists_run_and_stage_rows_even_on_stage_failure():
    db, repo = _db()
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


def test_runner_rolls_back_shared_session_after_stage_db_integrity_error():
    db, repo = _db()
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
