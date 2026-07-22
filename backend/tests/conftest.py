import os
import pytest
import tempfile

_test_db_dir = tempfile.mkdtemp()
_test_db_path = os.path.join(_test_db_dir, "test.db")

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_test_db_path}")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "zTgP1kM3vXG9wQeYrT6uI0oP2aS4dF7gH9jK1lN3mB8=")
os.environ.setdefault("INTERNAL_AUTH_SECRET", "test-only-internal-secret-do-not-use-in-prod")


@pytest.fixture(autouse=True)
def _reset_db():
    from app.db import Base, engine
    import app.models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.rate_limit import limiter
    limiter.reset()

    yield


def _create_user(github_id: str, username: str) -> int:
    from app.db import SessionLocal
    from app.models import User
    from app.token_crypto import encrypt_token

    db = SessionLocal()
    user = User(
        github_id=github_id,
        username=username,
        avatar_url=f"https://avatars.githubusercontent.com/u/{github_id}",
        email=f"{username}@example.com",
        access_token_encrypted=encrypt_token(f"test-github-oauth-token-{github_id}"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    return user_id


@pytest.fixture
def seed_user(_reset_db) -> int:
    return _create_user("12345", "octocat")


@pytest.fixture
def client(seed_user):
    from fastapi.testclient import TestClient
    from app.internal_auth import mint_internal_user_token
    from app.main import app

    test_client = TestClient(app)
    test_client.headers.update({
        "Authorization": "Bearer test-key",
        "X-Internal-User-Token": mint_internal_user_token("12345"),
    })
    test_client.test_user_id = seed_user
    return test_client


@pytest.fixture
def other_user_client(_reset_db):
    from fastapi.testclient import TestClient
    from app.internal_auth import mint_internal_user_token
    from app.main import app

    other_user_id = _create_user("99999", "other-user")
    test_client = TestClient(app)
    test_client.headers.update({
        "Authorization": "Bearer test-key",
        "X-Internal-User-Token": mint_internal_user_token("99999"),
    })
    test_client.test_user_id = other_user_id
    return test_client


@pytest.fixture
def client_without_auth():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def client_without_user_token():
    from fastapi.testclient import TestClient
    from app.main import app
    test_client = TestClient(app)
    test_client.headers.update({"Authorization": "Bearer test-key"})
    return test_client
