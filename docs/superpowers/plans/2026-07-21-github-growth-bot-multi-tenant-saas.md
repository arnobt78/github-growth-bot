# Multi-Tenant SaaS Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single-tenant GitHub Growth Bot into a real multi-tenant SaaS: anyone signs in with their own GitHub account (Auth.js/NextAuth v5) and tracks their own repos, fully isolated from every other user's data, with no reduction in the existing security/performance bar.

**Architecture:** Auth.js (GitHub OAuth, JWT session, no DB adapter) protects every page via `proxy.ts`. Every backend call still flows through Next.js Route Handlers (unchanged files — the auth-awareness is centralized in `lib/backend-client.ts`, not spread across 13 route files). The backend gains a `User` table, `user_id` on every existing table, a `require_user` dependency verifying a short-lived HMAC-signed internal token, and per-user scoping on every query.

**Tech Stack:** Auth.js (NextAuth) v5, `cryptography` (Fernet) for OAuth-token-at-rest encryption, stdlib `hmac`/`hashlib` for the internal token (no JWT library needed — it's a single custom claim, not a general-purpose JWT), `slowapi` for rate limiting, FastAPI `BackgroundTasks` for async pipeline triggers.

## Global Constraints

- Full design: `docs/superpowers/specs/2026-07-21-multi-tenant-saas-design.md`. Every task's requirements implicitly include that spec.
- **Public-repo OAuth scope only** (`read:user public_repo`) — no `repo` scope, no private-repo tracking in this phase.
- **Free tier only** — no billing/Stripe. `plan` (default `"free"`) and `max_tracked_repos` (default `5`) columns ship now so a future billing phase is a config change, not a migration.
- **Defense in depth, exactly as specified**: Auth.js session → signed internal token (60s TTL) → existing `require_api_key` (unchanged) → new `require_user` → per-`user_id` query filtering. Never skip a layer as an optimization.
- **Never leak existence via status code** — fetching another user's resource by id returns 404, not 403.
- OAuth tokens: encrypted at rest (Fernet), never logged, never returned by any API response, never sent to the browser.
- **SSR data-fetching stays in `page.tsx`; only genuinely interactive code in `use client` components.** `force-dynamic` + parallel `Promise.all` prefetch is unchanged by this plan — no page task in this plan touches that pattern, because the auth-awareness is centralized in `lib/backend-client.ts` (Tasks 12-13), not spread across every page.
- **No `loading.tsx` anywhere.** No new page in this plan needs one — the sign-in page has no async data to await.
- Strict TypeScript throughout; every new type lives in the same file as what it types unless shared (matching existing `lib/api-types.ts` convention).
- TDD throughout on the backend (`backend/tests/`, one file per module, following existing naming). Full suite: `.venv/bin/python -m pytest -v`, must stay 100% pass, no stray warnings.
- Code comments only where they explain *why*, matching this repo's existing style — no prose-explanation blocks, no new summary `.md` files.
- Every title/label/button in new UI carries a `lucide-react` icon with semantic color, matching existing convention (e.g. `nav-sidebar.tsx`'s `color` field per item).
- **This Next.js version renamed `middleware.ts` to `proxy.ts`** (confirmed via `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md` — Next.js v16.0.0 change). Use `proxy.ts` at the project root, exported function/re-export named `proxy`, not `middleware`. Proxy runs on the Node.js runtime by default in this version (no Edge Runtime concerns).
- Auth.js v5 is current-latest as `5.0.0-beta.32` (checked via `npm view next-auth versions` on 2026-07-21) — pin exactly, this is the actively-recommended release channel for v5, not a stale beta.

---

### Task 1: `User` model, per-user FKs, Alembic migrations, backfill script

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/<new>_add_users_table_and_user_id_fks.py` (nullable phase)
- Create: `backend/alembic/versions/<new2>_enforce_user_id_not_null.py` (not-null phase, chained after the first)
- Create: `backend/scripts/backfill_owner_user.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py` (extend), plus fix every existing test that constructs `Repo`/`Snapshot`/etc. directly without `user_id`

**Interfaces:**
- Consumes: existing `Base` (`app/db.py`), existing 8 models (`app/models.py`).
- Produces: `User` model (`id`, `github_id: str` unique indexed, `username: str`, `avatar_url: str`, `email: str | None`, `access_token_encrypted: str`, `plan: str` default `"free"`, `max_tracked_repos: int` default `5`, `created_at: datetime`). Every existing table gets `user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))` (NOT NULL in `models.py` — tests use `Base.metadata.create_all()`, never run migrations, so `models.py` reflects the final desired state directly). Later tasks import `from app.models import User`.

**Why two migrations:** production Postgres may already have rows in these 8 tables (this project isn't deployed yet, but the migration must still be written correctly for when it is — see spec §3). Migration 1 adds `users` + `user_id` as **nullable** FKs (safe against existing rows). The backfill script assigns pre-existing rows to one designated user. Migration 2 then enforces `NOT NULL`. `models.py` itself declares `user_id` as NOT NULL throughout, since it describes the schema's final state, not the migration path.

- [ ] **Step 1: Write the failing model test**

```python
# backend/tests/test_models.py — add to existing file
from app.models import User


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
```

(Check the top of `test_models.py` for its existing imports — add `User` to whatever it already imports from `app.models`, and confirm `SessionLocal`/`Repo` are already imported there; if not, add `from app.db import SessionLocal` and `from app.models import Repo` alongside.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py::test_create_user_and_scoped_repo -v`
Expected: FAIL with `ImportError: cannot import name 'User' from 'app.models'` (or `AttributeError` if `Repo` doesn't yet accept `user_id`).

- [ ] **Step 3: Add the `User` model and `user_id` FKs to every existing table**

```python
# backend/app/models.py — full replacement
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
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


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    date: Mapped[date] = mapped_column(Date)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
```

Note: `LLMUsage` deliberately does NOT get a `user_id` — it tracks the app's own shared LLM provider budget (global infrastructure cost), not per-user data. `StageRun.pipeline_run_id` keeps its existing plain FK (no `ondelete="CASCADE"`), matching the deliberate choice already made in migration `978cdad75b7b` — `StageRun` rows gain `user_id` for query-scoping convenience only (so `require_user`-gated endpoints can filter stage lookups without an extra join), not for cascade-delete semantics.

- [ ] **Step 4: Run the full suite and fix every `NOT NULL constraint failed` error**

Run: `cd backend && .venv/bin/python -m pytest -v 2>&1 | tail -80`

Expected: many failures — every test that constructs `Repo(...)`, `Snapshot(...)`, `PipelineRun(...)`, etc. directly (not via a `client.post(...)` API call) now fails `NOT NULL constraint failed: repos.user_id` (or the equivalent for other tables). This is expected and by design — go through each failing test file, seed a `User` row at the top of the failing test/fixture (or reuse one already seeded in that file), and pass `user_id=<that user's id>` to every direct model constructor call. Do this file-by-file until the full suite is green except for tests this plan's later tasks are explicitly meant to fix (there should be none yet at this point in Task 1 — every failure here must be resolved before moving on).

- [ ] **Step 5: Update `conftest.py`'s shared fixtures to seed a real user and attach a valid internal token**

This step's code depends on `app/token_crypto.py` and `app/internal_auth.py`, which don't exist until Task 2. **Do not write this step's code yet** — Task 1 ends here with the `User` model in place and every direct-construction test fixed to pass a raw `user_id` (using a plain seeded `User` row, no encryption/token concerns yet). Task 2 replaces `conftest.py` wholesale once the encryption/token modules exist, so leave a one-line TODO-free placeholder: for now, add a tiny local helper directly in `conftest.py` for Step 4's fixes to use:

```python
# backend/tests/conftest.py — add this fixture, keep everything else in the file as-is for now
@pytest.fixture
def seed_user():
    from app.db import SessionLocal
    from app.models import User

    db = SessionLocal()
    user = User(
        github_id="12345",
        username="octocat",
        avatar_url="https://avatars.githubusercontent.com/u/12345",
        email="octocat@example.com",
        access_token_encrypted="placeholder-ciphertext",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    return user_id
```

Use `seed_user` in every test/fixture from Step 4 that needs a `user_id` to satisfy the new NOT NULL constraint. This fixture gets replaced by a real encrypted-token version in Task 2 — that's expected, not a contradiction.

- [ ] **Step 6: Run the full suite, verify green**

Run: `cd backend && .venv/bin/python -m pytest -v 2>&1 | tail -20`
Expected: all tests pass, including the new `test_create_user_and_scoped_repo`.

- [ ] **Step 7: Write the Alembic migration (nullable phase)**

Run: `cd backend && .venv/bin/alembic revision -m "add users table and user_id fks"` and note the generated revision id (call it `<REV1>` below — replace with the real generated hex id). Then edit the generated file to read:

```python
"""add users table and user_id fks

Revision ID: <REV1>
Revises: 978cdad75b7b
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '<REV1>'
down_revision: Union[str, None] = '978cdad75b7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES_GAINING_USER_ID = [
    "repos",
    "snapshots",
    "benchmark_repos",
    "referrers",
    "popular_paths",
    "pipeline_runs",
    "stage_runs",
    "recommendations",
]


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('github_id', sa.String(length=64), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('avatar_url', sa.String(length=500), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('access_token_encrypted', sa.Text(), nullable=False),
        sa.Column('plan', sa.String(length=50), nullable=False, server_default='free'),
        sa.Column('max_tracked_repos', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_github_id', 'users', ['github_id'], unique=True)

    # Nullable for now — existing rows (if any, on a real deployed DB) have no
    # owning user yet. backend/scripts/backfill_owner_user.py assigns them to
    # one designated account; a follow-up migration then enforces NOT NULL.
    for table in TABLES_GAINING_USER_ID:
        op.add_column(table, sa.Column('user_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            f'{table}_user_id_fkey', table, 'users', ['user_id'], ['id'], ondelete='CASCADE'
        )


def downgrade() -> None:
    for table in TABLES_GAINING_USER_ID:
        op.drop_constraint(f'{table}_user_id_fkey', table, type_='foreignkey')
        op.drop_column(table, 'user_id')
    op.drop_index('ix_users_github_id', table_name='users')
    op.drop_table('users')
```

- [ ] **Step 8: Write the backfill script**

```python
# backend/scripts/backfill_owner_user.py
"""One-time, manually-run script for the real deployed Postgres database only.

Run after: (1) migration <REV1> has been applied, (2) the Product Owner has
signed in once via the live app (creating their User row through
POST /users/upsert). This script assigns every pre-existing row across the
8 tables in TABLES_GAINING_USER_ID to that one account, so no history from
before the multi-tenant migration is orphaned or lost.

Usage: .venv/bin/python -m scripts.backfill_owner_user --github-id <id>
"""
import argparse

from app.db import SessionLocal
from app.models import (
    BenchmarkRepo,
    PipelineRun,
    PopularPath,
    Recommendation,
    Referrer,
    Repo,
    Snapshot,
    StageRun,
    User,
)

TABLES = [Repo, Snapshot, BenchmarkRepo, Referrer, PopularPath, PipelineRun, StageRun, Recommendation]


def backfill(github_id: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.github_id == github_id).one_or_none()
        if user is None:
            raise SystemExit(
                f"No User row with github_id={github_id!r} — sign in via the live app first."
            )

        for model in TABLES:
            updated = (
                db.query(model)
                .filter(model.user_id.is_(None))
                .update({"user_id": user.id}, synchronize_session=False)
            )
            print(f"{model.__tablename__}: backfilled {updated} row(s) to user_id={user.id}")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-id", required=True, help="GitHub numeric user id to assign orphaned rows to")
    args = parser.parse_args()
    backfill(args.github_id)
```

- [ ] **Step 9: Write the second migration (enforce NOT NULL)**

Run: `cd backend && .venv/bin/alembic revision -m "enforce user_id not null"` and note the generated revision id (`<REV2>`).

```python
"""enforce user_id not null

Revision ID: <REV2>
Revises: <REV1>
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '<REV2>'
down_revision: Union[str, None] = '<REV1>'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES_WITH_USER_ID = [
    "repos",
    "snapshots",
    "benchmark_repos",
    "referrers",
    "popular_paths",
    "pipeline_runs",
    "stage_runs",
    "recommendations",
]


def upgrade() -> None:
    # Run backend/scripts/backfill_owner_user.py against the target database
    # BEFORE applying this migration — it will fail with a NOT NULL violation
    # on any table that still has un-backfilled rows.
    for table in TABLES_WITH_USER_ID:
        op.alter_column(table, 'user_id', existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    for table in TABLES_WITH_USER_ID:
        op.alter_column(table, 'user_id', existing_type=sa.Integer(), nullable=True)
```

- [ ] **Step 10: Commit**

```bash
cd backend
git add app/models.py alembic/versions/ scripts/backfill_owner_user.py tests/
git commit -m "feat(backend): add User model, per-user FKs on all tables, backfill script"
```

---

### Task 2: Token encryption, internal auth token, updated test fixtures

**Files:**
- Create: `backend/app/token_crypto.py`
- Create: `backend/app/internal_auth.py`
- Modify: `backend/app/config.py`
- Modify: `backend/tests/conftest.py` (replaces the `seed_user` placeholder from Task 1 with the real fixtures below)
- Test: `backend/tests/test_token_crypto.py`, `backend/tests/test_internal_auth.py`

**Interfaces:**
- Consumes: `Settings` (`app/config.py`), `User` model (Task 1).
- Produces: `encrypt_token(plaintext: str) -> str`, `decrypt_token(ciphertext: str) -> str` (`app/token_crypto.py`); `mint_internal_user_token(github_id: str) -> str`, `verify_internal_user_token(token: str) -> str` (`app/internal_auth.py`, raises `ValueError` on any failure). Later tasks (`deps.py`'s `require_user`) call `verify_internal_user_token`. The `client`/`other_user_client` fixtures this task builds are consumed by every subsequent per-user-scoping task's tests.

**Token format (must match the frontend's `lib/internal-auth.ts` from Task 13 exactly):** `f"{payload_b64}.{signature_hex}"` where `payload_b64` is URL-safe-base64 (unpadded) of `json.dumps({"sub": github_id, "exp": <unix_seconds>})`, and `signature_hex` is `HMAC-SHA256(payload_b64, INTERNAL_AUTH_SECRET)` as lowercase hex. TTL: 60 seconds.

- [ ] **Step 1: Write the failing token-crypto test**

```python
# backend/tests/test_token_crypto.py
from app.token_crypto import decrypt_token, encrypt_token


def test_encrypt_decrypt_round_trip():
    plaintext = "gho_realGitHubOAuthTokenValue"
    ciphertext = encrypt_token(plaintext)
    assert ciphertext != plaintext
    assert decrypt_token(ciphertext) == plaintext
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_token_crypto.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.token_crypto'`

- [ ] **Step 3: Add `TOKEN_ENCRYPTION_KEY`/`INTERNAL_AUTH_SECRET` to settings**

```python
# backend/app/config.py — full replacement
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    api_key: str
    github_token: str

    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    huggingface_api_key: str = ""
    cloudflare_api_key: str = ""
    cloudflare_account_id: str = ""
    vercel_ai_gateway_key: str = ""

    cors_origins: list[str] = []

    # Multi-tenant SaaS foundation (Phase 2)
    token_encryption_key: str = ""
    internal_auth_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Implement `token_crypto.py`**

```python
# backend/app/token_crypto.py
from cryptography.fernet import Fernet

from app.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.token_encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
```

Add `cryptography==49.0.0` to `backend/requirements.txt`, then run `cd backend && .venv/bin/pip install -r requirements.txt`.

- [ ] **Step 5: Add `TOKEN_ENCRYPTION_KEY` to test env and `.env.example`, run test**

```python
# backend/tests/conftest.py — add near the top, alongside the other os.environ.setdefault calls
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "zTgP1kM3vXG9wQeYrT6uI0oP2aS4dF7gH9jK1lN3mB8=")
os.environ.setdefault("INTERNAL_AUTH_SECRET", "test-only-internal-secret-do-not-use-in-prod")
```

(The `TOKEN_ENCRYPTION_KEY` value above is a real, valid Fernet key — 32 url-safe-base64-encoded bytes — hardcoded for test-only reproducibility; production generates its own via `Fernet.generate_key()` and stores it in Coolify env, never committed.)

```bash
# backend/.env.example — add these two lines
TOKEN_ENCRYPTION_KEY=
INTERNAL_AUTH_SECRET=
```

Run: `cd backend && .venv/bin/python -m pytest tests/test_token_crypto.py -v`
Expected: PASS

- [ ] **Step 6: Write the failing internal-auth test**

```python
# backend/tests/test_internal_auth.py
import time

import pytest

from app.internal_auth import mint_internal_user_token, verify_internal_user_token


def test_mint_and_verify_round_trip():
    token = mint_internal_user_token("12345")
    assert verify_internal_user_token(token) == "12345"


def test_verify_rejects_tampered_signature():
    token = mint_internal_user_token("12345")
    payload_b64, _sig = token.rsplit(".", 1)
    tampered = f"{payload_b64}.deadbeef"
    with pytest.raises(ValueError):
        verify_internal_user_token(tampered)


def test_verify_rejects_expired_token(monkeypatch):
    token = mint_internal_user_token("12345")
    # simulate 61 seconds passing (token TTL is 60s)
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 61)
    with pytest.raises(ValueError):
        verify_internal_user_token(token)
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_internal_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.internal_auth'`

- [ ] **Step 8: Implement `internal_auth.py`**

```python
# backend/app/internal_auth.py
import base64
import hashlib
import hmac
import json
import time

from app.config import get_settings

TOKEN_TTL_SECONDS = 60


def _sign(payload_b64: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.internal_auth_secret.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()


def mint_internal_user_token(github_id: str) -> str:
    """Backend-side minting exists only so tests can construct valid tokens
    without duplicating the HMAC scheme inline. Production tokens are minted
    by the frontend (frontend/lib/internal-auth.ts), server-side, from a
    verified Auth.js session — never by the browser."""
    payload = json.dumps({"sub": github_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS})
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode()
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_internal_user_token(token: str) -> str:
    try:
        payload_b64, signature_hex = token.rsplit(".", 1)
    except ValueError:
        raise ValueError("Malformed internal token")

    if not hmac.compare_digest(_sign(payload_b64), signature_hex):
        raise ValueError("Invalid internal token signature")

    padding = "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
    if payload["exp"] < time.time():
        raise ValueError("Expired internal token")
    return str(payload["sub"])
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_internal_auth.py -v`
Expected: 3 passed

- [ ] **Step 10: Replace `conftest.py`'s fixtures with the real encrypted-token versions**

```python
# backend/tests/conftest.py — full replacement
import os
import pytest
import tempfile

_test_db_dir = tempfile.mkdtemp()
_test_db_path = os.path.join(_test_db_dir, "test.db")

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_test_db_path}")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "zTgP1kM3vXG9wQeYrT6uI0oP2aS4dF7gH9jK1lN3mB8=")
os.environ.setdefault("INTERNAL_AUTH_SECRET", "test-only-internal-secret-do-not-use-in-prod")


@pytest.fixture(autouse=True)
def _reset_db():
    from app.db import Base, engine
    import app.models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
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
```

Note: `other_user_client` calls `_create_user` directly rather than depending on the `seed_user` fixture, since a test using both `client` and `other_user_client` together needs two distinct users, not one shared one.

- [ ] **Step 11: Run the full suite, fix any test still relying on the Task-1 placeholder `seed_user` shape**

Run: `cd backend && .venv/bin/python -m pytest -v 2>&1 | tail -60`

Task 1's temporary `seed_user` fixture returned a bare `user_id` from a plaintext-`access_token_encrypted` user; this task's version does the same (still returns `int`), so tests written against Task 1's version should keep working unchanged. If any fail, it's almost certainly because a test asserts on `client`'s user having `github_id="12345"` — this task keeps that value, so it should already match.

Expected: all tests pass.

- [ ] **Step 12: Commit**

```bash
cd backend
git add app/token_crypto.py app/internal_auth.py app/config.py tests/ requirements.txt .env.example
git commit -m "feat(backend): Fernet token encryption, HMAC-signed internal auth token"
```

---

### Task 3: `require_user` dependency, `POST /users/upsert`

**Files:**
- Modify: `backend/app/deps.py`
- Create: `backend/app/api/users.py`
- Modify: `backend/app/main.py` (register the new router)
- Test: `backend/tests/test_require_user.py`, `backend/tests/test_users_api.py`

**Interfaces:**
- Consumes: `verify_internal_user_token` (Task 2), `User` model (Task 1).
- Produces: `require_user(x_internal_user_token: str = Header(...), db: Session = Depends(get_db)) -> User` in `app/deps.py` — every subsequent task's endpoints add `current_user: User = Depends(require_user)` as a parameter. `POST /users/upsert` — the one endpoint gated by `require_api_key` only (no `require_user`, since the User row doesn't exist yet on first sign-in).

- [ ] **Step 1: Write the failing `require_user` test**

```python
# backend/tests/test_require_user.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_require_user.py -v`
Expected: FAIL — `/repos` doesn't require a user token yet, so the first three tests get 200 instead of 401.

- [ ] **Step 3: Implement `require_user` in `deps.py`**

```python
# backend/app/deps.py — full replacement
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.internal_auth import verify_internal_user_token
from app.models import User


def require_api_key(authorization: str = Header(default="")) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.api_key}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def require_user(
    x_internal_user_token: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    if not x_internal_user_token:
        raise HTTPException(status_code=401, detail="Missing internal user token")

    try:
        github_id = verify_internal_user_token(x_internal_user_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    user = db.execute(select(User).where(User.github_id == github_id)).scalars().first()
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user
```

This doesn't make the new tests pass yet — `/repos` doesn't call `require_user` until Task 4. Leave `test_require_user.py` red for now; it'll go green once Task 4 wires `require_user` into `repos.py`. Confirm the failure mode is now specifically about `/repos` not enforcing it (not an import error):

Run: `cd backend && .venv/bin/python -m pytest tests/test_require_user.py -v`
Expected: same 3 failures as Step 2, no new errors.

- [ ] **Step 4: Write the failing `/users/upsert` test**

```python
# backend/tests/test_users_api.py
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
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_users_api.py -v`
Expected: FAIL with 404 (no `/users` route yet).

- [ ] **Step 6: Implement `app/api/users.py`**

```python
# backend/app/api/users.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
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
    plan: str
    max_tracked_repos: int

    model_config = {"from_attributes": True}


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
```

`UserOut` deliberately excludes `access_token_encrypted` and any raw token field — this response model IS the "never return the token" guarantee from the spec, enforced by Pydantic's `response_model` filtering rather than by convention alone.

- [ ] **Step 7: Register the router**

```python
# backend/app/main.py:1-31 — add the import and include_router call
from app.api.users import router as users_router
# ... (alongside the other router imports)

app.include_router(users_router)
# ... (alongside the other include_router calls, before events_router is fine)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_users_api.py -v`
Expected: 3 passed

- [ ] **Step 9: Commit**

```bash
cd backend
git add app/deps.py app/api/users.py app/main.py tests/
git commit -m "feat(backend): require_user dependency, POST /users/upsert"
```

---

### Task 4: Per-user scoping on `repos.py`, quota enforcement

**Files:**
- Modify: `backend/app/api/repos.py`
- Test: `backend/tests/test_repos_api.py` (extend — existing tests keep passing unchanged since `client` now carries a valid user context)

**Interfaces:**
- Consumes: `require_user` (Task 3), `User.max_tracked_repos`.
- Produces: `list_repos`/`create_repo`/`get_repo`/`delete_repo` all take `current_user: User = Depends(require_user)` and filter/set by `current_user.id`. Later tasks (`insights.py`, `recommendations.py`) rely on `Repo` rows always having a real `user_id` matching their owner.

- [ ] **Step 1: Write the failing cross-user isolation test**

```python
# backend/tests/test_repos_api.py — add to existing file
def test_repo_isolated_per_user(client, other_user_client):
    create_resp = client.post("/repos", json={"owner": "octocat", "name": "mine"})
    repo_id = create_resp.json()["id"]

    other_list = other_user_client.get("/repos")
    assert other_list.json() == []

    other_get = other_user_client.get(f"/repos/{repo_id}")
    assert other_get.status_code == 404

    other_delete = other_user_client.delete(f"/repos/{repo_id}")
    assert other_delete.status_code == 404


def test_repo_quota_enforced(client):
    from app.db import SessionLocal
    from app.models import User

    db = SessionLocal()
    user = db.query(User).filter(User.github_id == "12345").one()
    user.max_tracked_repos = 1
    db.commit()
    db.close()

    first = client.post("/repos", json={"owner": "octocat", "name": "one"})
    assert first.status_code == 201

    second = client.post("/repos", json={"owner": "octocat", "name": "two"})
    assert second.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_repos_api.py -v`
Expected: FAIL — `other_user_client` currently sees every repo (no scoping yet), quota isn't enforced.

- [ ] **Step 3: Rewrite `repos.py` with per-user scoping**

```python
# backend/app/api/repos.py — full replacement
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key, require_user
from app.events import broadcaster
from app.models import Repo, User

router = APIRouter(prefix="/repos", tags=["repos"], dependencies=[Depends(require_api_key)])


class RepoCreate(BaseModel):
    owner: str
    name: str


class RepoOut(BaseModel):
    id: int
    owner: str
    name: str
    tracked_since: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[RepoOut])
def list_repos(db: Session = Depends(get_db), current_user: User = Depends(require_user)) -> list[Repo]:
    return db.execute(select(Repo).where(Repo.user_id == current_user.id)).scalars().all()


@router.post("", response_model=RepoOut, status_code=201)
def create_repo(
    payload: RepoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> Repo:
    tracked_count = db.execute(
        select(func.count()).select_from(Repo).where(Repo.user_id == current_user.id)
    ).scalar_one()
    if tracked_count >= current_user.max_tracked_repos:
        raise HTTPException(
            status_code=403,
            detail=f"Repo limit reached ({current_user.max_tracked_repos} on the {current_user.plan} plan).",
        )

    repo = Repo(owner=payload.owner, name=payload.name, user_id=current_user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    broadcaster.publish("repo_added", {"id": repo.id}, user_id=current_user.id)
    return repo


@router.get("/{repo_id}", response_model=RepoOut)
def get_repo(
    repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> Repo:
    repo = db.execute(
        select(Repo).where(Repo.id == repo_id, Repo.user_id == current_user.id)
    ).scalars().first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo


@router.delete("/{repo_id}", status_code=204)
def delete_repo(
    repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> None:
    repo = db.execute(
        select(Repo).where(Repo.id == repo_id, Repo.user_id == current_user.id)
    ).scalars().first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    db.delete(repo)
    db.commit()
    broadcaster.publish("repo_removed", {"id": repo_id}, user_id=current_user.id)
```

This calls `broadcaster.publish(..., user_id=current_user.id)` — a signature that doesn't exist until Task 5. **Do not run the full suite yet** — this task's own tests only exercise `repos.py` in isolation; `broadcaster.publish` still accepts the 2-arg call today (Task 5 adds the required `user_id` kwarg), so passing it now as a kwarg will raise `TypeError: publish() got an unexpected keyword argument 'user_id'` until Task 5 lands. Order matters: **complete Task 5 (SSE per-user scoping) before running `repos.py`'s own tests from this task**, even though it's listed after Task 4 in this document — the two tasks have a real mutual dependency (Task 5's tests don't need anything from Task 4, but Task 4's tests need Task 5's `EventBroadcaster` signature), so execute Task 5 first despite the numbering.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_repos_api.py -v`
Expected: all pass, including the 2 new tests.

- [ ] **Step 5: Run the full suite**

Run: `cd backend && .venv/bin/python -m pytest -v 2>&1 | tail -40`
Expected: all green (assuming Task 10 has already landed per the note in Step 3 — if not yet, this is the expected, temporary failure point; resolve by completing Task 10 first).

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/api/repos.py tests/test_repos_api.py
git commit -m "feat(backend): per-user repo scoping and tracked-repo quota"
```

---

### Task 5: `EventBroadcaster` per-user scoping (do this before/alongside Task 4 per its note)

**Files:**
- Modify: `backend/app/events.py`
- Modify: `backend/app/api/events.py`
- Test: `backend/tests/test_events.py` (extend)

**Interfaces:**
- Consumes: `require_user` (Task 3).
- Produces: `EventBroadcaster.subscribe(user_id: int) -> asyncio.Queue`, `EventBroadcaster.publish(event_type: str, payload: dict, user_id: int) -> None`. Every router that calls `broadcaster.publish` (repos.py, recommendations.py, runs.py, jobs.py) must pass `user_id=` from here on.

- [ ] **Step 1: Write the failing per-user scoping test**

```python
# backend/tests/test_events.py — add to existing file
import asyncio

from app.events import EventBroadcaster


def test_publish_only_delivers_to_matching_user():
    broadcaster = EventBroadcaster()
    queue_a = broadcaster.subscribe(user_id=1)
    queue_b = broadcaster.subscribe(user_id=2)

    broadcaster.publish("repo_added", {"id": 42}, user_id=1)

    assert queue_a.get_nowait() == {"type": "repo_added", "payload": {"id": 42}}
    assert queue_b.empty()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_events.py::test_publish_only_delivers_to_matching_user -v`
Expected: FAIL — `subscribe()`/`publish()` don't accept `user_id` yet.

- [ ] **Step 3: Rewrite `events.py`**

```python
# backend/app/events.py
import asyncio
from typing import Any


class EventBroadcaster:
    def __init__(self) -> None:
        self._subscribers: list[tuple[int, asyncio.Queue]] = []

    def subscribe(self, user_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append((user_id, queue))
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers = [(uid, q) for uid, q in self._subscribers if q is not queue]

    def publish(self, event_type: str, payload: dict[str, Any], user_id: int) -> None:
        event = {"type": event_type, "payload": payload}
        for uid, queue in list(self._subscribers):
            if uid == user_id:
                queue.put_nowait(event)


broadcaster = EventBroadcaster()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_events.py -v`
Expected: all pass (the pre-existing `test_publish_delivers_to_subscriber` test needs updating too — see Step 5).

- [ ] **Step 5: Fix the pre-existing test's call signature**

Open `backend/tests/test_events.py` and update its existing `test_publish_delivers_to_subscriber` (and any other pre-existing test in that file) to pass `user_id=` to both `subscribe(...)` and `publish(...)`, matching the new required signature — pick any consistent id (e.g. `user_id=1`) for both calls in that test so the existing assertion (that the one subscriber receives the one published event) still holds.

- [ ] **Step 6: Update `app/api/events.py`'s SSE endpoint**

```python
# backend/app/api/events.py
import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.deps import require_api_key, require_user
from app.events import broadcaster
from app.models import User

router = APIRouter(tags=["events"], dependencies=[Depends(require_api_key)])


@router.get("/events")
async def stream_events(current_user: User = Depends(require_user)):
    queue = broadcaster.subscribe(user_id=current_user.id)

    async def event_generator():
        try:
            while True:
                event = await queue.get()
                yield {"event": event["type"], "data": json.dumps(event["payload"])}
        finally:
            broadcaster.unsubscribe(queue)

    return EventSourceResponse(event_generator())
```

- [ ] **Step 7: Run the full suite**

Run: `cd backend && .venv/bin/python -m pytest -v 2>&1 | tail -40`
Expected: green, except for any router (repos.py, recommendations.py, runs.py) that hasn't yet been updated to pass `user_id=` to `broadcaster.publish` in a task not yet completed — those are expected failures at this point if executing strictly in the listed order; they resolve as Tasks 4, 6, 8 land.

- [ ] **Step 8: Commit**

```bash
cd backend
git add app/events.py app/api/events.py tests/test_events.py
git commit -m "feat(backend): scope SSE event delivery per-user"
```

---

### Task 6: Per-user scoping on `insights.py`

**Files:**
- Modify: `backend/app/api/insights.py`
- Test: `backend/tests/test_insights_extra_endpoints.py` (extend), `backend/tests/test_read_endpoints.py` (fix any direct-model-construction breakage per Task 1 Step 4's instruction)

**Interfaces:**
- Consumes: `require_user` (Task 3).
- Produces: every function in `insights.py` takes `current_user: User = Depends(require_user)`; `_require_repo` now also checks `Repo.user_id == current_user.id`.

- [ ] **Step 1: Write the failing cross-user isolation test**

```python
# backend/tests/test_insights_extra_endpoints.py — add to existing file
def test_snapshots_isolated_per_user(client, other_user_client):
    repo_resp = client.post("/repos", json={"owner": "octocat", "name": "mine"})
    repo_id = repo_resp.json()["id"]

    other_snapshots = other_user_client.get(f"/repos/{repo_id}/snapshots")
    assert other_snapshots.status_code == 404

    other_insights = other_user_client.get(f"/repos/{repo_id}/insights")
    assert other_insights.status_code == 404

    other_benchmarks = other_user_client.get(f"/repos/{repo_id}/benchmarks")
    assert other_benchmarks.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_insights_extra_endpoints.py::test_snapshots_isolated_per_user -v`
Expected: FAIL — `other_user_client` currently gets 200 (no scoping).

- [ ] **Step 3: Rewrite `insights.py`**

```python
# backend/app/api/insights.py — full replacement
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key, require_user
from app.models import BenchmarkRepo, PopularPath, Recommendation, Referrer, Repo, Snapshot, User

router = APIRouter(prefix="/repos", tags=["insights"], dependencies=[Depends(require_api_key)])


class SnapshotOut(BaseModel):
    id: int
    date: date
    stars: int
    forks: int
    watchers: int
    open_issues: int
    views_14d: int
    unique_views_14d: int
    clones_14d: int
    unique_clones_14d: int

    model_config = {"from_attributes": True}


class InsightsOut(BaseModel):
    latest_stars: int
    latest_forks: int
    recommendation_count: int


class BenchmarkOut(BaseModel):
    full_name: str
    stars: int
    forks: int
    topics: list[str]


class ReferrerOut(BaseModel):
    id: int
    date: date
    referrer: str
    count: int
    uniques: int

    model_config = {"from_attributes": True}


class PopularPathOut(BaseModel):
    id: int
    date: date
    path: str
    count: int
    uniques: int

    model_config = {"from_attributes": True}


@router.get("/{repo_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(
    repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> list[Snapshot]:
    _require_repo(repo_id, db, current_user)
    return db.execute(select(Snapshot).where(Snapshot.repo_id == repo_id).order_by(Snapshot.date)).scalars().all()


@router.get("/{repo_id}/insights", response_model=InsightsOut)
def get_insights(
    repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> InsightsOut:
    _require_repo(repo_id, db, current_user)
    latest = db.execute(
        select(Snapshot).where(Snapshot.repo_id == repo_id).order_by(Snapshot.date.desc())
    ).scalars().first()
    recommendations = db.execute(
        select(Recommendation).where(Recommendation.repo_id == repo_id, Recommendation.dismissed.is_(False))
    ).scalars().all()

    return InsightsOut(
        latest_stars=latest.stars if latest else 0,
        latest_forks=latest.forks if latest else 0,
        recommendation_count=len(recommendations),
    )


@router.get("/{repo_id}/benchmarks", response_model=list[BenchmarkOut])
def list_benchmarks(
    repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> list[BenchmarkOut]:
    _require_repo(repo_id, db, current_user)
    rows = db.execute(select(BenchmarkRepo).where(BenchmarkRepo.source_repo_id == repo_id)).scalars().all()
    return [BenchmarkOut(full_name=r.full_name, stars=r.stars, forks=r.forks, topics=r.topics) for r in rows]


@router.get("/{repo_id}/referrers", response_model=list[ReferrerOut])
def list_referrers(
    repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> list[Referrer]:
    _require_repo(repo_id, db, current_user)
    return db.execute(
        select(Referrer).where(Referrer.repo_id == repo_id).order_by(Referrer.date.desc())
    ).scalars().all()


@router.get("/{repo_id}/popular-paths", response_model=list[PopularPathOut])
def list_popular_paths(
    repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> list[PopularPath]:
    _require_repo(repo_id, db, current_user)
    return db.execute(
        select(PopularPath).where(PopularPath.repo_id == repo_id).order_by(PopularPath.date.desc())
    ).scalars().all()


def _require_repo(repo_id: int, db: Session, current_user: User) -> Repo:
    repo = db.execute(
        select(Repo).where(Repo.id == repo_id, Repo.user_id == current_user.id)
    ).scalars().first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_insights_extra_endpoints.py -v`
Expected: all pass.

- [ ] **Step 5: Fix `test_read_endpoints.py` if it breaks**

This pre-existing test file likely calls `client.get(...)` on these endpoints without expecting a `user_id` concept. Since `client` now carries a consistent test user, and the endpoint under test creates/reads its own data within that same test via the `client` fixture, this should keep working unchanged — run it and fix only if it fails:

Run: `cd backend && .venv/bin/python -m pytest tests/test_read_endpoints.py -v`
Expected: pass unchanged. If it fails, the likely cause is direct model construction without `user_id` (per Task 1 Step 4's pattern) — fix the same way.

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/api/insights.py tests/
git commit -m "feat(backend): per-user scoping on snapshots/insights/benchmarks/referrers/popular-paths"
```

---

### Task 7: Per-user scoping on `recommendations.py`

**Files:**
- Modify: `backend/app/api/recommendations.py`
- Test: `backend/tests/test_recommendations_api.py` (new — no dedicated file existed before; check `test_read_endpoints.py` isn't already covering this in a way you'd duplicate)

**Interfaces:**
- Consumes: `require_user` (Task 3), `broadcaster.publish(..., user_id=...)` (Task 5).
- Produces: `list_recommendations`/`update_recommendation` scoped by `current_user.id`.

- [ ] **Step 1: Write the failing isolation test**

```python
# backend/tests/test_recommendations_api.py
from datetime import date

from app.db import SessionLocal
from app.models import Recommendation, Repo, Snapshot


def _seed_recommendation_for(user_id: int) -> tuple[int, int]:
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    rec = Recommendation(
        user_id=user_id,
        repo_id=repo.id,
        category="missing_license",
        title="Add a LICENSE",
        body="No LICENSE file found.",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    rec_id = rec.id
    db.close()
    return repo.id, rec_id


def test_recommendations_isolated_per_user(client, other_user_client):
    _repo_id, rec_id = _seed_recommendation_for(client.test_user_id)

    other_list = other_user_client.get("/recommendations")
    assert other_list.json() == []

    other_patch = other_user_client.patch(f"/recommendations/{rec_id}", json={"dismissed": True})
    assert other_patch.status_code == 404


def test_dismiss_recommendation(client):
    _repo_id, rec_id = _seed_recommendation_for(client.test_user_id)

    resp = client.patch(f"/recommendations/{rec_id}", json={"dismissed": True})
    assert resp.status_code == 200
    assert resp.json()["dismissed"] is True

    list_resp = client.get("/recommendations")
    assert any(r["id"] == rec_id and r["dismissed"] for r in list_resp.json())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_recommendations_api.py -v`
Expected: FAIL — no scoping yet, `other_user_client` sees the recommendation.

- [ ] **Step 3: Rewrite `recommendations.py`**

```python
# backend/app/api/recommendations.py — full replacement
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key, require_user
from app.events import broadcaster
from app.models import Recommendation, User

router = APIRouter(prefix="/recommendations", tags=["recommendations"], dependencies=[Depends(require_api_key)])


class RecommendationOut(BaseModel):
    id: int
    repo_id: int
    category: str
    title: str
    body: str
    validated: bool
    dismissed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationPatch(BaseModel):
    dismissed: bool


@router.get("", response_model=list[RecommendationOut])
def list_recommendations(
    db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> list[Recommendation]:
    return db.execute(
        select(Recommendation)
        .where(Recommendation.user_id == current_user.id)
        .order_by(Recommendation.created_at.desc())
    ).scalars().all()


@router.patch("/{recommendation_id}", response_model=RecommendationOut)
def update_recommendation(
    recommendation_id: int,
    payload: RecommendationPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> Recommendation:
    rec = db.execute(
        select(Recommendation).where(
            Recommendation.id == recommendation_id, Recommendation.user_id == current_user.id
        )
    ).scalars().first()
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.dismissed = payload.dismissed
    db.commit()
    db.refresh(rec)
    broadcaster.publish(
        "recommendation_updated", {"id": rec.id, "dismissed": rec.dismissed}, user_id=current_user.id
    )
    return rec
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_recommendations_api.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/api/recommendations.py tests/test_recommendations_api.py
git commit -m "feat(backend): per-user scoping on recommendations"
```

---

### Task 8: `GitHubClient` circuit breaker, benchmark-search TTL cache

**Files:**
- Modify: `backend/app/github_client.py`
- Test: `backend/tests/test_github_client.py` (extend)

**Interfaces:**
- Consumes: nothing new.
- Produces: `GitHubAuthError` (exception, raised on any 401 from GitHub), `GitHubClient._get(path, **kwargs) -> httpx.Response` (internal helper, replaces every bare `self._http.get(...)` + `raise_for_status()` pair). `search_similar_repos` gains a process-wide, language+topic-keyed, 1-hour TTL cache — shared across users deliberately, since search results for public repos are identical regardless of which user's token asks. Task 9 (`jobs.py`) catches `GitHubAuthError` to implement the per-user circuit breaker.

- [ ] **Step 1: Write the failing auth-error test**

```python
# backend/tests/test_github_client.py — add to existing file
import httpx
import pytest

from app.github_client import GitHubAuthError, GitHubClient


def test_get_repo_raises_github_auth_error_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://api.github.com")
    client = GitHubClient(token="expired-token", http_client=http_client)

    with pytest.raises(GitHubAuthError):
        client.get_repo("octocat", "hello-world")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_github_client.py::test_get_repo_raises_github_auth_error_on_401 -v`
Expected: FAIL — currently raises `httpx.HTTPStatusError`, not `GitHubAuthError`.

- [ ] **Step 3: Add the `_get` helper, `GitHubAuthError`, and the benchmark cache**

```python
# backend/app/github_client.py — full replacement
import base64
import time

import httpx


class GitHubAuthError(Exception):
    """Raised when GitHub rejects the current token (expired/revoked) — lets
    the pipeline runner (app/pipeline/jobs.py) stop retrying that user's
    repos for the rest of the run instead of hammering a dead token."""


class GitHubClient:
    # Process-wide, shared across every GitHubClient instance/user — search
    # results for a given language+topic are the same public data regardless
    # of who's asking, so sharing this cache is a real efficiency win, not a
    # data leak. 1-hour TTL: benchmark data doesn't need to be fresher than that.
    _benchmark_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}
    _BENCHMARK_CACHE_TTL_SECONDS = 3600

    def __init__(self, token: str, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=15.0,
        )

    def _get(self, path: str, **kwargs) -> httpx.Response:
        resp = self._http.get(path, **kwargs)
        if resp.status_code == 401:
            raise GitHubAuthError(f"GitHub token rejected for {path}")
        resp.raise_for_status()
        return resp

    def get_repo(self, owner: str, name: str) -> dict:
        return self._get(f"/repos/{owner}/{name}").json()

    def get_traffic_views(self, owner: str, name: str) -> dict:
        return self._get(f"/repos/{owner}/{name}/traffic/views").json()

    def get_traffic_clones(self, owner: str, name: str) -> dict:
        return self._get(f"/repos/{owner}/{name}/traffic/clones").json()

    def get_referrers(self, owner: str, name: str) -> list[dict]:
        return self._get(f"/repos/{owner}/{name}/traffic/popular/referrers").json()

    def get_popular_paths(self, owner: str, name: str) -> list[dict]:
        return self._get(f"/repos/{owner}/{name}/traffic/popular/paths").json()

    def get_readme(self, owner: str, name: str) -> str | None:
        resp = self._http.get(f"/repos/{owner}/{name}/readme")
        if resp.status_code == 404:
            return None
        if resp.status_code == 401:
            raise GitHubAuthError(f"GitHub token rejected for /repos/{owner}/{name}/readme")
        resp.raise_for_status()
        content = resp.json().get("content", "")
        return base64.b64decode(content).decode("utf-8", errors="replace")

    def has_file(self, owner: str, name: str, path: str) -> bool:
        resp = self._http.get(f"/repos/{owner}/{name}/contents/{path}")
        if resp.status_code == 401:
            raise GitHubAuthError(f"GitHub token rejected for /repos/{owner}/{name}/contents/{path}")
        return resp.status_code == 200

    def search_similar_repos(self, language: str, topic: str, limit: int = 5) -> list[dict]:
        cache_key = (language, topic)
        cached = GitHubClient._benchmark_cache.get(cache_key)
        if cached and (time.time() - cached[0]) < self._BENCHMARK_CACHE_TTL_SECONDS:
            return cached[1][:limit]

        query = f"language:{language} topic:{topic}"
        items = self._get("/search/repositories", params={"q": query, "sort": "stars", "per_page": limit}).json().get("items", [])
        GitHubClient._benchmark_cache[cache_key] = (time.time(), items)
        return items
```

`get_readme` and `has_file` keep their own inline 401 checks (rather than routing through `_get`) because both already have special-cased status-code handling (`404` → `None`/`False`) that `_get`'s blanket `raise_for_status()` would short-circuit incorrectly — this is a deliberate, minimal deviation from the `_get` helper, not an oversight.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_github_client.py -v`
Expected: all pass, including all 6 pre-existing tests (they don't touch 401 handling, so they're unaffected by this refactor).

- [ ] **Step 5: Write the TTL cache test**

```python
# backend/tests/test_github_client.py — add to existing file
def test_search_similar_repos_caches_across_instances():
    from app.github_client import GitHubClient

    GitHubClient._benchmark_cache.clear()
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json={"items": [{"full_name": "torvalds/linux"}]})

    transport = httpx.MockTransport(handler)

    client_a = GitHubClient(token="token-a", http_client=httpx.Client(transport=transport, base_url="https://api.github.com"))
    client_b = GitHubClient(token="token-b", http_client=httpx.Client(transport=transport, base_url="https://api.github.com"))

    client_a.search_similar_repos(language="python", topic="cli", limit=5)
    client_b.search_similar_repos(language="python", topic="cli", limit=5)

    assert call_count["n"] == 1
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_github_client.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/github_client.py tests/test_github_client.py
git commit -m "feat(backend): GitHubAuthError circuit breaker, benchmark-search TTL cache"
```

---

### Task 9: Per-user pipeline wiring — `jobs.py`, `main.py`, BackgroundTasks in `runs.py`

**Files:**
- Modify: `backend/app/pipeline/jobs.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/runs.py`
- Test: `backend/tests/test_runner.py` (check still passes unchanged), `backend/tests/test_runs_api.py` (new)

**Interfaces:**
- Consumes: `decrypt_token` (Task 2), `GitHubAuthError` (Task 8), `broadcaster.publish(..., user_id=...)` (Task 5), `require_user` (Task 3).
- Produces: `run_pipeline_for_all_repos(db: Session, user_id: int | None = None) -> None` — `user_id=None` means "every user's repos" (the daily scheduled job); a specific id scopes to one user (manual trigger). Publishes `run_completed` per-user once their repos finish, and skips a user's remaining repos for the rest of that run if their token is rejected.

- [ ] **Step 1: Write the failing per-user pipeline test**

```python
# backend/tests/test_pipeline_per_user.py
from unittest.mock import MagicMock, patch

from app.db import SessionLocal
from app.models import PipelineRun, Repo, User
from app.token_crypto import encrypt_token


def _seed_user_with_repo(github_id: str) -> tuple[int, int]:
    db = SessionLocal()
    user = User(
        github_id=github_id,
        username=f"user-{github_id}",
        avatar_url=f"https://avatars.githubusercontent.com/u/{github_id}",
        email=None,
        access_token_encrypted=encrypt_token(f"token-for-{github_id}"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    repo = Repo(owner="octocat", name=f"repo-{github_id}", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    db.close()
    return user.id, repo.id


@patch("app.pipeline.jobs.build_stages")
def test_run_pipeline_scoped_to_one_user(mock_build_stages):
    user_a_id, _repo_a_id = _seed_user_with_repo("111")
    user_b_id, _repo_b_id = _seed_user_with_repo("222")

    mock_runner = MagicMock()
    mock_runner.run_for_repo.side_effect = lambda repo: type("Ctx", (), {"errors": []})()
    with patch("app.pipeline.jobs.PipelineRunner", return_value=mock_runner):
        from app.pipeline.jobs import run_pipeline_for_all_repos

        db = SessionLocal()
        run_pipeline_for_all_repos(db, user_id=user_a_id)
        db.close()

    assert mock_runner.run_for_repo.call_count == 1
    assert mock_runner.run_for_repo.call_args[0][0].user_id == user_a_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_pipeline_per_user.py -v`
Expected: FAIL — `run_pipeline_for_all_repos` doesn't accept `user_id` yet.

- [ ] **Step 3: Rewrite `jobs.py`**

```python
# backend/app/pipeline/jobs.py
from sqlalchemy.orm import Session

from app.config import get_settings
from app.events import broadcaster
from app.github_client import GitHubAuthError, GitHubClient
from app.llm_router import LLMRouter
from app.models import Repo, User
from app.pipeline.analyzer import Analyzer
from app.pipeline.assembler import Assembler
from app.pipeline.extractor import Extractor
from app.pipeline.optimizer import Optimizer
from app.pipeline.preprocessor import Preprocessor
from app.pipeline.runner import PipelineRunner
from app.pipeline.synthesizer import Synthesizer
from app.pipeline.validator import Validator
from app.token_crypto import decrypt_token


def build_stages(db: Session, gh_client: GitHubClient, llm_router: LLMRouter) -> list:
    return [
        Extractor(gh_client=gh_client),
        Preprocessor(db_session=db),
        Analyzer(),
        Optimizer(),
        Synthesizer(llm_router=llm_router),
        Validator(),
        Assembler(db_session=db),
    ]


def run_pipeline_for_all_repos(db: Session, user_id: int | None = None) -> None:
    settings = get_settings()
    llm_router = LLMRouter(settings=settings, db_session=db)

    query = db.query(Repo)
    if user_id is not None:
        query = query.filter(Repo.user_id == user_id)
    repos = query.all()

    failed_auth_user_ids: set[int] = set()
    processed_user_ids: set[int] = set()

    for repo in repos:
        if repo.user_id in failed_auth_user_ids:
            continue

        owner = db.get(User, repo.user_id)
        gh_client = GitHubClient(token=decrypt_token(owner.access_token_encrypted))
        runner = PipelineRunner(stages=build_stages(db, gh_client, llm_router), db_session=db)
        ctx = runner.run_for_repo(repo)

        if any("needs_reauth" in error for error in ctx.errors):
            failed_auth_user_ids.add(repo.user_id)
            continue

        processed_user_ids.add(repo.user_id)

    for uid in processed_user_ids:
        broadcaster.publish("run_completed", {}, user_id=uid)
```

Note: `GitHubAuthError`'s message must contain the literal substring `"needs_reauth"` for this detection to work — Step 4 fixes that.

- [ ] **Step 4: Update `GitHubAuthError`'s message to include the `needs_reauth` marker**

```python
# backend/app/github_client.py:14-17 — update the _get helper's raise
    def _get(self, path: str, **kwargs) -> httpx.Response:
        resp = self._http.get(path, **kwargs)
        if resp.status_code == 401:
            raise GitHubAuthError(f"needs_reauth: GitHub token rejected for {path}")
        resp.raise_for_status()
        return resp
```

Also update the two inline 401 checks in `get_readme` and `has_file` (from Task 8) to use the same `"needs_reauth: ..."` message prefix for consistency.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_pipeline_per_user.py -v`
Expected: PASS

- [ ] **Step 6: Update `main.py`'s scheduled job (now scans all users automatically — no change needed to the call itself, just confirm it still reads correctly)**

```python
# backend/app/main.py:36-41 — unchanged code, confirm it still reads this way
def _scheduled_pipeline_run() -> None:
    db = SessionLocal()
    try:
        run_pipeline_for_all_repos(db)  # user_id=None — every tracked repo, across every user
    finally:
        db.close()
```

(No edit needed here — `run_pipeline_for_all_repos(db)` already means "all users" now that `user_id` defaults to `None`. This step is a verification checkpoint, not a code change.)

- [ ] **Step 7: Write the failing BackgroundTasks test for `POST /runs`**

```python
# backend/tests/test_runs_api.py
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
```

- [ ] **Step 8: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_runs_api.py -v`
Expected: FAIL — `POST /runs` currently runs synchronously and returns `list[PipelineRunOut]`, not `{"status": "started"}`.

- [ ] **Step 9: Rewrite `runs.py`**

```python
# backend/app/api/runs.py — full replacement
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.deps import require_api_key, require_user
from app.models import PipelineRun, StageRun, User

router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(require_api_key)])


class PipelineRunOut(BaseModel):
    id: int
    status: str
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class StageRunOut(BaseModel):
    id: int
    stage_name: str
    status: str
    duration_ms: int
    error: str | None

    model_config = {"from_attributes": True}


class TriggerRunOut(BaseModel):
    status: str


@router.get("", response_model=list[PipelineRunOut])
def list_runs(db: Session = Depends(get_db), current_user: User = Depends(require_user)) -> list[PipelineRun]:
    return db.execute(
        select(PipelineRun)
        .where(PipelineRun.user_id == current_user.id)
        .order_by(PipelineRun.started_at.desc())
    ).scalars().all()


@router.post("", response_model=TriggerRunOut, status_code=202)
def trigger_run(
    background_tasks: BackgroundTasks, current_user: User = Depends(require_user)
) -> TriggerRunOut:
    background_tasks.add_task(_run_pipeline_background, current_user.id)
    return TriggerRunOut(status="started")


def _run_pipeline_background(user_id: int) -> None:
    from app.pipeline.jobs import run_pipeline_for_all_repos

    db = SessionLocal()
    try:
        run_pipeline_for_all_repos(db, user_id=user_id)
    finally:
        db.close()


@router.get("/{run_id}/stages", response_model=list[StageRunOut])
def list_run_stages(
    run_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_user)
) -> list[StageRun]:
    run = db.execute(
        select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.user_id == current_user.id)
    ).scalars().first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return db.execute(
        select(StageRun).where(StageRun.pipeline_run_id == run_id).order_by(StageRun.id)
    ).scalars().all()
```

Note: `PipelineRunner.run_for_repo` (unmodified — see `app/pipeline/runner.py`) doesn't set `PipelineRun.user_id` or `StageRun.user_id` itself; it only knows about `Repo`. Add that assignment in the runner's `run_for_repo` — wait, that file is explicitly load-bearing/policy-locked per `CLAUDE.md` ("breaking the interface breaks that resilience model"). Setting `user_id` on the rows it creates isn't a Stage-interface change — it's an internal detail of what `PipelineRunner` persists, and it directly serves this migration's requirement that every table have a real `user_id`. Make this one, minimal addition:

```python
# backend/app/pipeline/runner.py:15-19 — the only change, adding user_id to both created rows
    def run_for_repo(self, repo: Repo) -> PipelineContext:
        run_row = PipelineRun(status="running", user_id=repo.user_id)
        self.db.add(run_row)
        self.db.commit()
        self.db.refresh(run_row)
```

```python
# backend/app/pipeline/runner.py:38-44 — add user_id here too
            self.db.add(StageRun(
                pipeline_run_id=run_row.id,
                user_id=repo.user_id,
                stage_name=stage.name,
                status=status,
                duration_ms=duration_ms,
                error=error_text,
            ))
```

This is the smallest possible change to `runner.py` — the `Stage`/`PipelineContext` interface (the thing CLAUDE.md protects) is completely untouched; only the two `db.add(...)` calls gain one field each.

- [ ] **Step 10: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_runs_api.py -v`
Expected: PASS

- [ ] **Step 11: Run the full suite**

Run: `cd backend && .venv/bin/python -m pytest -v 2>&1 | tail -60`
Expected: all green. `test_runner.py`'s existing tests construct `PipelineRunner` directly with a `Repo` — confirm those repos have `user_id` set (per Task 1's fix-forward pass); if any fail here for the first time, it's because `runner.py`'s `run_for_repo` now reads `repo.user_id` — make sure every `Repo` fixture in `test_runner.py`/`test_pipeline_integration.py` has a real `user_id`.

- [ ] **Step 12: Commit**

```bash
cd backend
git add app/pipeline/jobs.py app/pipeline/runner.py app/main.py app/api/runs.py tests/
git commit -m "feat(backend): per-user pipeline scoping, async run trigger via BackgroundTasks"
```

---

### Task 10: Rate limiting (`slowapi`)

**Files:**
- Create: `backend/app/rate_limit.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/repos.py` (only the `create_repo` route)
- Modify: `backend/app/api/runs.py` (only the `trigger_run` route)
- Test: `backend/tests/test_rate_limit.py`

**Interfaces:**
- Consumes: `verify_internal_user_token` (Task 2).
- Produces: `limiter` (module-level `slowapi.Limiter` instance) importable from `app.rate_limit`, used as `@limiter.limit("10/minute")` on rate-limited routes.

- [ ] **Step 1: Add `slowapi` to requirements**

```bash
# backend/requirements.txt — add this line
slowapi==0.1.10
```

Run: `cd backend && .venv/bin/pip install -r requirements.txt`

- [ ] **Step 2: Write the failing rate-limit test**

```python
# backend/tests/test_rate_limit.py
def test_create_repo_rate_limited_after_threshold(client):
    responses = [client.post("/repos", json={"owner": "octocat", "name": f"repo-{i}"}) for i in range(11)]
    statuses = [r.status_code for r in responses]
    assert 429 in statuses
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_rate_limit.py -v`
Expected: FAIL — no rate limiting yet (11th request gets 403, the quota limit, not 429 — bump `max_tracked_repos` isn't the point here, so this test naturally hits the repo-count quota from Task 4 before the rate limit if the default quota (5) is lower than 11 attempts. Adjust the test to raise this user's quota first so the rate limiter — not the quota — is what's actually being exercised:

```python
# backend/tests/test_rate_limit.py — corrected version
def test_create_repo_rate_limited_after_threshold(client):
    from app.db import SessionLocal
    from app.models import User

    db = SessionLocal()
    user = db.query(User).filter(User.github_id == "12345").one()
    user.max_tracked_repos = 100
    db.commit()
    db.close()

    responses = [client.post("/repos", json={"owner": "octocat", "name": f"repo-{i}"}) for i in range(11)]
    statuses = [r.status_code for r in responses]
    assert 429 in statuses
```

- [ ] **Step 3: Implement `app/rate_limit.py`**

```python
# backend/app/rate_limit.py
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.internal_auth import verify_internal_user_token


def _rate_limit_key(request: Request) -> str:
    # Key by the verified github_id when a valid internal user token is
    # present, so per-user limits hold even behind a shared IP (office
    # network, corporate NAT). The token itself rotates every request (60s
    # TTL, minted fresh per call) so it can't be used as the key directly —
    # only the github_id it decodes to is stable.
    token = request.headers.get("x-internal-user-token", "")
    if token:
        try:
            return f"user:{verify_internal_user_token(token)}"
        except ValueError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)
```

- [ ] **Step 4: Wire the limiter into `main.py`**

```python
# backend/app/main.py — add these imports and lines
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.rate_limit import limiter

# ... after `app = FastAPI(title="GitHub Growth Bot API")`
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

- [ ] **Step 5: Apply the limit to `create_repo` and `trigger_run`**

```python
# backend/app/api/repos.py — add import and decorator
from fastapi import Request  # add to the existing fastapi import line
from app.rate_limit import limiter

@router.post("", response_model=RepoOut, status_code=201)
@limiter.limit("10/minute")
def create_repo(
    request: Request,
    payload: RepoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> Repo:
    ...  # body unchanged from Task 4
```

```python
# backend/app/api/runs.py — add import and decorator
from fastapi import Request  # add to the existing fastapi import line
from app.rate_limit import limiter

@router.post("", response_model=TriggerRunOut, status_code=202)
@limiter.limit("10/minute")
def trigger_run(
    request: Request, background_tasks: BackgroundTasks, current_user: User = Depends(require_user)
) -> TriggerRunOut:
    ...  # body unchanged from Task 9
```

`slowapi`'s `@limiter.limit(...)` decorator requires a `Request` parameter on the decorated function — this is the one signature change beyond adding the decorator itself.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_rate_limit.py -v`
Expected: PASS

- [ ] **Step 7: Run the full suite**

Run: `cd backend && .venv/bin/python -m pytest -v 2>&1 | tail -20`
Expected: all green. Watch for other tests that call `POST /repos` or `POST /runs` more than 10 times within the same test process — `slowapi`'s default in-memory store is per-process and doesn't reset between tests in the same run, so a test earlier in the suite hammering `POST /repos` could cause a LATER unrelated test to unexpectedly hit 429. If that happens, it means two tests in the same file (or process) are cumulatively exceeding 10 `POST /repos` calls — check `test_repos_api.py`, `test_repos_delete_cascade.py`, `test_recommendations_api.py`, and this file's own repeated-post loop don't collectively exceed the per-key 10/minute window in a way that bleeds across tests; if it does, either raise this test-only limit via a `RATE_LIMIT_TEST_OVERRIDE`-style conditional (avoid this — it weakens the test), or ensure the 11-request loop in this test's own function is the only place that deliberately exceeds 10 in a single test run, and confirm other test files collectively stay at or under 10 `POST /repos` calls each. If genuinely need be, `slowapi` supports resetting via `limiter.reset()` — call it in the `_reset_db` fixture in `conftest.py` for full test isolation:

```python
# backend/tests/conftest.py — add to the _reset_db fixture, after create_all
@pytest.fixture(autouse=True)
def _reset_db():
    from app.db import Base, engine
    import app.models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.rate_limit import limiter
    limiter.reset()

    yield
```

This is the correct fix — it isolates the rate limiter's counters per-test exactly like the DB is isolated per-test, rather than weakening the limit itself.

- [ ] **Step 8: Commit**

```bash
cd backend
git add app/rate_limit.py app/main.py app/api/repos.py app/api/runs.py tests/
git commit -m "feat(backend): per-user/per-IP rate limiting on repo creation and run triggers"
```

---

### Task 11: Backend whole-module review checkpoint

Before moving to the frontend, run the complete backend suite one final time and confirm the full request-authorization chain end-to-end.

- [ ] **Step 1: Full suite, zero warnings beyond the pre-existing accepted ones**

Run: `cd backend && .venv/bin/python -m pytest -v 2>&1 | tail -30`
Expected: 100% pass, only the pre-existing `on_event` deprecation warnings (RISK-0003).

- [ ] **Step 2: `pip-audit`, confirm the new dependencies introduce no known vulnerabilities**

Run: `cd backend && .venv/bin/pip-audit`
Expected: no known vulnerabilities (or, if any are found in `cryptography`/`slowapi`, treat exactly like the CVE-fix precedent from this same project's history — bump to the fixed version, re-run, don't skip this check).

- [ ] **Step 3: Commit any final cleanup, dispatch the fresh backend reviewer per this project's Red Team Protocol (CLAUDE.md: "Build Agent does not verify its own work")**

This is the natural point for `superpowers:subagent-driven-development`'s per-task reviewer pattern — if executing via that skill, this task's own review already happened per-task; this step is the controller's cue to also run a broader review across Tasks 1-10 together (the full backend diff), since per-task reviews can't see cross-task issues like the `EventBroadcaster`/`repos.py` ordering note in Task 4.

---

### Task 12: Auth.js (NextAuth v5) setup — GitHub provider, config, route handler

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/auth.ts`
- Create: `frontend/app/api/auth/[...nextauth]/route.ts`
- Create: `frontend/types/next-auth.d.ts`
- Modify: `frontend/.env.local.example`

**Interfaces:**
- Consumes: nothing new (this is the root of the frontend auth work).
- Produces: `auth`, `handlers`, `signIn`, `signOut` exported from `@/auth` — `lib/backend-client.ts` (Task 13) imports `auth`; `proxy.ts` (Task 14) imports `auth`.

- [ ] **Step 1: Install Auth.js v5**

```bash
cd frontend
npm install next-auth@5.0.0-beta.32
```

- [ ] **Step 2: Add env vars**

```bash
# frontend/.env.local.example — add these lines
AUTH_SECRET=
AUTH_GITHUB_ID=
AUTH_GITHUB_SECRET=
INTERNAL_AUTH_SECRET=
```

`AUTH_SECRET` signs/encrypts Auth.js's own session cookie (generate via `openssl rand -base64 32`). `AUTH_GITHUB_ID`/`AUTH_GITHUB_SECRET` come from a GitHub OAuth App (GitHub → Settings → Developer settings → OAuth Apps → New OAuth App; callback URL `http://localhost:3000/api/auth/callback/github` for dev, the production Vercel domain's equivalent for deploy). `INTERNAL_AUTH_SECRET` must be the exact same value as the backend's `INTERNAL_AUTH_SECRET` env var (Task 2) — this is the shared secret both sides HMAC-sign/verify with.

- [ ] **Step 3: Write `frontend/auth.ts`**

```typescript
// frontend/auth.ts
import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY ?? "";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    GitHub({
      // Public-repo scope only (spec §2) — no `repo` scope, no private-repo access.
      authorization: { params: { scope: "read:user public_repo" } },
    }),
  ],
  callbacks: {
    async jwt({ token, account, profile }) {
      // account/profile are only present on the initial sign-in, not on
      // every subsequent token refresh — this is where we bootstrap the
      // backend's User row, deliberately via a raw fetch (not lib/api.ts)
      // to avoid a circular import: lib/backend-client.ts imports auth()
      // from this file for its own per-request session check, so this file
      // must not import back into lib/ at module scope.
      if (account?.provider === "github" && profile) {
        const githubId = String(profile.id);
        token.githubId = githubId;

        await fetch(`${BACKEND_URL}/users/upsert`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${BACKEND_API_KEY}`,
          },
          body: JSON.stringify({
            github_id: githubId,
            username: (profile as { login?: string }).login ?? "unknown",
            avatar_url: (profile as { avatar_url?: string }).avatar_url ?? "",
            email: profile.email ?? null,
            access_token: account.access_token,
          }),
        });
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.githubId as string;
      }
      return session;
    },
  },
});
```

- [ ] **Step 4: Route handler**

```typescript
// frontend/app/api/auth/[...nextauth]/route.ts
import { handlers } from "@/auth";

export const { GET, POST } = handlers;
```

- [ ] **Step 5: TypeScript module augmentation**

```typescript
// frontend/types/next-auth.d.ts
import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
    } & DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    githubId?: string;
  }
}
```

- [ ] **Step 6: Verify it builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean (no type errors).

- [ ] **Step 7: Commit**

```bash
cd frontend
git add package.json package-lock.json auth.ts app/api/auth types/next-auth.d.ts .env.local.example
git commit -m "feat(frontend): Auth.js v5 GitHub OAuth setup, public_repo scope only"
```

---

### Task 13: Internal token minting, `backend-client.ts` auto-attach, `upsertUser` API method

**Files:**
- Create: `frontend/lib/internal-auth.ts`
- Modify: `frontend/lib/backend-client.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/api-types.ts` (if `TriggerRunOut`/user types need adding — check current contents first)
- Test: `frontend/tests/internal-auth.test.ts`

**Interfaces:**
- Consumes: `auth` from `@/auth` (Task 12).
- Produces: `mintInternalUserToken(githubId: string): string`; `backendFetch<T>` (unchanged call signature, now throws `BackendError(401, ...)` if no session); new `backendFetchSystem<T>` (API-key only, no session check) for the one bootstrap call. **Every existing Route Handler (13 files) and every existing `page.tsx` SSR prefetch call needs zero changes** — the auth-awareness is fully centralized here, per this plan's Global Constraints.

- [ ] **Step 1: Write the failing token round-trip test**

```typescript
// frontend/tests/internal-auth.test.ts
import { describe, expect, it, vi } from "vitest";

vi.stubEnv("INTERNAL_AUTH_SECRET", "test-only-internal-secret-do-not-use-in-prod");

import { mintInternalUserToken } from "@/lib/internal-auth";

describe("mintInternalUserToken", () => {
  it("produces a token with a payload segment and a signature segment", () => {
    const token = mintInternalUserToken("12345");
    const parts = token.split(".");
    expect(parts).toHaveLength(2);

    const payload = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf-8"));
    expect(payload.sub).toBe("12345");
    expect(typeof payload.exp).toBe("number");
  });

  it("produces a different signature for a different secret", () => {
    const tokenA = mintInternalUserToken("12345");
    vi.stubEnv("INTERNAL_AUTH_SECRET", "a-different-secret");
    vi.resetModules();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- internal-auth`
Expected: FAIL — `@/lib/internal-auth` doesn't exist yet.

- [ ] **Step 3: Implement `lib/internal-auth.ts`**

```typescript
// frontend/lib/internal-auth.ts
import "server-only";
import { createHmac } from "node:crypto";

const SECRET = process.env.INTERNAL_AUTH_SECRET ?? "";
const TOKEN_TTL_SECONDS = 60;

// Signed, short-lived proof of "this request's user id was verified by our
// own Auth.js session check, not supplied by the browser." Verified by the
// backend's app/internal_auth.py::verify_internal_user_token — the payload
// and signature format must match exactly (see that file's docstring).
export function mintInternalUserToken(githubId: string): string {
  const payload = JSON.stringify({
    sub: githubId,
    exp: Math.floor(Date.now() / 1000) + TOKEN_TTL_SECONDS,
  });
  const payloadB64 = Buffer.from(payload, "utf-8").toString("base64url");
  const signature = createHmac("sha256", SECRET).update(payloadB64).digest("hex");
  return `${payloadB64}.${signature}`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- internal-auth`
Expected: PASS

- [ ] **Step 5: Rewrite `lib/backend-client.ts`**

```typescript
// frontend/lib/backend-client.ts
import "server-only";
import { auth } from "@/auth";
import { mintInternalUserToken } from "@/lib/internal-auth";

const BASE_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const API_KEY = process.env.BACKEND_API_KEY ?? "";

export class BackendError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new BackendError(res.status, text || res.statusText);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

// The authenticated fetcher — used by every existing api.ts method except
// upsertUser. Automatically derives the signed internal user token from the
// current Auth.js session, so every one of the 13 Route Handlers and every
// page.tsx SSR prefetch call needs zero changes to become per-user scoped.
export async function backendFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const session = await auth();
  const githubId = session?.user?.id;
  if (!githubId) {
    throw new BackendError(401, "Not authenticated");
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
      "X-Internal-User-Token": mintInternalUserToken(githubId),
      ...init?.headers,
    },
    cache: "no-store",
  });

  return handleResponse<T>(res);
}

// API-key only, no session required — exists solely for the one bootstrap
// call (api.upsertUser) made from auth.ts's own jwt callback, before a
// session/User row necessarily exists yet.
export async function backendFetchSystem<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
      ...init?.headers,
    },
    cache: "no-store",
  });

  return handleResponse<T>(res);
}
```

- [ ] **Step 6: Add `upsertUser` to `lib/api.ts`**

```typescript
// frontend/lib/api.ts — add this method to the existing `api` object, and this import
import { backendFetchSystem } from "@/lib/backend-client";
// (keep the existing `import { backendFetch } from "@/lib/backend-client";` line too)

// ... inside `export const api = { ... }`, add:
  upsertUser: (payload: {
    github_id: string;
    username: string;
    avatar_url: string;
    email: string | null;
    access_token: string;
  }) => backendFetchSystem<{ id: number; github_id: string }>("/users/upsert", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
```

Note: `auth.ts`'s `jwt` callback (Task 12) deliberately does NOT call `api.upsertUser` — it does a raw `fetch` directly, to avoid the circular import (`auth.ts` → `lib/api.ts` → `lib/backend-client.ts` → `auth.ts`). This `api.upsertUser` method exists for consistency/completeness and any future non-callback call site, but is not on the hot path Task 12 actually uses.

- [ ] **Step 7: Also update `triggerRun`'s return type to match the backend's new `{status: string}` contract (Task 9)**

```typescript
// frontend/lib/api.ts — update this one line in the existing api object
  triggerRun: () => backendFetch<{ status: string }>("/runs", { method: "POST" }),
```

Check `frontend/hooks/use-runs.ts`'s `useTriggerRun` mutation — it doesn't consume the returned data in its `onSuccess` (only invalidates), so this return-type change requires no further edits there. Confirm this by reading the hook before assuming it's a no-op change.

- [ ] **Step 8: Verify types and run the full frontend test suite**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: both clean.

- [ ] **Step 9: Commit**

```bash
cd frontend
git add lib/internal-auth.ts lib/backend-client.ts lib/api.ts tests/internal-auth.test.ts
git commit -m "feat(frontend): auto-attach signed internal user token to every backend call"
```

---

### Task 14: `proxy.ts` route protection

**Files:**
- Create: `frontend/proxy.ts`

**Interfaces:**
- Consumes: `auth` from `@/auth` (Task 12).
- Produces: redirects any unauthenticated request for a protected page to `/sign-in` (Task 15 builds that page). Route Handlers under `/api/**` are excluded from this matcher — they do their own explicit `auth()` check inside `backendFetch` (Task 13), matching this Next.js version's own documented guidance ("Always verify authentication and authorization inside each Server Function rather than relying on Proxy alone").

- [ ] **Step 1: Write `proxy.ts`**

```typescript
// frontend/proxy.ts
// NOTE: this Next.js version renamed the `middleware.ts` file convention to
// `proxy.ts` (confirmed via node_modules/next/dist/docs/.../proxy.md — v16.0.0
// change). The exported function/re-export must be named `proxy`, not
// `middleware`, or Next.js won't pick this file up at all.
export { auth as proxy } from "@/auth";

export const config = {
  // Runs on every page except: API routes (they self-check via backendFetch),
  // the sign-in page itself (would otherwise redirect-loop), Next's own
  // static/image assets, and the root-level metadata files.
  matcher: [
    "/((?!api|sign-in|_next/static|_next/image|favicon.ico|robots.txt).*)",
  ],
};
```

Auth.js's `auth` export, used this way, redirects to its configured sign-in page automatically when there's no session and the matched route requires one — by default it redirects to `/api/auth/signin` (Auth.js's own built-in page). Since this project wants its own styled sign-in page (Task 15), add a `pages` option to the `NextAuth(...)` config:

```typescript
// frontend/auth.ts — add this key to the NextAuth({...}) config object from Task 12
  pages: {
    signIn: "/sign-in",
  },
```

- [ ] **Step 2: Verify it builds and the type-checks pass**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Manual verification (no automated test — proxy execution requires a running dev server)**

Run: `cd frontend && npm run dev` (and `cd backend && .venv/bin/uvicorn app.main:app --reload` in another terminal). Visit `http://localhost:3000/` in a private/incognito browser window (no existing session) — confirm it redirects to `/sign-in` (Task 15's page will 404 until that task lands; a redirect to a 404 page still proves the proxy itself is working correctly at this point — re-verify fully once Task 15 exists).

- [ ] **Step 4: Commit**

```bash
cd frontend
git add proxy.ts auth.ts
git commit -m "feat(frontend): protect every page via proxy.ts, redirect unauthenticated to /sign-in"
```

---

### Task 15: Sign-in page, nav-sidebar avatar/logout

**Files:**
- Create: `frontend/app/sign-in/page.tsx`
- Create: `frontend/components/sign-in/sign-in-button.tsx`
- Modify: `frontend/components/nav-sidebar.tsx`
- Modify: `frontend/app/layout.tsx`

**Interfaces:**
- Consumes: `signIn`/`signOut`/`auth` from `@/auth`.
- Produces: `/sign-in` page (public, excluded from `proxy.ts`'s matcher); nav sidebar shows the signed-in user's avatar + a sign-out control.

- [ ] **Step 1: Sign-in page (Server Component — no client-side data fetching needed)**

```tsx
// frontend/app/sign-in/page.tsx
import { Github, Rocket } from "lucide-react";
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { SignInButton } from "@/components/sign-in/sign-in-button";

export default async function SignInPage() {
  const session = await auth();
  if (session?.user) {
    redirect("/");
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex w-full max-w-sm flex-col items-center gap-6 rounded-lg border p-8 text-center">
        <Rocket className="h-10 w-10 text-sky-500" aria-hidden="true" />
        <div className="space-y-1">
          <h1 className="text-lg font-semibold">GitHub Growth Bot</h1>
          <p className="text-sm text-muted-foreground">
            Sign in with GitHub to track your repos and get AI-synthesized growth recommendations.
          </p>
        </div>
        <SignInButton />
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Github className="h-3.5 w-3.5" aria-hidden="true" />
          Public-repo read access only — we never touch private repos or write to GitHub.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Sign-in button (client component — `signIn()` is an interactive click handler)**

```tsx
// frontend/components/sign-in/sign-in-button.tsx
"use client";

import { Github } from "lucide-react";
import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";

export function SignInButton() {
  return (
    <Button onClick={() => signIn("github", { callbackUrl: "/" })} className="w-full gap-2">
      <Github className="h-4 w-4" aria-hidden="true" />
      Continue with GitHub
    </Button>
  );
}
```

- [ ] **Step 3: Nav sidebar — avatar + sign-out**

```tsx
// frontend/components/nav-sidebar.tsx — full replacement
"use client";

import { Bell, History, LayoutDashboard, LogOut, Settings } from "lucide-react";
import { signOut } from "next-auth/react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SafeImage } from "@/components/safe-image";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard, color: "text-sky-500" },
  { href: "/recommendations", label: "Recommendations", icon: Bell, color: "text-amber-500" },
  { href: "/runs", label: "Pipeline Runs", icon: History, color: "text-violet-500" },
  { href: "/settings", label: "Settings", icon: Settings, color: "text-slate-500" },
];

export function NavSidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();

  return (
    <nav className="flex w-56 shrink-0 flex-col gap-1 border-r p-4">
      {NAV_ITEMS.map(({ href, label, icon: Icon, color }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium",
              active ? "bg-muted" : "hover:bg-muted/50",
            )}
          >
            <Icon className={`h-4 w-4 ${color}`} aria-hidden="true" />
            {label}
          </Link>
        );
      })}

      {session?.user && (
        <div className="mt-auto flex items-center gap-2 border-t pt-4">
          <SafeImage
            src={session.user.image ?? ""}
            alt={session.user.name ?? "Account"}
            width={28}
            height={28}
            className="rounded-full"
          />
          <span className="flex-1 truncate text-sm font-medium">{session.user.name}</span>
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/sign-in" })}
            aria-label="Sign out"
            className="rounded-md p-1.5 hover:bg-muted/50"
          >
            <LogOut className="h-4 w-4 text-rose-500" aria-hidden="true" />
          </button>
        </div>
      )}
    </nav>
  );
}
```

`useSession()` requires the app to be wrapped in Auth.js's `SessionProvider` — add it to the provider stack.

- [ ] **Step 4: Add `SessionProvider` to the layout**

```tsx
// frontend/app/layout.tsx — full replacement
import type { Metadata } from "next";
import { SessionProvider } from "next-auth/react";
import { Toaster } from "@/components/ui/sonner";
import { NavSidebar } from "@/components/nav-sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { QueryProvider } from "@/providers/query-provider";
import { LiveEventsProvider } from "@/providers/live-events-provider";
import { ThemeProvider } from "@/providers/theme-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "GitHub Growth Bot",
  description: "Personal GitHub repo health, benchmarking, and recommendations dashboard.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <body>
        <SessionProvider>
          <ThemeProvider>
            <QueryProvider>
              <LiveEventsProvider>
                <div className="flex min-h-screen">
                  <NavSidebar />
                  <div className="flex-1">
                    <header className="flex items-center justify-between border-b px-6 py-3">
                      <h1 className="text-base font-semibold">GitHub Growth Bot</h1>
                      <ThemeToggle />
                    </header>
                    <main className="p-6">{children}</main>
                  </div>
                </div>
                <Toaster />
              </LiveEventsProvider>
            </QueryProvider>
          </ThemeProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
```

Note: `LiveEventsProvider` (and its `useLiveEvents` hook) subscribes to `/api/events` unconditionally today, including on `/sign-in` where there's no session yet. Task 16 updates the `/api/events` Route Handler to require a session — for an unauthenticated visitor on `/sign-in`, that means the `EventSource` connection will fail immediately with a 401, which the existing `use-live-events.ts` hook doesn't currently distinguish from a network blip. This is a pre-existing hook, not a new one — check `hooks/use-live-events.ts`'s current error handling; if it silently retries forever with no backoff on a hard 401, that's wasted client work worth a small guard (only connect when `session` exists), applied in Task 16 alongside the Route Handler change.

- [ ] **Step 5: Run type-check and lint**

Run: `cd frontend && npx tsc --noEmit && npx eslint .`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add app/sign-in components/sign-in components/nav-sidebar.tsx app/layout.tsx
git commit -m "feat(frontend): sign-in page, nav-sidebar avatar and sign-out"
```

---

### Task 16: `/api/events` per-user auth, `useLiveEvents` session guard

**Files:**
- Modify: `frontend/app/api/events/route.ts`
- Modify: `frontend/hooks/use-live-events.ts`

**Interfaces:**
- Consumes: `auth` from `@/auth`, `mintInternalUserToken` from `@/lib/internal-auth`.
- Produces: the SSE proxy now requires and forwards a real session; `useLiveEvents` only opens the `EventSource` connection when a session exists (read via `useSession()`), matching Task 15's guard note.

- [ ] **Step 1: Update the SSE Route Handler**

```typescript
// frontend/app/api/events/route.ts
import { auth } from "@/auth";
import { mintInternalUserToken } from "@/lib/internal-auth";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  const githubId = session?.user?.id;
  if (!githubId) {
    return new Response(null, { status: 401 });
  }

  const baseUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  const apiKey = process.env.BACKEND_API_KEY ?? "";

  const backendResponse = await fetch(`${baseUrl}/events`, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "X-Internal-User-Token": mintInternalUserToken(githubId),
    },
    cache: "no-store",
  });

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
```

- [ ] **Step 2: Read the current `use-live-events.ts` before changing it**

Read `frontend/hooks/use-live-events.ts` in full. Confirm its current `useEffect` opens `new EventSource("/api/events")` unconditionally on mount. Add a session guard so it never opens a connection (and never triggers a needless 401) when signed out:

```typescript
// frontend/hooks/use-live-events.ts — add this near the top of the hook function
"use client";

import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";

const EVENT_QUERY_MAP: Record<string, QueryKey[]> = {
  repo_added: [queryKeys.repos.all],
  repo_removed: [queryKeys.repos.all],
  recommendation_updated: [queryKeys.recommendations.all],
  run_completed: [queryKeys.runs.all, queryKeys.repos.all, queryKeys.recommendations.all],
};

export function useLiveEvents() {
  const queryClient = useQueryClient();
  const { status } = useSession();

  useEffect(() => {
    if (status !== "authenticated") {
      return;
    }

    const source = new EventSource("/api/events");

    const handler = (event: MessageEvent) => {
      const keysToInvalidate = EVENT_QUERY_MAP[event.type] ?? [];
      for (const key of keysToInvalidate) {
        queryClient.invalidateQueries({ queryKey: key });
      }
    };

    for (const eventType of Object.keys(EVENT_QUERY_MAP)) {
      source.addEventListener(eventType, handler);
    }

    return () => {
      source.close();
    };
  }, [queryClient, status]);
}
```

This preserves the exact `EVENT_QUERY_MAP` this project's final-review fix already established (all 3 keys on `run_completed`) — only the `status !== "authenticated"` guard and the `useSession` import are new. Confirm this against the real current file content before writing it (the map above must match verbatim, not be reconstructed from memory).

- [ ] **Step 3: Verify types and existing SSE test still passes**

Run: `cd frontend && npx tsc --noEmit && npm test -- use-live-events`
Expected: both clean — check the existing `tests/use-live-events.test.tsx` (`FakeEventSource` pattern) for whether it needs a `SessionProvider` wrapper or a mocked `useSession` now that the hook calls it; if the test fails only because `useSession` has no provider in the test's render tree, wrap the test's render call in `<SessionProvider session={{ user: { id: "12345" }, expires: "..." }}>` or mock `next-auth/react`'s `useSession` directly — read the existing test file first to match its established mocking style before choosing.

- [ ] **Step 4: Commit**

```bash
cd frontend
git add app/api/events/route.ts hooks/use-live-events.ts tests/
git commit -m "feat(frontend): per-user SSE auth, skip connecting when signed out"
```

---

### Task 17: Frontend test suite, lint, build — whole-frontend checkpoint

**Files:**
- No new files — verification only, fixing anything that surfaces.

- [ ] **Step 1: Full type-check, lint, test, build**

Run: `cd frontend && npx tsc --noEmit && npx eslint . && npm test && npm run build`
Expected: all four clean. Fix anything that surfaces — do not skip any of the four checks.

- [ ] **Step 2: `npm audit`**

Run: `cd frontend && npm audit`
Expected: no new vulnerabilities beyond the already-accepted `RISK-0012` (postcss, documented and accepted). If `next-auth` introduces anything new, treat it exactly like this project's established CVE-fix precedent (RISK-0013) — bump, don't ignore.

- [ ] **Step 3: Commit any fixes surfaced by Steps 1-2**

---

### Task 18: End-to-end live verification, final whole-branch review

This task has no automated test of its own — it's the live confirmation that everything wired across Tasks 1-17 actually works together, and the point where this plan's one open spec risk (public_repo scope sufficiency for traffic endpoints, spec §9) gets its real-world answer.

- [ ] **Step 1: Start both servers**

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload &
cd frontend && npm run dev &
```

- [ ] **Step 2: Real GitHub OAuth sign-in**

Requires a real GitHub OAuth App registered with callback `http://localhost:3000/api/auth/callback/github` (Task 12, Step 2) and its `AUTH_GITHUB_ID`/`AUTH_GITHUB_SECRET` in `frontend/.env.local`. Visit `http://localhost:3000`, confirm redirect to `/sign-in`, click "Continue with GitHub", complete the real OAuth consent screen, confirm redirect back to `/` with the nav sidebar showing your real GitHub avatar and username.

- [ ] **Step 3: Verify the `public_repo` scope resolves the spec's open risk**

Add one of your own real public repos via the dashboard. Confirm the next pipeline run (trigger manually via "Run now") successfully populates real traffic views/clones/referrers/popular-paths data for it — not empty/error rows. If this fails specifically with a 403/404 from GitHub's traffic endpoints (not a 401 — a 401 would mean the token itself is bad, a 403/404 here specifically would mean the scope is insufficient), that confirms spec §9's risk was real: escalate to the Product Owner before proceeding further, since it means "public repos only" (spec §2) needs revisiting.

- [ ] **Step 4: Cross-user isolation, live**

In a second browser (or private window), sign in with a different real GitHub account. Confirm this second account sees zero repos (not the first account's), and that adding a repo here doesn't appear in the first account's Overview page.

- [ ] **Step 5: Instant cross-tab updates, still working post-auth**

With both accounts' dashboards open in separate tabs, dismiss a recommendation in one of account A's tabs — confirm it updates instantly in account A's OTHER open tab, and confirms it does NOT appear/change in account B's tab (proving the per-user SSE scoping from Task 5/16 actually works live, not just in unit tests).

- [ ] **Step 6: Rate limiting, live**

Rapidly click "Track a repo" more than 10 times within a minute (or script `curl` calls against `POST /repos` with a real session's headers) — confirm a 429 eventually surfaces, and that the frontend's existing `onError` toast (already wired per the earlier frontend plan) shows something reasonable rather than a raw crash.

- [ ] **Step 7: Dispatch the final whole-branch review**

Per `superpowers:subagent-driven-development`'s pattern — one fresh, most-capable-model reviewer across the full diff from this plan's first commit through its last, checking especially: the defense-in-depth chain end-to-end (can a request skip any layer?), that no OAuth token or `INTERNAL_AUTH_SECRET`/`TOKEN_ENCRYPTION_KEY` value is logged or returned anywhere, and that every one of the 8 previously-global tables is genuinely unreachable cross-user (not just at the API layer, but checking there's no lingering direct-query path that forgot the `user_id` filter).

- [ ] **Step 8: Update governance**

Update `.agile-v/REQUIREMENTS.md` (new REQ ids for the multi-tenant SaaS requirements, tracing to this plan), `.agile-v/RISK_REGISTER.md` (close out spec §9's risk with its real-world verified answer from Step 3), `.agile-v/STATE.md`, `docs/PROJECT_PLAN.md` (Phase 2 → done), matching this project's established governance-update pattern from every prior phase.
