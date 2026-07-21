from datetime import date

from app.db import SessionLocal
from app.models import BenchmarkRepo, PopularPath, Referrer, Repo


def _seed_repo_with_traffic_data(user_id):
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    repo_id = repo.id

    db.add(Referrer(user_id=user_id, repo_id=repo_id, date=date(2026, 7, 20), referrer="github.com", count=50, uniques=30))
    db.add(PopularPath(user_id=user_id, repo_id=repo_id, date=date(2026, 7, 20), path="/", count=100, uniques=60))
    db.add(BenchmarkRepo(user_id=user_id, source_repo_id=repo_id, full_name="torvalds/linux", stars=999, forks=100, topics=["kernel"]))
    db.commit()
    db.close()
    return repo_id


def test_repo_out_includes_tracked_since(client, seed_user):
    resp = client.post("/repos", json={"owner": "octocat", "name": "hello-world"})
    assert resp.status_code == 201
    assert "tracked_since" in resp.json()


def test_referrers_endpoint_returns_seeded_rows(client, seed_user):
    repo_id = _seed_repo_with_traffic_data(seed_user)

    resp = client.get(f"/repos/{repo_id}/referrers")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["referrer"] == "github.com"
    assert body[0]["uniques"] == 30


def test_popular_paths_endpoint_returns_seeded_rows(client, seed_user):
    repo_id = _seed_repo_with_traffic_data(seed_user)

    resp = client.get(f"/repos/{repo_id}/popular-paths")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["path"] == "/"
    assert body[0]["count"] == 100


def test_benchmarks_endpoint_uses_typed_schema(client, seed_user):
    repo_id = _seed_repo_with_traffic_data(seed_user)

    resp = client.get(f"/repos/{repo_id}/benchmarks")
    assert resp.status_code == 200
    assert resp.json() == [{"full_name": "torvalds/linux", "stars": 999, "forks": 100, "topics": ["kernel"]}]


def test_insights_endpoint_uses_typed_schema(client, seed_user):
    repo_id = _seed_repo_with_traffic_data(seed_user)

    resp = client.get(f"/repos/{repo_id}/insights")
    assert resp.status_code == 200
    assert resp.json() == {"latest_stars": 0, "latest_forks": 0, "recommendation_count": 0}


def test_unknown_repo_returns_404_for_new_endpoints(client):
    assert client.get("/repos/999999/referrers").status_code == 404
    assert client.get("/repos/999999/popular-paths").status_code == 404


def test_snapshots_isolated_per_user(client, other_user_client):
    repo_resp = client.post("/repos", json={"owner": "octocat", "name": "mine"})
    repo_id = repo_resp.json()["id"]

    other_snapshots = other_user_client.get(f"/repos/{repo_id}/snapshots")
    assert other_snapshots.status_code == 404

    other_insights = other_user_client.get(f"/repos/{repo_id}/insights")
    assert other_insights.status_code == 404

    other_benchmarks = other_user_client.get(f"/repos/{repo_id}/benchmarks")
    assert other_benchmarks.status_code == 404
