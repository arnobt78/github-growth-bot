def test_require_user_rejects_missing_token(client_without_user_token):
    resp = client_without_user_token.get("/repos")
    assert resp.status_code == 401


def test_require_user_rejects_invalid_token(client_without_user_token):
    client_without_user_token.headers.update({"X-Internal-User-Token": "garbage.notasignature"})
    resp = client_without_user_token.get("/repos")
    assert resp.status_code == 401


def test_require_user_rejects_unknown_github_id(client_without_user_token):
    from app.internal_auth import mint_internal_user_token

    client_without_user_token.headers.update(
        {"X-Internal-User-Token": mint_internal_user_token("no-such-user-999")}
    )
    resp = client_without_user_token.get("/repos")
    assert resp.status_code == 401


def test_require_user_accepts_valid_token(client):
    resp = client.get("/repos")
    assert resp.status_code == 200
