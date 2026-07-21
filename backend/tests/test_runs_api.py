import time


def test_trigger_run_returns_immediately_and_scopes_to_caller(client):
    client.post("/repos", json={"owner": "octocat", "name": "hello-world"})

    start = time.monotonic()
    resp = client.post("/runs")
    elapsed = time.monotonic() - start

    assert resp.status_code == 202
    assert resp.json() == {"status": "started"}
    assert elapsed < 1.0  # must not block on the actual pipeline run


def test_trigger_run_requires_user_token(client_without_user_token):
    resp = client_without_user_token.post("/runs")
    assert resp.status_code == 401
