import base64

import httpx


class GitHubClient:
    def __init__(self, token: str, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=15.0,
        )

    def get_repo(self, owner: str, name: str) -> dict:
        resp = self._http.get(f"/repos/{owner}/{name}")
        resp.raise_for_status()
        return resp.json()

    def get_traffic_views(self, owner: str, name: str) -> dict:
        resp = self._http.get(f"/repos/{owner}/{name}/traffic/views")
        resp.raise_for_status()
        return resp.json()

    def get_traffic_clones(self, owner: str, name: str) -> dict:
        resp = self._http.get(f"/repos/{owner}/{name}/traffic/clones")
        resp.raise_for_status()
        return resp.json()

    def get_referrers(self, owner: str, name: str) -> list[dict]:
        resp = self._http.get(f"/repos/{owner}/{name}/traffic/popular/referrers")
        resp.raise_for_status()
        return resp.json()

    def get_popular_paths(self, owner: str, name: str) -> list[dict]:
        resp = self._http.get(f"/repos/{owner}/{name}/traffic/popular/paths")
        resp.raise_for_status()
        return resp.json()

    def get_readme(self, owner: str, name: str) -> str | None:
        resp = self._http.get(f"/repos/{owner}/{name}/readme")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        content = resp.json().get("content", "")
        return base64.b64decode(content).decode("utf-8", errors="replace")

    def has_file(self, owner: str, name: str, path: str) -> bool:
        resp = self._http.get(f"/repos/{owner}/{name}/contents/{path}")
        return resp.status_code == 200

    def search_similar_repos(self, language: str, topic: str, limit: int = 5) -> list[dict]:
        query = f"language:{language} topic:{topic}"
        resp = self._http.get("/search/repositories", params={"q": query, "sort": "stars", "per_page": limit})
        resp.raise_for_status()
        return resp.json().get("items", [])
