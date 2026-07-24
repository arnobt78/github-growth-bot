from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Fallback alert-email recipient when `email` (derived from GitHub OAuth
    # scope, not guaranteed present) is empty. Settings page lets the user
    # set/clear this directly — see app/api/users.py's GET/PATCH /users/me.
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Rate-limit guard for the needs_reauth alert email: null means "never
    # sent (or eligible to send again)". needs_reauth persists until the user
    # reconnects GitHub, so without this the daily scheduler would re-email
    # the same unresolved condition every single day.
    last_reauth_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Fernet ciphertext of the user's GitHub OAuth access token. Never logged,
    # never returned by any API response — see app/token_crypto.py.
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    max_tracked_repos: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    owner: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    tracked_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Last release tag_name we've already generated (or attempted to generate)
    # release notes for. Null means "never checked" — the repo's current
    # latest release, even if it predates tracking, still gets a Draft the
    # first time the content pipeline runs for it. Only advances when a Draft
    # was actually written (see ContentAssembler) — a transient LLM outage
    # must not permanently skip a release.
    last_release_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    watchers: Mapped[int] = mapped_column(Integer, default=0)
    open_issues: Mapped[int] = mapped_column(Integer, default=0)
    views_14d: Mapped[int] = mapped_column(Integer, default=0)
    unique_views_14d: Mapped[int] = mapped_column(Integer, default=0)
    clones_14d: Mapped[int] = mapped_column(Integer, default=0)
    unique_clones_14d: Mapped[int] = mapped_column(Integer, default=0)


class BenchmarkRepo(Base):
    __tablename__ = "benchmark_repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    full_name: Mapped[str] = mapped_column(String(255))
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Referrer(Base):
    __tablename__ = "referrers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    referrer: Mapped[str] = mapped_column(String(255))
    count: Mapped[int] = mapped_column(Integer, default=0)
    uniques: Mapped[int] = mapped_column(Integer, default=0)


class PopularPath(Base):
    __tablename__ = "popular_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    path: Mapped[str] = mapped_column(String(500))
    count: Mapped[int] = mapped_column(Integer, default=0)
    uniques: Mapped[int] = mapped_column(Integer, default=0)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running")
    pipeline_kind: Mapped[str] = mapped_column(String(50), default="analytics")


class StageRun(Base):
    __tablename__ = "stage_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    pipeline_run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"))
    stage_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"))
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=True)
    category: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    repo_id: Mapped[int | None] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(255))
    content: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    date: Mapped[date] = mapped_column(Date)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
