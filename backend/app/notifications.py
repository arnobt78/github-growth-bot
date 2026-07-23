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
    last = user.last_reauth_notified_at
    if last is not None:
        # SQLite (test DB) returns DateTime(timezone=True) columns as naive,
        # while Postgres (prod) keeps them tz-aware — same gotcha documented
        # in app/api/drafts.py. Values are always written as UTC (see below),
        # so a naive read is interpreted as UTC rather than compared raw.
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last < REAUTH_COOLDOWN:
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
