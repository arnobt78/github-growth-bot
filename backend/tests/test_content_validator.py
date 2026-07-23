from unittest.mock import MagicMock

from app.models import Repo
from app.pipeline.content.validator import ContentValidator
from app.pipeline.content_base import ContentPipelineContext, ContentTask


def _ctx_with_task(task: ContentTask, raw: dict | None = None) -> ContentPipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.raw = raw or {}
    ctx.tasks = [task]
    return ctx


def test_validator_skips_task_with_no_candidates():
    task = ContentTask(kind="readme_suggestion", target="readme", structured=False, current=None, source_material={})
    ctx = _ctx_with_task(task)
    llm = MagicMock()

    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].valid is False
    llm.chat_completion.assert_not_called()


def test_validator_single_candidate_skips_judge_call():
    task = ContentTask(kind="readme_suggestion", target="readme", structured=False, current=None, source_material={}, candidates=["# Good README"])
    ctx = _ctx_with_task(task, raw={"stars": 5})

    llm = MagicMock()
    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].winner == "# Good README"
    assert ctx.tasks[0].valid is True
    llm.chat_completion.assert_not_called()


def test_validator_judges_multiple_free_text_candidates_and_checks_numbers():
    task = ContentTask(
        kind="readme_suggestion", target="readme", structured=False, current=None, source_material={},
        candidates=["This repo has 5 stars.", "This repo has 9999 stars!"],
    )
    ctx = _ctx_with_task(task, raw={"stars": 5})

    llm = MagicMock()
    llm.chat_completion.return_value = '{"best_index": 0, "reason": "accurate"}'
    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].winner == "This repo has 5 stars."
    assert ctx.tasks[0].winner_reason == "accurate"
    assert ctx.tasks[0].valid is True


def test_validator_rejects_winner_citing_unverified_numbers():
    task = ContentTask(
        kind="readme_suggestion", target="readme", structured=False, current=None, source_material={},
        candidates=["This repo has 5 stars.", "This repo has 9999 stars!"],
    )
    ctx = _ctx_with_task(task, raw={"stars": 5})

    llm = MagicMock()
    llm.chat_completion.return_value = '{"best_index": 1, "reason": "punchy"}'
    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].valid is False
    assert any("unverified numbers" in e for e in ctx.errors)


def test_validator_trusts_synthesizer_shape_check_for_structured_tasks():
    task = ContentTask(
        kind="topic_suggestion", target="topics", structured=True, current=["cli"], source_material={},
        candidates=[["cli", "python"], ["cli", "automation", "devtools"]],
    )
    ctx = _ctx_with_task(task)

    llm = MagicMock()
    llm.chat_completion.return_value = '{"best_index": 1, "reason": "broader coverage"}'
    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].winner == ["cli", "automation", "devtools"]
    assert ctx.tasks[0].valid is True
