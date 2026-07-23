from app.db import Base, engine, SessionLocal
from app.models import Repo, User


def test_create_and_query_repo(seed_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()

    fetched = db.query(Repo).filter_by(owner="octocat", name="hello-world").first()
    assert fetched is not None
    assert fetched.name == "hello-world"
    assert fetched.tracked_since is not None
    db.close()


def test_create_user_and_scoped_repo():
    db = SessionLocal()
    user = User(
        github_id="555",
        username="tester",
        avatar_url="https://avatars.githubusercontent.com/u/555",
        email="tester@example.com",
        access_token_encrypted="ciphertext-placeholder",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.plan == "free"
    assert user.max_tracked_repos == 5

    repo = Repo(owner="octocat", name="hello-world", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    assert repo.user_id == user.id
    db.close()


def test_user_notification_fields_default_none_and_are_settable():
    db = SessionLocal()
    user = User(
        github_id="666",
        username="notif-tester",
        avatar_url="https://avatars.githubusercontent.com/u/666",
        email=None,
        access_token_encrypted="ciphertext-placeholder",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    assert user.notification_email is None
    assert user.last_reauth_notified_at is None

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    user.notification_email = "fallback@example.com"
    user.last_reauth_notified_at = now
    db.commit()
    db.refresh(user)

    assert user.notification_email == "fallback@example.com"
    assert user.last_reauth_notified_at is not None
    db.close()
