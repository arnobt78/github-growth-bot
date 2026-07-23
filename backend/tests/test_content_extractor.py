from unittest.mock import MagicMock

from app.models import Repo
from app.pipeline.content.extractor import ContentExtractor
from app.pipeline.content_base import ContentPipelineContext


def _fake_gh_client(missing: set[str] | None = None):
    missing = missing or set()
    gh = MagicMock()
    gh.get_repo.return_value = {
        "topics": ["cli", "python"],
        "description": "A tool",
        "stargazers_count": 42,
    }
    gh.get_readme.return_value = "# Hello"
    gh.has_file.side_effect = lambda owner, name, path: path not in missing
    return gh


def test_extractor_populates_raw_with_repo_material():
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    gh = _fake_gh_client()

    ctx = ContentExtractor(gh_client=gh).run(ctx)

    assert ctx.raw["readme"] == "# Hello"
    assert ctx.raw["topics"] == ["cli", "python"]
    assert ctx.raw["description"] == "A tool"
    assert ctx.raw["stars"] == 42
    assert ctx.raw["missing_docs"] == []


def test_extractor_detects_missing_standard_docs():
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    gh = _fake_gh_client(missing={"SECURITY.md", "CODE_OF_CONDUCT.md"})

    ctx = ContentExtractor(gh_client=gh).run(ctx)

    assert set(ctx.raw["missing_docs"]) == {"SECURITY.md", "CODE_OF_CONDUCT.md"}
