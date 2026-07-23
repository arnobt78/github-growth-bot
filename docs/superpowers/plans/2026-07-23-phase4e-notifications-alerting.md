# Phase 4E: Notifications & Alerting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resend-backed email alerts fire on scheduled (not manual) analytics-run degradation, `needs_reauth` (rate-limited to once per 24h), and new content-pipeline drafts ready — plus a Settings-page fallback email field for users with no public GitHub email.

**Architecture:** A new `EmailClient` (httpx, mirrors `GitHubClient`'s shape, fails soft) and `notifications.py` (three sender functions) get wired into `run_pipeline_for_all_repos`/`run_content_pipeline_for_all_repos` via a new `notify: bool = False` parameter that only the two APScheduler wrappers in `main.py` set `True`. Two new nullable `User` columns store the fallback recipient and reauth-email rate-limit timestamp. A new `GET`/`PATCH /users/me` pair (first `require_user`-scoped endpoints on `app/api/users.py`) backs a new Settings-page card, wired into the existing SSE/TanStack Query invalidation pattern via a new `user_updated` event.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, httpx, pytest (backend); Next.js 16 App Router, TanStack Query, Vitest (frontend).

## Global Constraints

- Manual triggers (`POST /runs`, `POST /runs/content`) never send email — `notify` must default to `False` and only the two scheduler wrappers in `app/main.py` pass `notify=True`.
- `needs_reauth` emails are rate-limited to once per 24h via `User.last_reauth_notified_at`; the timestamp only updates when the send actually succeeds.
- Recipient resolves to `user.notification_email or user.email`; if neither exists, every notify function is a silent no-op (not an error, not a log line beyond normal operation).
- `EmailClient.send` never raises — a Resend outage must degrade to "no email sent," never crash a scheduled job.
- No endpoint path may contain `analytics`/`analysis`/`tracking`/`performance`/`metrics`.
- Every new/changed endpoint keeps `Depends(require_api_key)` (router-level, already present on `app/api/users.py`) and adds `Depends(require_user)` for the two new per-user endpoints.
- `Resend`/`EMAIL_FROM`/`FRONTEND_BASE_URL` values are read only from `Settings` (env-backed) — never hardcoded, never logged.
- Full spec: `docs/superpowers/specs/2026-07-23-phase4e-notifications-alerting-design.md`.

---

### Task 1: `User` model columns + migration

**Files:**
- Modify: `backend/app/models.py` (`User` class)
- Create: `backend/alembic/versions/<hash>_add_notification_fields_to_users.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `User.notification_email: str | None`, `User.last_reauth_notified_at: datetime | None` — both nullable, both consumed by `app/notifications.py` (Task 3) and `app/api/users.py` (Task 6).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py::test_user_notification_fields_default_none_and_are_settable -v`
Expected: FAIL with `AttributeError: 'User' object has no attribute 'notification_email'` (or a `TypeError` from the constructor rejecting an unknown kwarg is NOT expected here since we don't pass it to the constructor — the failure is the two `assert`/attribute-access lines).

- [ ] **Step 3: Add the columns to the model**

In `backend/app/models.py`, inside `class User(Base):`, immediately after the existing `email` column (find `email: Mapped[str | None] = mapped_column(String(255), nullable=True)`), add:

```python
    # Fallback alert-email recipient when `email` (derived from GitHub OAuth
    # scope, not guaranteed present) is empty. Settings page lets the user
    # set/clear this directly — see app/api/users.py's GET/PATCH /users/me.
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Rate-limit guard for the needs_reauth alert email: null means "never
    # sent (or eligible to send again)". needs_reauth persists until the user
    # reconnects GitHub, so without this the daily scheduler would re-email
    # the same unresolved condition every single day.
    last_reauth_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

(`datetime` is already imported at the top of `models.py` — confirm, don't re-add if present.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py -v`
Expected: all pass, including the new test. (Test DB is SQLite recreated fresh per test via `conftest.py`'s `_reset_db` autouse fixture, so no migration is needed for tests to pass — but the migration is still required for real Postgres.)

- [ ] **Step 5: Generate and review the Alembic migration**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "add notification fields to users"`

This creates `backend/alembic/versions/<hash>_add_notification_fields_to_users.py` with `down_revision = '779af5521153'` (the current head). Open it and confirm it matches this shape (both columns nullable, no `server_default` needed since nullable columns don't violate constraints on existing rows):

```python
def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('notification_email', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('last_reauth_notified_at', sa.DateTime(timezone=True), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'last_reauth_notified_at')
    op.drop_column('users', 'notification_email')
    # ### end Alembic commands ###
```

If the autogenerated file differs in column order or adds anything unexpected (e.g. picks up unrelated drift), fix it to match exactly this `upgrade`/`downgrade` pair before continuing — this project's established habit is to always manually review autogenerated migrations, never blindly commit them.

Do **not** run `alembic upgrade head` against a real database in this task (no local Postgres is assumed to be running in the dev/CI sandbox) — the migration file being correct and the SQLite-backed test suite passing is the deliverable here. The Product Owner runs `alembic upgrade head` against their own local/prod Postgres when ready, same as every prior migration in this project.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/alembic/versions/*_add_notification_fields_to_users.py backend/tests/test_models.py
git commit -m "feat(4e): add notification_email + last_reauth_notified_at to User"
```

---

### Task 2: `EmailClient`

**Files:**
- Create: `backend/app/email_client.py`
- Test: `backend/tests/test_email_client.py`

**Interfaces:**
- Produces: `EmailClient(api_key: str, from_address: str, http_client: httpx.Client | None = None)` with method `send(to: str, subject: str, html: str) -> bool`. Consumed by `app/notifications.py` (Task 3).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_email_client.py`:

```python
import httpx
import pytest

from app.email_client import EmailClient


@pytest.fixture
def success_client():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer fake-resend-key"
        return httpx.Response(200, json={"id": "email-123"})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url="https://api.resend.com", transport=transport)
    return EmailClient(api_key="fake-resend-key", from_address="Bot <bot@example.com>", http_client=http)


@pytest.fixture
def failing_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "internal error"})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url="https://api.resend.com", transport=transport)
    return EmailClient(api_key="fake-resend-key", from_address="Bot <bot@example.com>", http_client=http)


def test_send_returns_true_on_success(success_client):
    assert success_client.send("user@example.com", "Subject", "<p>Body</p>") is True


def test_send_returns_false_on_http_error(failing_client):
    assert failing_client.send("user@example.com", "Subject", "<p>Body</p>") is False


def test_send_sends_correct_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = httpx.Request(
            request.method, request.url, headers=request.headers, content=request.content
        ).read()
        import json as json_module
        captured["body"] = json_module.loads(request.content)
        return httpx.Response(200, json={"id": "email-123"})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url="https://api.resend.com", transport=transport)
    client = EmailClient(api_key="k", from_address="Bot <bot@example.com>", http_client=http)

    client.send("user@example.com", "Hello", "<p>Hi</p>")

    assert captured["body"] == {
        "from": "Bot <bot@example.com>",
        "to": ["user@example.com"],
        "subject": "Hello",
        "html": "<p>Hi</p>",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_email_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.email_client'`

- [ ] **Step 3: Implement `EmailClient`**

Create `backend/app/email_client.py`:

```python
import httpx


class EmailClient:
    """Thin wrapper around Resend's REST API, mirroring GitHubClient's
    httpx.Client-based shape. Unlike GitHubClient (which raises
    GitHubAuthError on a rejected token), send() never raises — a Resend
    outage must degrade to "no email sent for this one alert," never crash
    the scheduled job that's calling it."""

    def __init__(self, api_key: str, from_address: str, http_client: httpx.Client | None = None):
        self._from = from_address
        self._http = http_client or httpx.Client(
            base_url="https://api.resend.com",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )

    def send(self, to: str, subject: str, html: str) -> bool:
        try:
            resp = self._http.post(
                "/emails",
                json={"from": self._from, "to": [to], "subject": subject, "html": html},
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPError:
            return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_email_client.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/email_client.py backend/tests/test_email_client.py
git commit -m "feat(4e): add EmailClient (Resend REST wrapper)"
```

---

### Task 3: `notifications.py` + config settings

**Files:**
- Create: `backend/app/notifications.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_notifications.py`

**Interfaces:**
- Consumes: `EmailClient` (Task 2), `Settings` (this task adds 3 fields to it), `User` model (Task 1's new columns).
- Produces: `notify_pipeline_degraded(user: User, repo_names: list[str]) -> None`, `notify_needs_reauth(db: Session, user: User) -> None`, `notify_drafts_ready(user: User, draft_count: int) -> None`. Consumed by `app/pipeline/jobs.py` and `app/pipeline/content_jobs.py` (Tasks 4 and 5).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_notifications.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_notifications.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.notifications'`

- [ ] **Step 3: Add the 3 new settings fields**

In `backend/app/config.py`, inside `class Settings(BaseSettings):`, immediately after the existing `internal_auth_secret: str = ""` line, add:

```python

    # Phase 4E: Notifications & alerting
    resend_api_key: str = ""
    email_from: str = ""
    frontend_base_url: str = ""
```

- [ ] **Step 4: Document the new settings in `.env.example`**

In `backend/.env.example`, after the existing `INTERNAL_AUTH_SECRET=` block, add:

```text

# --- Phase 4E: Notifications & alerting (all optional — if unset, alert
# emails silently never send; no error, no crash) ---
# Resend: https://resend.com/api-keys (free tier is generous for personal-SaaS volume)
RESEND_API_KEY=
# Must be a sender address verified on your Resend account/domain, e.g.
# "GitHub Growth <alerts@yourdomain.com>". Using an unverified domain causes
# every send to fail (EmailClient degrades to "no email sent," not a crash).
EMAIL_FROM=
# Your deployed frontend's base URL, used to build the "View" button link in
# alert emails, e.g. https://your-app.vercel.app (no trailing slash).
FRONTEND_BASE_URL=
```

- [ ] **Step 5: Implement `notifications.py`**

Create `backend/app/notifications.py`:

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.email_client import EmailClient
from app.models import User

REAUTH_COOLDOWN = timedelta(hours=24)


def _recipient(user: User) -> str | None:
    return user.notification_email or user.email


def _render_email(title: str, body_html: str, cta_label: str, cta_path: str) -> str:
    settings = get_settings()
    cta_url = f"{settings.frontend_base_url}{cta_path}"
    return f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #0f172a;">{title}</h2>
      <div style="color: #334155; line-height: 1.6;">{body_html}</div>
      <a href="{cta_url}" style="display: inline-block; margin-top: 16px; padding: 10px 20px;
         background: #0ea5e9; color: white; border-radius: 6px; text-decoration: none;">{cta_label}</a>
    </div>
    """


def _client() -> EmailClient:
    settings = get_settings()
    return EmailClient(api_key=settings.resend_api_key, from_address=settings.email_from)


def notify_pipeline_degraded(user: User, repo_names: list[str]) -> None:
    to = _recipient(user)
    if not to or not repo_names:
        return
    body = "The following tracked repos had an issue during today's run: " + ", ".join(repo_names)
    html = _render_email("Some repos need attention", body, "View runs", "/runs")
    _client().send(to, "GitHub Growth Bot: a repo run had issues", html)


def notify_needs_reauth(db: Session, user: User) -> None:
    to = _recipient(user)
    if not to:
        return
    now = datetime.now(timezone.utc)
    if user.last_reauth_notified_at and now - user.last_reauth_notified_at < REAUTH_COOLDOWN:
        return
    html = _render_email(
        "Reconnect your GitHub account",
        "Your GitHub sign-in has expired or was revoked, so today's run couldn't fetch your repo data.",
        "Reconnect",
        "/settings",
    )
    if _client().send(to, "GitHub Growth Bot: please reconnect GitHub", html):
        user.last_reauth_notified_at = now
        db.commit()


def notify_drafts_ready(user: User, draft_count: int) -> None:
    to = _recipient(user)
    if not to or draft_count < 1:
        return
    html = _render_email(
        f"{draft_count} new draft{'s' if draft_count != 1 else ''} ready",
        "New content suggestions are waiting for your review.",
        "Review drafts",
        "/drafts",
    )
    _client().send(to, f"GitHub Growth Bot: {draft_count} new drafts ready to review", html)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_notifications.py -v`
Expected: `10 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/notifications.py backend/app/config.py backend/.env.example backend/tests/test_notifications.py
git commit -m "feat(4e): add notifications.py (degraded/reauth/drafts-ready senders)"
```

---

### Task 4: Wire `notify` into `run_pipeline_for_all_repos`

**Files:**
- Modify: `backend/app/pipeline/jobs.py`
- Test: `backend/tests/test_pipeline_per_user.py`

**Interfaces:**
- Consumes: `notify_pipeline_degraded`, `notify_needs_reauth` from `app/notifications.py` (Task 3).
- Produces: `run_pipeline_for_all_repos(db: Session, user_id: int | None = None, notify: bool = False) -> None` (signature change — adds `notify` param, default preserves existing behavior for all current callers).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_pipeline_per_user.py`:

```python
@patch("app.pipeline.jobs.notify_needs_reauth")
@patch("app.pipeline.jobs.notify_pipeline_degraded")
@patch("app.events.broadcaster.publish")
@patch("app.pipeline.jobs.build_stages")
def test_notify_false_by_default_sends_nothing(mock_build_stages, mock_publish, mock_notify_degraded, mock_notify_reauth):
    user_id, _repo_id = _seed_user_with_repo("901")

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = lambda repo: type(
        "Ctx", (), {"errors": ["extractor: boom"]}
    )()
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db, user_id=user_id)  # notify defaults False
        db.close()

    mock_notify_degraded.assert_not_called()
    mock_notify_reauth.assert_not_called()


@patch("app.pipeline.jobs.notify_needs_reauth")
@patch("app.pipeline.jobs.notify_pipeline_degraded")
@patch("app.events.broadcaster.publish")
@patch("app.pipeline.jobs.build_stages")
def test_notify_true_sends_degraded_alert_with_repo_names(mock_build_stages, mock_publish, mock_notify_degraded, mock_notify_reauth):
    user_id, repo_id = _seed_user_with_repo("902")

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = lambda repo: type(
        "Ctx", (), {"errors": ["extractor: boom"]}
    )()
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db, user_id=user_id, notify=True)
        db.close()

    mock_notify_degraded.assert_called_once()
    call_user, call_repo_names = mock_notify_degraded.call_args[0]
    assert call_user.id == user_id
    assert call_repo_names == ["octocat/repo-902"]
    mock_notify_reauth.assert_not_called()


@patch("app.pipeline.jobs.notify_needs_reauth")
@patch("app.pipeline.jobs.notify_pipeline_degraded")
@patch("app.events.broadcaster.publish")
@patch("app.pipeline.jobs.build_stages")
def test_notify_true_sends_reauth_alert(mock_build_stages, mock_publish, mock_notify_degraded, mock_notify_reauth):
    user_id, _repo_id = _seed_user_with_repo("903")

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = lambda repo: type(
        "Ctx", (), {"errors": ["extractor: needs_reauth: GitHub token rejected"]}
    )()
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db, user_id=user_id, notify=True)
        db.close()

    mock_notify_reauth.assert_called_once()
    reauth_db_arg, reauth_user_arg = mock_notify_reauth.call_args[0]
    assert reauth_user_arg.id == user_id
    mock_notify_degraded.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_pipeline_per_user.py -v -k notify`
Expected: FAIL — `TypeError: run_pipeline_for_all_repos() got an unexpected keyword argument 'notify'`

- [ ] **Step 3: Wire `notify` into `run_pipeline_for_all_repos`**

In `backend/app/pipeline/jobs.py`, add the import (alongside the existing imports):

```python
from app.notifications import notify_needs_reauth, notify_pipeline_degraded
```

Replace the function signature and body (the existing loop's needs_reauth handling stays exactly as-is; this adds a `degraded` dict and the post-loop notify block):

```python
def run_pipeline_for_all_repos(db: Session, user_id: int | None = None, notify: bool = False) -> None:
    settings = get_settings()
    llm_router = LLMRouter(settings=settings, db_session=db)

    query = db.query(Repo)
    if user_id is not None:
        query = query.filter(Repo.user_id == user_id)
    repos = query.all()

    failed_auth_user_ids: set[int] = set()
    processed_user_ids: set[int] = set()
    degraded: dict[int, list[str]] = {}

    for repo in repos:
        if repo.user_id in failed_auth_user_ids:
            continue

        try:
            owner = db.get(User, repo.user_id)
            gh_client = GitHubClient(token=decrypt_token(owner.access_token_encrypted))
        except Exception:
            failed_auth_user_ids.add(repo.user_id)
            continue

        runner = PipelineRunner(stages=build_stages(db, gh_client, llm_router), db_session=db)
        ctx = runner.run_for_repo(repo)

        if any("needs_reauth" in error for error in ctx.errors):
            failed_auth_user_ids.add(repo.user_id)
            continue

        if ctx.errors:
            degraded.setdefault(repo.user_id, []).append(f"{repo.owner}/{repo.name}")

        processed_user_ids.add(repo.user_id)

    for uid in processed_user_ids:
        broadcaster.publish("run_completed", {}, user_id=uid)

    if notify:
        for uid, repo_names in degraded.items():
            owner = db.get(User, uid)
            if owner is not None:
                notify_pipeline_degraded(owner, repo_names)
        for uid in failed_auth_user_ids:
            owner = db.get(User, uid)
            if owner is not None:
                notify_needs_reauth(db, owner)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_pipeline_per_user.py -v`
Expected: all pass (existing tests + 3 new ones), no regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/jobs.py backend/tests/test_pipeline_per_user.py
git commit -m "feat(4e): wire notify param into run_pipeline_for_all_repos"
```

---

### Task 5: Wire `notify` into `run_content_pipeline_for_all_repos` + scheduler

**Files:**
- Modify: `backend/app/pipeline/content_jobs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_content_jobs.py`

**Interfaces:**
- Consumes: `notify_drafts_ready` from `app/notifications.py` (Task 3).
- Produces: `run_content_pipeline_for_all_repos(db: Session, user_id: int | None = None, notify: bool = False) -> None` (signature change, same default-preserving pattern as Task 4).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_content_jobs.py`:

```python
@patch("app.pipeline.content_jobs.notify_drafts_ready")
@patch("app.pipeline.content_jobs.broadcaster.publish")
@patch("app.pipeline.content_jobs.GitHubClient")
@patch("app.pipeline.content_jobs.LLMRouter")
def test_notify_false_by_default_sends_nothing(mock_llm_cls, mock_gh_cls, mock_publish, mock_notify, seed_user):
    mock_gh_cls.return_value = _fake_gh_client()
    mock_llm_cls.return_value = _fake_llm_router()

    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()

    run_content_pipeline_for_all_repos(db, user_id=seed_user)  # notify defaults False
    db.close()

    mock_notify.assert_not_called()


@patch("app.pipeline.content_jobs.notify_drafts_ready")
@patch("app.pipeline.content_jobs.broadcaster.publish")
@patch("app.pipeline.content_jobs.GitHubClient")
@patch("app.pipeline.content_jobs.LLMRouter")
def test_notify_true_sends_drafts_ready_with_count(mock_llm_cls, mock_gh_cls, mock_publish, mock_notify, seed_user):
    mock_gh_cls.return_value = _fake_gh_client()
    mock_llm_cls.return_value = _fake_llm_router()

    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()

    run_content_pipeline_for_all_repos(db, user_id=seed_user, notify=True)

    mock_notify.assert_called_once()
    call_user, call_count = mock_notify.call_args[0]
    assert call_user.id == seed_user
    assert call_count >= 1  # at least the readme_suggestion draft
    db.close()


@patch("app.pipeline.content_jobs.notify_drafts_ready")
@patch("app.pipeline.content_jobs.broadcaster.publish")
def test_notify_true_skips_when_zero_drafts_created(mock_publish, mock_notify, seed_user):
    db = SessionLocal()
    user = db.get(User, seed_user)
    user.access_token_encrypted = "not-valid-fernet-ciphertext"
    db.commit()

    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()

    run_content_pipeline_for_all_repos(db, user_id=seed_user, notify=True)
    db.close()

    mock_notify.assert_not_called()
```

(`_fake_gh_client`, `_fake_llm_router` are the existing module-level helpers already defined at the top of `test_content_jobs.py` — reuse them, do not redefine.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_jobs.py -v -k notify`
Expected: FAIL — `TypeError: run_content_pipeline_for_all_repos() got an unexpected keyword argument 'notify'`

- [ ] **Step 3: Wire `notify` into `run_content_pipeline_for_all_repos`**

In `backend/app/pipeline/content_jobs.py`, add the import and a `datetime`/`Draft` import (check `Draft` isn't already imported — it isn't, per the current file's `from app.models import Repo, User`):

```python
from datetime import datetime, timezone

from app.models import Draft, Repo, User
from app.notifications import notify_drafts_ready
```

Replace the function signature and body:

```python
def run_content_pipeline_for_all_repos(db: Session, user_id: int | None = None, notify: bool = False) -> None:
    settings = get_settings()
    llm_router = LLMRouter(settings=settings, db_session=db)

    query = db.query(Repo)
    if user_id is not None:
        query = query.filter(Repo.user_id == user_id)
    repos = query.all()

    failed_auth_user_ids: set[int] = set()
    processed_user_ids: set[int] = set()
    run_started_at = datetime.now(timezone.utc)

    for repo in repos:
        if repo.user_id in failed_auth_user_ids:
            continue

        try:
            owner = db.get(User, repo.user_id)
            gh_client = GitHubClient(token=decrypt_token(owner.access_token_encrypted))
        except Exception:
            failed_auth_user_ids.add(repo.user_id)
            continue

        runner = PipelineRunner(
            stages=build_content_stages(db, gh_client, llm_router),
            db_session=db,
            context_factory=ContentPipelineContext,
            pipeline_kind="content",
        )
        ctx = runner.run_for_repo(repo)

        if any("needs_reauth" in error for error in ctx.errors):
            failed_auth_user_ids.add(repo.user_id)
            continue

        processed_user_ids.add(repo.user_id)

    for uid in processed_user_ids:
        broadcaster.publish("drafts_generated", {}, user_id=uid)

    if notify:
        for uid in processed_user_ids:
            draft_count = db.query(Draft).filter(
                Draft.user_id == uid, Draft.created_at >= run_started_at
            ).count()
            if draft_count > 0:
                owner = db.get(User, uid)
                if owner is not None:
                    notify_drafts_ready(owner, draft_count)
```

- [ ] **Step 4: Pass `notify=True` from the scheduler wrappers**

In `backend/app/main.py`, update both scheduler wrapper functions:

```python
def _scheduled_pipeline_run() -> None:
    db = SessionLocal()
    try:
        run_pipeline_for_all_repos(db, notify=True)
    finally:
        db.close()


def _scheduled_content_pipeline_run() -> None:
    db = SessionLocal()
    try:
        run_content_pipeline_for_all_repos(db, notify=True)
    finally:
        db.close()
```

(Everything else in `main.py` — the `add_job` calls, the 12h offset comment, imports — stays unchanged. `app/api/runs.py`'s two manual-trigger routes are NOT touched in this task — they keep calling `run_pipeline_for_all_repos(db, user_id=user_id)` / `run_content_pipeline_for_all_repos(db, user_id=user_id)` with no `notify` arg, correctly defaulting to `False`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_jobs.py -v`
Expected: all pass (existing 2 + 3 new), no regressions.

Then run the full backend suite to confirm no cross-file regressions from the `main.py` change:

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all pass (115 + the new tests from Tasks 1-4, no failures).

- [ ] **Step 6: Commit**

```bash
git add backend/app/pipeline/content_jobs.py backend/app/main.py backend/tests/test_content_jobs.py
git commit -m "feat(4e): wire notify param into run_content_pipeline_for_all_repos + scheduler"
```

---

### Task 6: `GET`/`PATCH /users/me` + `user_updated` SSE event

**Files:**
- Modify: `backend/app/api/users.py`
- Test: `backend/tests/test_users_api.py`

**Interfaces:**
- Consumes: `require_user` from `app/deps.py` (already used by every other per-user router).
- Produces: `GET /users/me -> UserOut` (extended with `notification_email`), `PATCH /users/me` (body `{"notification_email": str | None}`) `-> UserOut`. Publishes `broadcaster.publish("user_updated", {}, user_id=current_user.id)` on successful `PATCH`. Consumed by the frontend's `lib/api.ts` (Task 7).

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_users_api.py` (add the needed imports at the top: `from unittest.mock import patch` alongside the existing imports):

```python
from unittest.mock import patch


def test_get_me_returns_current_user(client):
    resp = client.get("/users/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == client.test_user_id
    assert body["username"] == "octocat"
    assert body["notification_email"] is None


def test_get_me_requires_user_token(client_without_user_token):
    resp = client_without_user_token.get("/users/me")
    assert resp.status_code == 401


@patch("app.api.users.broadcaster.publish")
def test_patch_me_sets_notification_email(mock_publish, client):
    resp = client.patch("/users/me", json={"notification_email": "fallback@example.com"})
    assert resp.status_code == 200
    assert resp.json()["notification_email"] == "fallback@example.com"

    mock_publish.assert_called_once_with("user_updated", {}, user_id=client.test_user_id)

    followup = client.get("/users/me")
    assert followup.json()["notification_email"] == "fallback@example.com"


def test_patch_me_empty_string_normalizes_to_none(client):
    client.patch("/users/me", json={"notification_email": "fallback@example.com"})
    resp = client.patch("/users/me", json={"notification_email": ""})
    assert resp.status_code == 200
    assert resp.json()["notification_email"] is None


def test_patch_me_requires_user_token(client_without_user_token):
    resp = client_without_user_token.patch("/users/me", json={"notification_email": "x@example.com"})
    assert resp.status_code == 401


def test_users_me_is_scoped_to_the_calling_user(client, other_user_client):
    client.patch("/users/me", json={"notification_email": "mine@example.com"})
    other_resp = other_user_client.get("/users/me")
    assert other_resp.json()["notification_email"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_users_api.py -v -k "me"`
Expected: FAIL — `404 Not Found` for `/users/me` (route doesn't exist yet).

- [ ] **Step 3: Implement `GET`/`PATCH /users/me`**

In `backend/app/api/users.py`, update the imports and add the new route. Full new file content:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key, require_user
from app.events import broadcaster
from app.models import User
from app.token_crypto import encrypt_token

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_api_key)])


class UserUpsert(BaseModel):
    github_id: str
    username: str
    avatar_url: str
    email: str | None
    access_token: str


class UserOut(BaseModel):
    id: int
    github_id: str
    username: str
    avatar_url: str
    email: str | None
    notification_email: str | None
    plan: str
    max_tracked_repos: int

    model_config = {"from_attributes": True}


class UserMePatch(BaseModel):
    notification_email: str | None


@router.post("/upsert", response_model=UserOut)
def upsert_user(payload: UserUpsert, db: Session = Depends(get_db)) -> User:
    user = db.execute(select(User).where(User.github_id == payload.github_id)).scalars().first()
    encrypted = encrypt_token(payload.access_token)

    if user is None:
        user = User(
            github_id=payload.github_id,
            username=payload.username,
            avatar_url=payload.avatar_url,
            email=payload.email,
            access_token_encrypted=encrypted,
        )
        db.add(user)
    else:
        user.username = payload.username
        user.avatar_url = payload.avatar_url
        user.email = payload.email
        user.access_token_encrypted = encrypted

    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(require_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserMePatch, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> User:
    # Empty string means "clear the fallback" — must actually become NULL,
    # not get stored as a literal empty string (which _recipient() in
    # app/notifications.py would otherwise treat as a truthy-but-invalid address).
    current_user.notification_email = payload.notification_email or None
    db.commit()
    db.refresh(current_user)
    broadcaster.publish("user_updated", {}, user_id=current_user.id)
    return current_user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_users_api.py -v`
Expected: all pass (existing 3 + 6 new).

Then run the full backend suite one more time:

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all pass, pristine output.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/users.py backend/tests/test_users_api.py
git commit -m "feat(4e): add GET/PATCH /users/me + user_updated SSE event"
```

---

### Task 7: Frontend types, API client, hook, SSE mapping

**Files:**
- Modify: `frontend/lib/query-keys.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/hooks/use-live-events.ts`
- Create: `frontend/app/api/users/me/route.ts`
- Create: `frontend/hooks/use-me.ts`
- Test: `frontend/tests/use-live-events.test.ts` (extend if it exists; otherwise check `frontend/tests/` for the closest existing SSE-mapping test and extend that)

**Interfaces:**
- Consumes: `backendFetch`/`fetchJson` (existing `lib/backend-client.ts`/`lib/fetch-json.ts`), `UserOut` type (regenerated from the backend's live OpenAPI schema — now includes `notification_email` from Task 6).
- Produces: `queryKeys.users.me`, `api.getMe()`, `api.updateMe(payload)`, `useMe()`, `useUpdateMe()`. Consumed by `NotificationSettingsCard` (Task 8).

- [ ] **Step 1: Regenerate OpenAPI types**

Start the local backend so its live OpenAPI schema reflects Task 6's new endpoints:

Run (from `backend/`): `.venv/bin/uvicorn app.main:app --reload &` (background it, or run in a separate terminal)

Then, from `frontend/`:

Run: `npm run generate:types`

Expected: `frontend/types/api.d.ts` regenerates, now including `notification_email` on the `UserOut` schema and the new `/users/me` paths. Confirm with:

Run: `grep -n "notification_email" frontend/types/api.d.ts`
Expected: at least one match.

Stop the background `uvicorn` process before continuing (it was only needed to serve the OpenAPI schema for this one command).

- [ ] **Step 2: Add the query key**

In `frontend/lib/query-keys.ts`, add a new top-level entry (after the existing `providers` entry):

```ts
  users: {
    me: ["users", "me"] as const,
  },
```

- [ ] **Step 3: Add `api.getMe`/`api.updateMe`**

In `frontend/lib/api.ts`, find the existing `upsertUser` method and add these two new methods immediately after it (matching the file's existing method style — check the exact surrounding syntax before editing, since methods are comma-separated properties of one `export const api = { ... }` object, not standalone functions):

```ts
  getMe: () => backendFetch<UserOut>("/users/me"),
  updateMe: (payload: { notification_email: string | null }) =>
    backendFetch<UserOut>("/users/me", { method: "PATCH", body: JSON.stringify(payload) }),
```

(`UserOut` is already imported in this file per the existing `upsertUser` method's return type — confirm the import line includes it; if not, add it to the existing `import type { ... } from "@/lib/api-types"` line.)

- [ ] **Step 4: Add the `user_updated` SSE mapping**

In `frontend/hooks/use-live-events.ts`, add one entry to `EVENT_QUERY_MAP` (after the existing `drafts_generated` entry):

```ts
  user_updated: [queryKeys.users.me],
```

- [ ] **Step 5: Create the Route Handler**

Create `frontend/app/api/users/me/route.ts`:

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET() {
  return proxyRoute(() => api.getMe());
}

export async function PATCH(request: Request) {
  const payload = (await request.json()) as { notification_email: string | null };
  return proxyRoute(() => api.updateMe(payload));
}
```

- [ ] **Step 6: Create the `useMe`/`useUpdateMe` hook**

Create `frontend/hooks/use-me.ts`:

```ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { UserOut } from "@/lib/api-types";

export function useMe() {
  return useQuery({
    queryKey: queryKeys.users.me,
    queryFn: () => fetchJson<UserOut>("/api/users/me"),
  });
}

export function useUpdateMe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { notification_email: string | null }) =>
      fetchJson<UserOut>("/api/users/me", { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.users.me, updated);
    },
  });
}
```

(Check `frontend/lib/api-types.ts` — `UserOut` is already exported there per the existing `export type UserOut = components["schemas"]["UserOut"];` line; Task 7 Step 1's regeneration means it now includes `notification_email`, no manual edit to `api-types.ts` needed.)

- [ ] **Step 7: Write the SSE-mapping test**

First check whether an existing test already asserts on `EVENT_QUERY_MAP` contents (search `frontend/tests/*.test.ts*` for `EVENT_QUERY_MAP` or `drafts_generated`). If one exists, add a case to it:

```ts
it("maps user_updated to the users.me query key", () => {
  expect(EVENT_QUERY_MAP.user_updated).toEqual([queryKeys.users.me]);
});
```

If no such test file/pattern exists yet, create `frontend/tests/use-live-events.test.ts` following whatever testing-library/vitest setup pattern the other files in `frontend/tests/` use (check one, e.g. the hooks test closest to this one in shape, before writing setup boilerplate) and add the assertion above alongside a minimal existing-mapping sanity check (e.g. `run_completed` maps to the 3 keys it already maps to) so the new test file isn't trivially vacuous.

- [ ] **Step 8: Run tests, typecheck, lint**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npx eslint .`
Expected: all pass, zero errors/warnings.

- [ ] **Step 9: Commit**

```bash
git add frontend/types/api.d.ts frontend/lib/query-keys.ts frontend/lib/api.ts frontend/hooks/use-live-events.ts frontend/app/api/users/me/route.ts frontend/hooks/use-me.ts frontend/tests/
git commit -m "feat(4e): add users/me API client, hook, SSE mapping"
```

---

### Task 8: `NotificationSettingsCard` + Settings page wiring

**Files:**
- Create: `frontend/components/settings/notification-settings-card.tsx`
- Modify: `frontend/components/settings/settings-client.tsx`
- Modify: `frontend/app/settings/page.tsx`
- Test: `frontend/tests/notification-settings-card.test.tsx`

**Interfaces:**
- Consumes: `useMe`, `useUpdateMe` (Task 7).
- Produces: `<NotificationSettingsCard />`, rendered inside `SettingsClient`.

- [ ] **Step 1: Write the failing test**

First check `frontend/tests/` for an existing component test (e.g. whatever tests `draft-content.tsx` or another `components/settings/*`/`components/drafts/*` component) to match its exact render/mock setup (how `useMe`/`useUpdateMe`-equivalent hooks get mocked, how `QueryClientProvider` wrapping is done if needed). Then create `frontend/tests/notification-settings-card.test.tsx` following that same pattern, with these cases:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { NotificationSettingsCard } from "@/components/settings/notification-settings-card";
import * as useMeModule from "@/hooks/use-me";

describe("NotificationSettingsCard", () => {
  it("shows the GitHub email as the effective recipient when no fallback is set", () => {
    vi.spyOn(useMeModule, "useMe").mockReturnValue({
      data: { id: 1, github_id: "1", username: "octocat", avatar_url: "", email: "gh@example.com", notification_email: null, plan: "free", max_tracked_repos: 5 },
    } as ReturnType<typeof useMeModule.useMe>);
    vi.spyOn(useMeModule, "useUpdateMe").mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useMeModule.useUpdateMe>);

    render(<NotificationSettingsCard />);

    expect(screen.getByText("gh@example.com")).toBeInTheDocument();
  });

  it("shows a fallback-not-set message when neither email exists", () => {
    vi.spyOn(useMeModule, "useMe").mockReturnValue({
      data: { id: 1, github_id: "1", username: "octocat", avatar_url: "", email: null, notification_email: null, plan: "free", max_tracked_repos: 5 },
    } as ReturnType<typeof useMeModule.useMe>);
    vi.spyOn(useMeModule, "useUpdateMe").mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useMeModule.useUpdateMe>);

    render(<NotificationSettingsCard />);

    expect(screen.getByText("No email on file")).toBeInTheDocument();
  });

  it("calls updateMe with the trimmed input value on save", () => {
    const mutate = vi.fn();
    vi.spyOn(useMeModule, "useMe").mockReturnValue({
      data: { id: 1, github_id: "1", username: "octocat", avatar_url: "", email: "gh@example.com", notification_email: null, plan: "free", max_tracked_repos: 5 },
    } as ReturnType<typeof useMeModule.useMe>);
    vi.spyOn(useMeModule, "useUpdateMe").mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof useMeModule.useUpdateMe>);

    render(<NotificationSettingsCard />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "  fallback@example.com  " } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(mutate).toHaveBeenCalledWith(
      { notification_email: "fallback@example.com" },
      expect.objectContaining({ onError: expect.any(Function) })
    );
  });
});
```

Adjust the exact mock shape/import style to match whatever convention the nearest existing component test in `frontend/tests/` actually uses (e.g. some projects mock the whole hook module differently than `vi.spyOn` — check one real file first rather than assuming).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/notification-settings-card.test.tsx`
Expected: FAIL — module `@/components/settings/notification-settings-card` not found.

- [ ] **Step 3: Implement `NotificationSettingsCard`**

Create `frontend/components/settings/notification-settings-card.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Mail } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SectionHeading } from "@/components/ui/section-heading";
import { useMe, useUpdateMe } from "@/hooks/use-me";

export function NotificationSettingsCard() {
  const { data: me } = useMe();
  const updateMe = useUpdateMe();
  const [value, setValue] = useState(me?.notification_email ?? "");

  const effectiveEmail = me?.notification_email || me?.email || "No email on file";

  const handleSave = () => {
    const trimmed = value.trim();
    updateMe.mutate(
      { notification_email: trimmed || null },
      { onError: () => toast.error("Could not update notification email — try again.") }
    );
  };

  return (
    <div className="space-y-3">
      <SectionHeading icon={Mail} title="Notifications" iconColor="text-amber-500" />
      <Card>
        <CardContent className="space-y-3 py-4">
          <p className="text-sm text-muted-foreground">
            Alert emails currently go to: <span className="font-medium">{effectiveEmail}</span>
          </p>
          <div className="flex items-center gap-2">
            <Input
              type="email"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="fallback-email@example.com"
              aria-label="Notification fallback email"
            />
            <Button onClick={handleSave} disabled={updateMe.isPending}>
              Save
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

`components/ui/input.tsx` already exists (a `@base-ui/react/input` wrapper) — used here instead of a raw `<input>` to stay consistent with the rest of the design system, matching `AddRepoDialog`'s existing usage of the same primitive.

- [ ] **Step 4: Wire into `SettingsClient`**

In `frontend/components/settings/settings-client.tsx`, add the import and render the new card after `<ProviderStatusTable />`:

```tsx
import { NotificationSettingsCard } from "@/components/settings/notification-settings-card";
```

```tsx
      <ProviderStatusTable />

      <NotificationSettingsCard />
```

- [ ] **Step 5: Prefetch `getMe` in `settings/page.tsx`**

In `frontend/app/settings/page.tsx`, extend the existing parallel prefetch:

```tsx
import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { SettingsClient } from "@/components/settings/settings-client";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const queryClient = new QueryClient();

  const [repos, providerStatus, me] = await Promise.all([
    api.listRepos(),
    api.providerStatus(),
    api.getMe(),
  ]);
  queryClient.setQueryData(queryKeys.repos.all, repos);
  queryClient.setQueryData(queryKeys.providers.status, providerStatus);
  queryClient.setQueryData(queryKeys.users.me, me);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <SettingsClient />
    </HydrationBoundary>
  );
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd frontend && npx vitest run`
Expected: all pass, including the 3 new `NotificationSettingsCard` tests.

Then the full frontend verification:

Run: `cd frontend && npx tsc --noEmit && npx eslint . && npx next build`
Expected: all clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/settings/notification-settings-card.tsx frontend/components/settings/settings-client.tsx frontend/app/settings/page.tsx frontend/tests/notification-settings-card.test.tsx
git commit -m "feat(4e): add Notifications settings card, wire into Settings page"
```

---

## Final whole-branch review

After all 8 tasks: dispatch a final whole-branch code reviewer (opus, per this project's established pattern for every prior sub-project) covering the full diff since this plan's first commit. Confirm: backend full suite passes with no warnings, `pip-audit` clean; frontend `tsc`/`eslint`/`vitest`/`next build` all clean; `notify=False` default genuinely never regresses any existing manual-trigger test; no secret (Resend key, `EMAIL_FROM`) ever appears in a log statement, test fixture, or committed file. Then update `.agile-v/REQUIREMENTS.md` (new REQ), `.agile-v/STATE.md`, `docs/PROJECT_PLAN.md` (mark 4E done), and `docs/PROJECT_WALKTHROUGH.md` before the Product Owner's Gate 2 review — same sequence as every prior sub-project.
