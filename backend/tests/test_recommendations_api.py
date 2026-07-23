from app.db import SessionLocal
from app.models import Recommendation, Repo


def _seed_recommendation_for(user_id: int) -> tuple[int, int]:
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    rec = Recommendation(
        user_id=user_id,
        repo_id=repo.id,
        category="missing_license",
        title="Add a LICENSE",
        body="No LICENSE file found.",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    rec_id = rec.id
    repo_id = repo.id
    db.close()
    return repo_id, rec_id


def test_recommendations_isolated_per_user(client, other_user_client):
    _repo_id, rec_id = _seed_recommendation_for(client.test_user_id)

    other_list = other_user_client.get("/recommendations")
    assert other_list.json() == []

    other_patch = other_user_client.patch(f"/recommendations/{rec_id}", json={"dismissed": True})
    assert other_patch.status_code == 404


def test_dismiss_recommendation(client):
    _repo_id, rec_id = _seed_recommendation_for(client.test_user_id)

    resp = client.patch(f"/recommendations/{rec_id}", json={"dismissed": True})
    assert resp.status_code == 200
    assert resp.json()["dismissed"] is True

    list_resp = client.get("/recommendations")
    assert any(r["id"] == rec_id and r["dismissed"] for r in list_resp.json())
