from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.db import SessionLocal
from app.models import User
from app.notifications import notify_drafts_ready, notify_needs_reauth, notify_pipeline_degraded


def _make_user(notification_email=None, email=None, last_reauth_notified_at=None) -> User:
    db = SessionLocal()
    user = User(
        github_id=f"notif-{id(object())}",
        username="notif-user",
        avatar_url="https://avatars.githubusercontent.com/u/1",
        email=email,
        notification_email=notification_email,
        last_reauth_notified_at=last_reauth_notified_at,
        access_token_encrypted="ciphertext-placeholder",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@patch("app.notifications._client")
def test_notify_pipeline_degraded_noops_with_no_recipient(mock_client_factory):
    user = _make_user(notification_email=None, email=None)
    notify_pipeline_degraded(user, ["octocat/hello-world"])
    mock_client_factory.assert_not_called()


@patch("app.notifications._client")
def test_notify_pipeline_degraded_noops_with_no_repos(mock_client_factory):
    user = _make_user(notification_email="me@example.com")
    notify_pipeline_degraded(user, [])
    mock_client_factory.assert_not_called()


@patch("app.notifications._client")
def test_notify_pipeline_degraded_sends_to_fallback_email(mock_client_factory):
    mock_client = MagicMock()
    mock_client_factory.return_value = mock_client
    user = _make_user(notification_email="fallback@example.com", email="github@example.com")

    notify_pipeline_degraded(user, ["octocat/hello-world"])

    mock_client.send.assert_called_once()
    assert mock_client.send.call_args[0][0] == "fallback@example.com"


@patch("app.notifications._client")
def test_notify_pipeline_degraded_falls_back_to_github_email(mock_client_factory):
    mock_client = MagicMock()
    mock_client_factory.return_value = mock_client
    user = _make_user(notification_email=None, email="github@example.com")

    notify_pipeline_degraded(user, ["octocat/hello-world"])

    assert mock_client.send.call_args[0][0] == "github@example.com"


@patch("app.notifications._client")
def test_notify_needs_reauth_sends_and_updates_timestamp_when_never_sent(mock_client_factory):
    mock_client = MagicMock()
    mock_client.send.return_value = True
    mock_client_factory.return_value = mock_client
    user = _make_user(notification_email="me@example.com", last_reauth_notified_at=None)

    db = SessionLocal()
    db.add(user)
    notify_needs_reauth(db, user)
    db.refresh(user)

    mock_client.send.assert_called_once()
    assert user.last_reauth_notified_at is not None
    db.close()


@patch("app.notifications._client")
def test_notify_needs_reauth_skips_within_24h_cooldown(mock_client_factory):
    mock_client = MagicMock()
    mock_client_factory.return_value = mock_client
    recent = datetime.now(timezone.utc) - timedelta(hours=2)
    user = _make_user(notification_email="me@example.com", last_reauth_notified_at=recent)

    db = SessionLocal()
    db.add(user)
    notify_needs_reauth(db, user)

    mock_client.send.assert_not_called()
    db.close()


@patch("app.notifications._client")
def test_notify_needs_reauth_sends_again_after_24h(mock_client_factory):
    mock_client = MagicMock()
    mock_client.send.return_value = True
    mock_client_factory.return_value = mock_client
    stale = datetime.now(timezone.utc) - timedelta(hours=25)
    user = _make_user(notification_email="me@example.com", last_reauth_notified_at=stale)

    db = SessionLocal()
    db.add(user)
    notify_needs_reauth(db, user)

    mock_client.send.assert_called_once()
    db.close()


@patch("app.notifications._client")
def test_notify_needs_reauth_does_not_update_timestamp_on_failed_send(mock_client_factory):
    mock_client = MagicMock()
    mock_client.send.return_value = False
    mock_client_factory.return_value = mock_client
    user = _make_user(notification_email="me@example.com", last_reauth_notified_at=None)

    db = SessionLocal()
    db.add(user)
    notify_needs_reauth(db, user)
    db.refresh(user)

    assert user.last_reauth_notified_at is None
    db.close()


@patch("app.notifications._client")
def test_notify_drafts_ready_noops_with_zero_count(mock_client_factory):
    user = _make_user(notification_email="me@example.com")
    notify_drafts_ready(user, 0)
    mock_client_factory.assert_not_called()


@patch("app.notifications._client")
def test_notify_drafts_ready_sends_with_positive_count(mock_client_factory):
    mock_client = MagicMock()
    mock_client_factory.return_value = mock_client
    user = _make_user(notification_email="me@example.com")

    notify_drafts_ready(user, 3)

    mock_client.send.assert_called_once()
    assert "3" in mock_client.send.call_args[0][1]  # subject mentions the count
