from app.github_client import GitHubClient
from app.pipeline.base import PipelineContext, Stage


class Extractor(Stage):
    name = "extractor"

    def __init__(self, gh_client: GitHubClient):
        self.gh_client = gh_client

    def run(self, ctx: PipelineContext) -> PipelineContext:
        owner, name = ctx.repo.owner, ctx.repo.name
        repo_data = self.gh_client.get_repo(owner, name)

        ctx.raw = {
            "repo": repo_data,
            "traffic_views": self.gh_client.get_traffic_views(owner, name),
            "traffic_clones": self.gh_client.get_traffic_clones(owner, name),
            "referrers": self.gh_client.get_referrers(owner, name),
            "popular_paths": self.gh_client.get_popular_paths(owner, name),
            "readme": self.gh_client.get_readme(owner, name),
            "has_license": self.gh_client.has_file(owner, name, "LICENSE"),
            "has_contributing": self.gh_client.has_file(owner, name, "CONTRIBUTING.md"),
            "topics": repo_data.get("topics", []),
            "benchmarks": self._get_benchmarks(repo_data),
        }
        return ctx

    def _get_benchmarks(self, repo_data: dict) -> list[dict]:
        language = repo_data.get("language") or ""
        topics = repo_data.get("topics") or []
        if not language or not topics:
            return []
        return self.gh_client.search_similar_repos(language=language, topic=topics[0], limit=5)
