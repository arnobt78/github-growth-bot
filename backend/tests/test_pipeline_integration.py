# backend/tests/test_pipeline_integration.py
"""
End-to-end integration test for the real 7-stage pipeline, wired the same way
`app.pipeline.jobs.build_stages` wires it. Unlike the other pipeline tests
(which exercise stages individually or via fake/partial stages), this test
constructs the actual Extractor/Preprocessor/Analyzer/Optimizer/Synthesizer/
Validator/Assembler classes and drives them through a real PipelineRunner, so
a future constructor-signature mismatch in build_stages would be caught here.
"""
from unittest.mock import MagicMock

from app.db import Base, SessionLocal, engine
from app.models import PipelineRun, Repo, Snapshot, StageRun
from app.pipeline.analyzer import Analyzer
from app.pipeline.assembler import Assembler
from app.pipeline.extractor import Extractor
from app.pipeline.optimizer import Optimizer
from app.pipeline.preprocessor import Preprocessor
from app.pipeline.runner import PipelineRunner
from app.pipeline.synthesizer import Synthesizer
from app.pipeline.validator import Validator


def _fake_gh_client():
    gh = MagicMock()
    gh.get_repo.return_value = {
        "stargazers_count": 110,
        "forks_count": 12,
        "watchers_count": 110,
        "subscribers_count": 22,
        "open_issues_count": 4,
        "description": "A tool",
        "topics": ["cli"],
        "language": "Python",
    }
    gh.get_traffic_views.return_value = {"count": 200, "uniques": 90}
    gh.get_traffic_clones.return_value = {"count": 30, "uniques": 15}
    gh.get_referrers.return_value = [{"referrer": "news.ycombinator.com", "count": 40, "uniques": 30}]
    gh.get_popular_paths.return_value = [{"path": "/", "count": 50, "uniques": 40}]
    gh.get_readme.return_value = "# My Repo"
    gh.has_file.return_value = False
    gh.search_similar_repos.return_value = [
        {"full_name": "other/repo", "stargazers_count": 500, "forks_count": 50, "topics": ["cli"]}
    ]
    return gh


def _fake_llm_router():
    llm = MagicMock()
    llm.chat_completion.return_value = '[{"title": "t", "body": "b", "category": "c"}]'
    return llm


def test_real_pipeline_runs_end_to_end_through_production_wiring():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()
    db.refresh(repo)

    gh_client = _fake_gh_client()
    llm_router = _fake_llm_router()

    # Constructed the same way app.pipeline.jobs.build_stages wires them, so a
    # future __init__ signature mismatch on any real stage would fail here.
    stages = [
        Extractor(gh_client=gh_client),
        Preprocessor(db_session=db),
        Analyzer(),
        Optimizer(),
        Synthesizer(llm_router=llm_router),
        Validator(),
        Assembler(db_session=db),
    ]
    runner = PipelineRunner(stages=stages, db_session=db)

    ctx = runner.run_for_repo(repo)  # must not raise

    assert ctx.errors == []

    snapshot = db.query(Snapshot).filter_by(repo_id=repo.id).first()
    assert snapshot is not None
    assert snapshot.stars == 110

    run_row = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    assert run_row is not None
    assert run_row.status in ("ok", "degraded")

    stage_rows = db.query(StageRun).filter_by(pipeline_run_id=run_row.id).all()
    assert len(stage_rows) == 7
    assert {s.stage_name for s in stage_rows} == {
        "extractor", "preprocessor", "analyzer", "optimizer", "synthesizer", "validator", "assembler",
    }

    db.close()
