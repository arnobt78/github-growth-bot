from datetime import date

from app.db import SessionLocal
from app.models import PipelineRun, Recommendation, Repo, Snapshot


def _seed():
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()
    db.refresh(repo)
    repo_id = repo.id  # captured before later commits expire the instance

    db.add(Snapshot(repo_id=repo_id, date=date(2026, 7, 19), stars=100, forks=10, watchers=100, open_issues=2))
    snap = Snapshot(repo_id=repo_id, date=date(2026, 7, 20), stars=110, forks=12, watchers=110, open_issues=3)
    db.add(snap)
    db.commit()
    db.refresh(snap)
    snap_id = snap.id

    db.add(Recommendation(repo_id=repo_id, snapshot_id=snap_id, category="missing_license", title="Add a LICENSE", body="No LICENSE file found.", validated=True))
    db.add(PipelineRun(status="ok"))
    db.commit()
    db.close()
    return repo_id


def test_snapshots_and_insights_and_recommendations_and_runs(client):
    repo_id = _seed()

    snapshots_resp = client.get(f"/repos/{repo_id}/snapshots")
    assert snapshots_resp.status_code == 200
    assert len(snapshots_resp.json()) == 2

    insights_resp = client.get(f"/repos/{repo_id}/insights")
    assert insights_resp.status_code == 200
    assert insights_resp.json()["latest_stars"] == 110

    recs_resp = client.get("/recommendations")
    assert recs_resp.status_code == 200
    rec_id = recs_resp.json()[0]["id"]

    dismiss_resp = client.patch(f"/recommendations/{rec_id}", json={"dismissed": True})
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["dismissed"] is True

    runs_resp = client.get("/runs")
    assert runs_resp.status_code == 200
    assert len(runs_resp.json()) == 1

    providers_resp = client.get("/providers/status")
    assert providers_resp.status_code == 200
    assert isinstance(providers_resp.json(), list)
