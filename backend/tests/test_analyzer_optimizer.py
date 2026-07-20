from app.models import Repo
from app.pipeline.analyzer import Analyzer
from app.pipeline.base import PipelineContext
from app.pipeline.optimizer import Optimizer


def _ctx_with_normalized(**overrides) -> PipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = PipelineContext(repo=repo)
    ctx.normalized = {
        "stars": 110,
        "stars_delta": 10,
        "forks_delta": 2,
        "benchmarks": [{"full_name": "other/repo", "stargazers_count": 500, "forks_count": 50, "topics": ["cli"]}],
        "has_license": False,
        "has_contributing": False,
        "topics": [],
        "referrers": [{"referrer": "news.ycombinator.com", "count": 400, "uniques": 300}],
    }
    ctx.normalized.update(overrides)
    return ctx


def test_analyzer_flags_missing_license_and_topics():
    ctx = _ctx_with_normalized()
    ctx = Analyzer().run(ctx)

    categories = {f["category"] for f in ctx.findings}
    assert "missing_license" in categories
    assert "missing_topics" in categories
    assert "referrer_spike" in categories


def test_analyzer_percentile_vs_benchmarks():
    ctx = _ctx_with_normalized()
    ctx = Analyzer().run(ctx)
    percentile_finding = next(f for f in ctx.findings if f["category"] == "benchmark_gap")
    assert "500" in percentile_finding["message"]


def test_optimizer_ranks_and_caps_at_ten():
    ctx = _ctx_with_normalized()
    ctx = Analyzer().run(ctx)
    ctx = Optimizer().run(ctx)

    assert len(ctx.ranked_findings) <= 10
    impacts = [f["impact"] - f["effort"] for f in ctx.ranked_findings]
    assert impacts == sorted(impacts, reverse=True)
