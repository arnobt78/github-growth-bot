from unittest.mock import patch

from app.db import SessionLocal
from app.models import Draft, Repo


def _seed_draft_for(user_id: int, status: str = "pending") -> tuple[int, int]:
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    draft = Draft(
        user_id=user_id,
        repo_id=repo.id,
        kind="readme_suggestion",
        target="readme",
        content={"text": "Add a Quick Start section."},
        status=status,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    repo_id, draft_id = repo.id, draft.id
    db.close()
    return repo_id, draft_id


def test_drafts_isolated_per_user(client, other_user_client):
    _repo_id, draft_id = _seed_draft_for(client.test_user_id)

    other_list = other_user_client.get("/drafts")
    assert other_list.json() == []

    other_patch = other_user_client.patch(f"/drafts/{draft_id}", json={"status": "approved"})
    assert other_patch.status_code == 404


def test_list_drafts_returns_current_users_drafts(client):
    _repo_id, draft_id = _seed_draft_for(client.test_user_id)

    resp = client.get("/drafts")
    assert resp.status_code == 200
    assert any(d["id"] == draft_id and d["status"] == "pending" for d in resp.json())


@patch("app.api.drafts.broadcaster.publish")
def test_approve_draft(mock_publish, client):
    _repo_id, draft_id = _seed_draft_for(client.test_user_id)

    resp = client.patch(f"/drafts/{draft_id}", json={"status": "approved"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["reviewed_at"] is not None

    mock_publish.assert_called_once_with(
        "draft_updated", {"id": draft_id, "status": "approved"}, user_id=client.test_user_id
    )


def test_reject_draft(client):
    _repo_id, draft_id = _seed_draft_for(client.test_user_id)

    resp = client.patch(f"/drafts/{draft_id}", json={"status": "rejected"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_patch_rejects_invalid_status_value(client):
    _repo_id, draft_id = _seed_draft_for(client.test_user_id)

    resp = client.patch(f"/drafts/{draft_id}", json={"status": "pending"})
    assert resp.status_code == 422


def test_patch_already_reviewed_draft_returns_409(client):
    _repo_id, draft_id = _seed_draft_for(client.test_user_id, status="approved")

    resp = client.patch(f"/drafts/{draft_id}", json={"status": "rejected"})
    assert resp.status_code == 409

    list_resp = client.get("/drafts")
    assert any(d["id"] == draft_id and d["status"] == "approved" for d in list_resp.json())


def test_drafts_require_user_token(client_without_user_token):
    resp = client_without_user_token.get("/drafts")
    assert resp.status_code == 401

    resp = client_without_user_token.patch("/drafts/1", json={"status": "approved"})
    assert resp.status_code == 401
