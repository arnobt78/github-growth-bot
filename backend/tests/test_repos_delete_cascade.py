from datetime import date

from app.db import SessionLocal
from app.models import BenchmarkRepo, PopularPath, Recommendation, Referrer, Repo, Snapshot


def _seed_repo_with_full_history(user_id):
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    repo_id = repo.id

    snapshot = Snapshot(
        user_id=user_id,
        repo_id=repo_id,
        date=date(2026, 7, 20),
        stars=100,
        forks=10,
        watchers=100,
        open_issues=2,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    snapshot_id = snapshot.id

    db.add(
        Recommendation(
            user_id=user_id,
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            category="missing_license",
            title="Add a LICENSE",
            body="No LICENSE file found.",
        )
    )
    db.add(Referrer(user_id=user_id, repo_id=repo_id, date=date(2026, 7, 20), referrer="github.com", count=50, uniques=30))
    db.add(PopularPath(user_id=user_id, repo_id=repo_id, date=date(2026, 7, 20), path="/", count=100, uniques=60))
    db.add(BenchmarkRepo(user_id=user_id, source_repo_id=repo_id, full_name="torvalds/linux", stars=999, forks=100, topics=["kernel"]))
    db.commit()
    db.close()
    return repo_id, snapshot_id


def test_delete_repo_with_zero_dependent_rows_still_works(client, seed_user):
    create_resp = client.post("/repos", json={"owner": "octocat", "name": "empty-repo"})
    assert create_resp.status_code == 201
    repo_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/repos/{repo_id}")
    assert delete_resp.status_code == 204

    db = SessionLocal()
    assert db.get(Repo, repo_id) is None
    db.close()


def test_delete_repo_cascades_all_dependent_rows(client, seed_user):
    repo_id, snapshot_id = _seed_repo_with_full_history(seed_user)

    delete_resp = client.delete(f"/repos/{repo_id}")
    assert delete_resp.status_code == 204

    db = SessionLocal()
    try:
        assert db.get(Repo, repo_id) is None
        assert db.query(Snapshot).filter_by(repo_id=repo_id).count() == 0
        assert db.query(Recommendation).filter_by(repo_id=repo_id).count() == 0
        assert db.query(Referrer).filter_by(repo_id=repo_id).count() == 0
        assert db.query(PopularPath).filter_by(repo_id=repo_id).count() == 0
        assert db.query(BenchmarkRepo).filter_by(source_repo_id=repo_id).count() == 0
        # snapshot_id used above only to prove it was seeded via a real FK chain
        assert snapshot_id is not None
    finally:
        db.close()
