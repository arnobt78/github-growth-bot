import httpx
import pytest

from app.github_client import GitHubAuthError, GitHubClient


@pytest.fixture
def mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octocat/hello-world":
            return httpx.Response(200, json={"stargazers_count": 42, "forks_count": 7, "watchers_count": 42, "open_issues_count": 3})
        if request.url.path == "/repos/octocat/hello-world/traffic/views":
            return httpx.Response(200, json={"count": 100, "uniques": 50})
        if request.url.path == "/repos/octocat/hello-world/traffic/clones":
            return httpx.Response(200, json={"count": 20, "uniques": 10})
        if request.url.path == "/repos/octocat/hello-world/traffic/popular/referrers":
            return httpx.Response(200, json=[{"referrer": "google.com", "count": 5, "uniques": 3}])
        if request.url.path == "/repos/octocat/hello-world/traffic/popular/paths":
            return httpx.Response(200, json=[{"path": "/", "count": 10, "uniques": 8}])
        if request.url.path == "/repos/octocat/hello-world/readme":
            return httpx.Response(200, json={"content": "SGVsbG8="})
        if request.url.path == "/repos/octocat/hello-world/contents/LICENSE":
            return httpx.Response(200, json={})
        if request.url.path == "/search/repositories":
            return httpx.Response(200, json={"items": [{"full_name": "similar/repo", "stargazers_count": 100, "forks_count": 20, "topics": ["python"]}]})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def gh_client(mock_transport):
    http = httpx.Client(base_url="https://api.github.com", transport=mock_transport)
    return GitHubClient(token="fake-token", http_client=http)


def test_get_repo(gh_client):
    data = gh_client.get_repo("octocat", "hello-world")
    assert data["stargazers_count"] == 42


def test_get_traffic_views(gh_client):
    data = gh_client.get_traffic_views("octocat", "hello-world")
    assert data["count"] == 100


def test_get_readme_decodes_base64(gh_client):
    text = gh_client.get_readme("octocat", "hello-world")
    assert text == "Hello"


def test_has_file_true(gh_client):
    assert gh_client.has_file("octocat", "hello-world", "LICENSE") is True


def test_has_file_false(gh_client):
    assert gh_client.has_file("octocat", "hello-world", "CONTRIBUTING.md") is False


def test_search_similar_repos(gh_client):
    results = gh_client.search_similar_repos(language="python", topic="cli", limit=5)
    assert results[0]["full_name"] == "similar/repo"


def test_get_repo_raises_github_auth_error_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://api.github.com")
    client = GitHubClient(token="expired-token", http_client=http_client)

    with pytest.raises(GitHubAuthError):
        client.get_repo("octocat", "hello-world")


def test_search_similar_repos_caches_across_instances():
    from app.github_client import GitHubClient

    GitHubClient._benchmark_cache.clear()
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json={"items": [{"full_name": "torvalds/linux"}]})

    transport = httpx.MockTransport(handler)

    client_a = GitHubClient(token="token-a", http_client=httpx.Client(transport=transport, base_url="https://api.github.com"))
    client_b = GitHubClient(token="token-b", http_client=httpx.Client(transport=transport, base_url="https://api.github.com"))

    client_a.search_similar_repos(language="python", topic="cli", limit=5)
    client_b.search_similar_repos(language="python", topic="cli", limit=5)

    assert call_count["n"] == 1
