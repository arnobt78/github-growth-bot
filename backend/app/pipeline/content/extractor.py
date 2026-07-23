from app.github_client import GitHubClient
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext

# Beyond LICENSE/CONTRIBUTING.md (already checked by the analytics Extractor),
# these are the standard community-health files GitHub itself surfaces as
# "recommended community standards" — the natural next tier to auto-draft.
STANDARD_DOC_FILES = ["CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md"]


class ContentExtractor(Stage):
    name = "content_extractor"

    def __init__(self, gh_client: GitHubClient):
        self.gh_client = gh_client

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        owner, name = ctx.repo.owner, ctx.repo.name
        repo_data = self.gh_client.get_repo(owner, name)

        missing_docs = [f for f in STANDARD_DOC_FILES if not self.gh_client.has_file(owner, name, f)]

        ctx.raw = {
            "repo": repo_data,
            "readme": self.gh_client.get_readme(owner, name),
            "topics": repo_data.get("topics", []),
            "description": repo_data.get("description"),
            "stars": repo_data.get("stargazers_count", 0),
            "missing_docs": missing_docs,
        }
        return ctx
