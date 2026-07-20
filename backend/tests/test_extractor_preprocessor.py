from datetime import date
from unittest.mock import MagicMock

from app.db import Base, SessionLocal, engine
from app.models import Repo, Snapshot
from app.pipeline.base import PipelineContext
from app.pipeline.extractor import Extractor
from app.pipeline.preprocessor import Preprocessor


def _fake_gh_client():
    gh = MagicMock()
    gh.get_repo.return_value = {"stargazers_count": 110, "forks_count": 12, "watchers_count": 110, "subscribers_count": 22, "open_issues_count": 4, "description": "A tool", "topics": ["cli"], "language": "Python"}
    gh.get_traffic_views.return_value = {"count": 200, "uniques": 90}
    gh.get_traffic_clones.return_value = {"count": 30, "uniques": 15}
    gh.get_referrers.return_value = [{"referrer": "news.ycombinator.com", "count": 40, "uniques": 30}]
    gh.get_popular_paths.return_value = [{"path": "/", "count": 50, "uniques": 40}]
    gh.get_readme.return_value = "# My Repo"
    gh.has_file.return_value = False
    gh.search_similar_repos.return_value = [{"full_name": "other/repo", "stargazers_count": 500, "forks_count": 50, "topics": ["cli"]}]
    return gh


def test_extractor_populates_raw():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()
    db.refresh(repo)

    ctx = PipelineContext(repo=repo)
    extractor = Extractor(gh_client=_fake_gh_client())
    ctx = extractor.run(ctx)

    assert ctx.raw["repo"]["stargazers_count"] == 110
    assert ctx.raw["traffic_views"]["count"] == 200
    assert ctx.raw["benchmarks"][0]["full_name"] == "other/repo"
    assert ctx.raw["has_license"] is False
    db.close()


def test_preprocessor_diffs_against_previous_snapshot():
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()
    db.refresh(repo)
    db.add(Snapshot(repo_id=repo.id, date=date(2026, 7, 19), stars=100, forks=10, watchers=100, open_issues=5))
    db.commit()

    ctx = PipelineContext(repo=repo)
    ctx.raw = {
        "repo": {"stargazers_count": 110, "forks_count": 12, "watchers_count": 110, "subscribers_count": 22, "open_issues_count": 4},
        "traffic_views": {"count": 200, "uniques": 90},
        "traffic_clones": {"count": 30, "uniques": 15},
        "referrers": [{"referrer": "news.ycombinator.com", "count": 40, "uniques": 30}],
        "popular_paths": [{"path": "/", "count": 50, "uniques": 40}],
        "benchmarks": [{"full_name": "other/repo", "stargazers_count": 500, "forks_count": 50, "topics": ["cli"]}],
        "has_license": False,
        "has_contributing": False,
        "readme": "# My Repo",
        "topics": ["cli"],
    }

    preprocessor = Preprocessor(db_session=db)
    ctx = preprocessor.run(ctx)

    assert ctx.normalized["stars"] == 110
    assert ctx.normalized["stars_delta"] == 10
    assert ctx.normalized["forks_delta"] == 2
    # watchers must come from subscribers_count (the real subscriber count), not
    # watchers_count (which GitHub's API sets equal to stargazers_count).
    assert ctx.normalized["watchers"] == 22
    db.close()
