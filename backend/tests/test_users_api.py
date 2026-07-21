from app.db import SessionLocal
from app.models import User
from app.token_crypto import decrypt_token


def test_upsert_creates_new_user(client_without_user_token):
    resp = client_without_user_token.post(
        "/users/upsert",
        json={
            "github_id": "777",
            "username": "newuser",
            "avatar_url": "https://avatars.githubusercontent.com/u/777",
            "email": "newuser@example.com",
            "access_token": "gho_plaintextTokenFromOAuth",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["github_id"] == "777"
    assert "access_token" not in body
    assert "access_token_encrypted" not in body

    db = SessionLocal()
    user = db.query(User).filter(User.github_id == "777").one()
    assert decrypt_token(user.access_token_encrypted) == "gho_plaintextTokenFromOAuth"
    db.close()


def test_upsert_updates_existing_user_token(client_without_user_token):
    client_without_user_token.post(
        "/users/upsert",
        json={
            "github_id": "888",
            "username": "existing",
            "avatar_url": "https://avatars.githubusercontent.com/u/888",
            "email": "existing@example.com",
            "access_token": "gho_firstToken",
        },
    )
    resp = client_without_user_token.post(
        "/users/upsert",
        json={
            "github_id": "888",
            "username": "existing",
            "avatar_url": "https://avatars.githubusercontent.com/u/888",
            "email": "existing@example.com",
            "access_token": "gho_refreshedToken",
        },
    )
    assert resp.status_code == 200

    db = SessionLocal()
    matches = db.query(User).filter(User.github_id == "888").all()
    assert len(matches) == 1
    assert decrypt_token(matches[0].access_token_encrypted) == "gho_refreshedToken"
    db.close()


def test_upsert_requires_api_key(client_without_auth):
    resp = client_without_auth.post("/users/upsert", json={
        "github_id": "999", "username": "x", "avatar_url": "https://x", "email": None, "access_token": "t",
    })
    assert resp.status_code == 401
