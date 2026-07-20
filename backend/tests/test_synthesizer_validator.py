import re
from unittest.mock import MagicMock

from app.models import Repo
from app.pipeline.base import PipelineContext
from app.pipeline.synthesizer import Synthesizer
from app.pipeline.validator import Validator


def _ctx_with_findings() -> PipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = PipelineContext(repo=repo)
    ctx.normalized = {"stars": 110, "stars_delta": 10}
    ctx.ranked_findings = [
        {"category": "missing_license", "message": "This repo has no LICENSE file.", "impact": 7, "effort": 1},
    ]
    return ctx


def test_synthesizer_produces_recommendations_from_llm():
    ctx = _ctx_with_findings()
    fake_llm = MagicMock()
    fake_llm.chat_completion.return_value = (
        '[{"title": "Add a LICENSE file", "body": "Your repo gained 10 stars but has no LICENSE file. Add one to encourage adoption.", "category": "missing_license"}]'
    )

    ctx = Synthesizer(llm_router=fake_llm).run(ctx)

    assert len(ctx.recommendations) == 1
    assert ctx.recommendations[0]["title"] == "Add a LICENSE file"
    assert "10 stars" in ctx.recommendations[0]["body"]


def test_synthesizer_degrades_gracefully_on_llm_exception():
    ctx = _ctx_with_findings()
    fake_llm = MagicMock()
    fake_llm.chat_completion.side_effect = RuntimeError("all providers failed")

    ctx = Synthesizer(llm_router=fake_llm).run(ctx)

    assert ctx.recommendations == []
    assert len(ctx.errors) == 1
    assert "synthesizer: LLM call failed" in ctx.errors[0]


def test_synthesizer_degrades_gracefully_on_non_list_json():
    ctx = _ctx_with_findings()
    fake_llm = MagicMock()
    fake_llm.chat_completion.return_value = '{"not": "a list"}'

    ctx = Synthesizer(llm_router=fake_llm).run(ctx)

    assert ctx.recommendations == []
    assert len(ctx.errors) == 1
    assert "synthesizer: LLM response was not a JSON list" in ctx.errors[0]


def test_validator_accepts_claims_backed_by_data():
    ctx = _ctx_with_findings()
    ctx.recommendations = [
        {"category": "missing_license", "title": "Add a LICENSE file", "body": "Your repo gained 10 stars but has no LICENSE file."}
    ]
    ctx = Validator().run(ctx)
    assert ctx.recommendations[0]["validated"] is True


def test_validator_rejects_fabricated_numbers():
    ctx = _ctx_with_findings()
    ctx.recommendations = [
        {"category": "missing_license", "title": "Add a LICENSE file", "body": "Your repo gained 9999 stars this week!"}
    ]
    ctx = Validator().run(ctx)
    assert ctx.recommendations[0]["validated"] is False
    assert len(ctx.errors) == 1
