from unittest.mock import MagicMock

from app.models import Repo
from app.pipeline.content.synthesizer import ContentSynthesizer
from app.pipeline.content_base import ContentPipelineContext, ContentTask


def _ctx_with_task(task: ContentTask) -> ContentPipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [task]
    return ctx


def _fake_llm(responses: list[str]):
    llm = MagicMock()
    llm.available_provider_names.return_value = ["groq", "gemini", "openrouter"]
    llm.chat_completion.side_effect = responses
    return llm


def test_synthesizer_collects_three_free_text_candidates():
    task = ContentTask(kind="readme_suggestion", target="readme", structured=False, current="# Old", source_material={"readme": "# Old", "topics": [], "description": None})
    ctx = _ctx_with_task(task)
    llm = _fake_llm(["# New A", "# New B", "# New C"])

    ctx = ContentSynthesizer(llm_router=llm).run(ctx)

    assert ctx.tasks[0].candidates == ["# New A", "# New B", "# New C"]
    assert llm.chat_completion.call_count == 3
    skip_sets = [call.kwargs["skip_providers"] for call in llm.chat_completion.call_args_list]
    assert skip_sets == [set(), {"groq"}, {"groq", "gemini"}]


def test_synthesizer_parses_structured_topic_candidates():
    task = ContentTask(kind="topic_suggestion", target="topics", structured=True, current=["cli"], source_material={"topics": ["cli"], "readme": "", "description": None})
    ctx = _ctx_with_task(task)
    llm = _fake_llm(['["cli", "python", "automation"]', "not json", '["cli", "devtools"]'])

    ctx = ContentSynthesizer(llm_router=llm).run(ctx)

    assert ctx.tasks[0].candidates == [["cli", "python", "automation"], ["cli", "devtools"]]


def test_synthesizer_omits_candidate_on_call_failure():
    task = ContentTask(kind="readme_suggestion", target="readme", structured=False, current=None, source_material={"readme": "", "topics": [], "description": None})
    ctx = _ctx_with_task(task)
    llm = MagicMock()
    llm.available_provider_names.return_value = ["groq", "gemini", "openrouter"]
    llm.chat_completion.side_effect = [RuntimeError("boom"), "# New B", RuntimeError("boom again")]

    ctx = ContentSynthesizer(llm_router=llm).run(ctx)

    assert ctx.tasks[0].candidates == ["# New B"]
    assert any("candidate call failed" in e for e in ctx.errors)


def test_synthesizer_gracefully_handles_unknown_kind():
    task = ContentTask(kind="unknown_kind", target="x", structured=False, current=None, source_material={})
    ctx = _ctx_with_task(task)
    llm = MagicMock()
    llm.available_provider_names.return_value = ["groq"]

    ctx = ContentSynthesizer(llm_router=llm).run(ctx)  # must not raise

    assert ctx.tasks[0].candidates == []
    assert any("unknown task kind" in e for e in ctx.errors)
    llm.chat_completion.assert_not_called()
