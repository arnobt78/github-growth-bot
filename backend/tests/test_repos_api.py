def test_create_list_get_delete_repo(client, seed_user):
    create_resp = client.post("/repos", json={"owner": "octocat", "name": "hello-world"})
    assert create_resp.status_code == 201
    repo_id = create_resp.json()["id"]

    list_resp = client.get("/repos")
    assert list_resp.status_code == 200
    assert any(r["id"] == repo_id for r in list_resp.json())

    get_resp = client.get(f"/repos/{repo_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["owner"] == "octocat"

    delete_resp = client.delete(f"/repos/{repo_id}")
    assert delete_resp.status_code == 204

    missing_resp = client.get(f"/repos/{repo_id}")
    assert missing_resp.status_code == 404


def test_requires_api_key():
    from fastapi.testclient import TestClient
    from app.main import app
    unauthenticated = TestClient(app)
    resp = unauthenticated.get("/repos")
    assert resp.status_code == 401
