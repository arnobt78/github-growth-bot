from app.models import Repo
from app.pipeline.content.analyzer import ContentAnalyzer
from app.pipeline.content_base import ContentPipelineContext


def _ctx(**raw_overrides) -> ContentPipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.raw = {
        "readme": "# Hello",
        "topics": ["cli"],
        "description": "A tool",
        "missing_docs": ["SECURITY.md"],
    }
    ctx.raw.update(raw_overrides)
    return ctx


def test_analyzer_always_builds_readme_and_seo_tasks():
    ctx = ContentAnalyzer().run(_ctx())
    kinds = [t.kind for t in ctx.tasks]
    assert "readme_suggestion" in kinds
    assert "seo_suggestion" in kinds


def test_analyzer_builds_one_task_per_missing_doc():
    ctx = ContentAnalyzer().run(_ctx(missing_docs=["SECURITY.md", "CODE_OF_CONDUCT.md"]))
    doc_tasks = [t for t in ctx.tasks if t.kind == "missing_doc_suggestion"]
    assert {t.target for t in doc_tasks} == {"SECURITY.md", "CODE_OF_CONDUCT.md"}
    assert all(t.current is None and t.structured is False for t in doc_tasks)


def test_analyzer_skips_topic_task_when_already_well_tagged():
    ctx = ContentAnalyzer().run(_ctx(topics=["a", "b", "c", "d", "e"]))
    assert not any(t.kind == "topic_suggestion" for t in ctx.tasks)


def test_analyzer_builds_topic_task_when_under_tagged():
    ctx = ContentAnalyzer().run(_ctx(topics=["cli"]))
    topic_task = next(t for t in ctx.tasks if t.kind == "topic_suggestion")
    assert topic_task.current == ["cli"]
    assert topic_task.structured is True


def test_analyzer_builds_release_notes_task_for_new_release():
    ctx = _ctx(latest_release={"tag_name": "v1.2.0", "body": "- Added dark mode"})
    ctx = ContentAnalyzer().run(ctx)

    release_task = next(t for t in ctx.tasks if t.kind == "release_notes")
    assert release_task.target == "v1.2.0"
    assert release_task.current is None
    assert release_task.structured is False
    assert release_task.source_material == {"tag": "v1.2.0", "raw_notes": "- Added dark mode", "repo_name": "hello-world"}


def test_analyzer_skips_release_notes_task_when_tag_already_drafted():
    ctx = _ctx(latest_release={"tag_name": "v1.2.0", "body": "- Added dark mode"})
    ctx.repo.last_release_tag = "v1.2.0"

    ctx = ContentAnalyzer().run(ctx)

    assert not any(t.kind == "release_notes" for t in ctx.tasks)


def test_analyzer_skips_release_notes_task_when_body_is_empty():
    ctx = _ctx(latest_release={"tag_name": "v1.2.0", "body": ""})
    ctx = ContentAnalyzer().run(ctx)

    assert not any(t.kind == "release_notes" for t in ctx.tasks)


def test_analyzer_skips_release_notes_task_when_no_release_exists():
    ctx = _ctx(latest_release=None)
    ctx = ContentAnalyzer().run(ctx)

    assert not any(t.kind == "release_notes" for t in ctx.tasks)
