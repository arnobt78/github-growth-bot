from app.models import Repo
from app.pipeline.content.optimizer import ContentOptimizer
from app.pipeline.content.preprocessor import ContentPreprocessor
from app.pipeline.content_base import ContentPipelineContext, ContentTask


def _ctx_with_task(readme: str) -> ContentPipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [ContentTask(kind="readme_suggestion", target="readme", structured=False, current=readme, source_material={"readme": readme})]
    return ctx


def test_preprocessor_strips_whitespace_and_caps_length():
    ctx = _ctx_with_task("  \n# Hello  \n" + ("x" * 7000))
    ctx = ContentPreprocessor().run(ctx)
    readme = ctx.tasks[0].source_material["readme"]
    assert readme.startswith("# Hello")
    assert len(readme) <= 6000


def test_optimizer_caps_at_4000_chars():
    ctx = _ctx_with_task("y" * 10000)
    ctx = ContentPreprocessor().run(ctx)
    ctx = ContentOptimizer().run(ctx)
    assert len(ctx.tasks[0].source_material["readme"]) == 4000


def test_optimizer_noop_on_task_without_readme():
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [ContentTask(kind="missing_doc_suggestion", target="SECURITY.md", structured=False, current=None, source_material={"filename": "SECURITY.md"})]
    ctx = ContentOptimizer().run(ctx)
    assert "readme" not in ctx.tasks[0].source_material
