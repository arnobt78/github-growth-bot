# GitHub Growth Bot — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python/FastAPI backend for the GitHub Growth Bot Phase 1 — the 7-stage
analytics pipeline (Extractor→Preprocessor→Analyzer→Optimizer→Synthesizer→Validator→Assembler),
multi-provider LLM fallback router, Postgres-backed history, and the REST+SSE API the (later)
Next.js dashboard will consume.

**Architecture:** FastAPI app with SQLAlchemy/Postgres, a plain-Python pipeline of `Stage`
objects run by a `PipelineRunner`, an `httpx`-based `LLMRouter` with provider fallback, an
in-process asyncio broadcaster for SSE, and APScheduler for the daily trigger — all in one
Docker container per the user's existing Coolify deployment pattern.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x + Alembic, Postgres, httpx, APScheduler,
pytest, pydantic-settings.

## Global Constraints

- Python 3.12-slim base image, non-root Docker user, `.dockerignore` excludes `.git`/`.env*`/`__pycache__`/tests — per `docs/DOCKER_VPS_BACKEND_PLAYBOOK.md`.
- Endpoint paths never contain `analytics`, `analysis`, `tracking`, `performance`, or `metrics` (ad-blocker filter avoidance) — use `insights`, `snapshots`, `benchmarks`, `runs` instead.
- LLM fallback order is exactly: Groq → Gemini → OpenRouter (`:free` models) → Hugging Face → Cloudflare Workers AI → Vercel AI Gateway. Never stop after one provider failure.
- Groq models: `openai/gpt-oss-120b`, `qwen/qwen3.6-27b`, `openai/gpt-oss-20b` only — never `llama-3.1-8b-instant` or `llama-3.3-70b-versatile` (deprecated, shutdown 2026-08-16).
- All endpoints require `Authorization: Bearer <API_KEY>` (static, env-configured) except `GET /api/health`.
- No artificial star/fork/traffic inflation anywhere in this codebase — it is a hard non-goal.
- No dead code, no debug print statements left in, no placeholder/TODO logic — every function shipped must be complete and correct.
- Config via environment variables only (pydantic-settings), never hardcoded secrets.

---

## File Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app, startup (APScheduler), router includes
│   ├── config.py                # pydantic-settings Settings
│   ├── db.py                    # SQLAlchemy engine/session
│   ├── models.py                # ORM models
│   ├── github_client.py         # GitHub REST API wrapper
│   ├── llm_router.py            # multi-provider LLM fallback router
│   ├── events.py                # in-process asyncio SSE broadcaster
│   ├── pipeline/
│   │   ├── base.py              # PipelineContext, Stage
│   │   ├── extractor.py
│   │   ├── preprocessor.py
│   │   ├── analyzer.py
│   │   ├── optimizer.py
│   │   ├── synthesizer.py
│   │   ├── validator.py
│   │   ├── assembler.py
│   │   └── runner.py            # PipelineRunner
│   └── api/
│       ├── repos.py
│       ├── insights.py
│       ├── recommendations.py
│       ├── runs.py
│       ├── providers.py
│       └── events.py
├── alembic/                     # migrations
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_models.py
│   ├── test_repos_api.py
│   ├── test_github_client.py
│   ├── test_extractor_preprocessor.py
│   ├── test_analyzer_optimizer.py
│   ├── test_llm_router.py
│   ├── test_synthesizer_validator.py
│   ├── test_runner.py
│   ├── test_read_endpoints.py
│   └── test_events.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
└── .env.example
```

---

### Task 1: Project scaffold, config, health endpoint, Dockerfile

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`
- Create: `backend/.env.example`
- Test: `backend/tests/test_health.py`
- Test: `backend/tests/conftest.py`

**Interfaces:**
- Produces: `app.config.Settings` (pydantic-settings, fields: `database_url: str`, `api_key: str`, `github_token: str`, `groq_api_key: str = ""`, `gemini_api_key: str = ""`, `openrouter_api_key: str = ""`, `huggingface_api_key: str = ""`, `cloudflare_api_key: str = ""`, `cloudflare_account_id: str = ""`, `vercel_ai_gateway_key: str = ""`, `cors_origins: list[str] = []`), `app.config.get_settings()` (cached singleton).
- Produces: `app.main.app` (FastAPI instance), `GET /api/health` returning `{"status": "ok"}`.

- [ ] **Step 1: Write `requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
alembic==1.14.0
psycopg[binary]==3.2.3
pydantic-settings==2.7.0
httpx==0.28.1
apscheduler==3.11.0
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 2: Write the failing test for config + health**

```python
# backend/tests/conftest.py
import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("GITHUB_TOKEN", "test-token")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
```

```python
# backend/tests/test_health.py
def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'` or `app.main` not found.

- [ ] **Step 4: Write `app/config.py`**

```python
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Write `app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(title="GitHub Growth Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 7: Write `Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=3000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN groupadd --system --gid 10001 appgroup \
    && useradd --system --uid 10001 --gid appgroup --home-dir /app --no-create-home appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,os; p=os.environ.get('PORT','3000'); urllib.request.urlopen('http://127.0.0.1:'+p+'/api/health')" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
```

- [ ] **Step 8: Write `.dockerignore`**

```
.git
.env
.env.*
!.env.example
__pycache__
*.pyc
.venv
venv
.pytest_cache
tests/
```

- [ ] **Step 9: Write `.env.example`**

```
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/github_growth_bot
API_KEY=change-me
GITHUB_TOKEN=ghp_xxx
GROQ_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
HUGGINGFACE_API_KEY=
CLOUDFLARE_API_KEY=
CLOUDFLARE_ACCOUNT_ID=
VERCEL_AI_GATEWAY_KEY=
CORS_ORIGINS=["http://localhost:3001"]
```

- [ ] **Step 10: Commit**

```bash
git add backend/requirements.txt backend/app/__init__.py backend/app/config.py backend/app/main.py backend/Dockerfile backend/.dockerignore backend/.env.example backend/tests/conftest.py backend/tests/test_health.py
git commit -m "feat(backend): scaffold FastAPI app with config and health endpoint"
```

---

### Task 2: Database layer and ORM models

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Task 1).
- Produces: `app.db.engine`, `app.db.SessionLocal`, `app.db.Base`, `app.db.get_db()` (FastAPI dependency yielding a session).
- Produces ORM models: `Repo(id, owner, name, tracked_since)`, `Snapshot(id, repo_id, date, stars, forks, watchers, open_issues, views_14d, unique_views_14d, clones_14d, unique_clones_14d)`, `BenchmarkRepo(id, source_repo_id, full_name, stars, forks, topics, captured_at)`, `Referrer(id, repo_id, date, referrer, count, uniques)`, `PopularPath(id, repo_id, date, path, count, uniques)`, `PipelineRun(id, started_at, finished_at, status)`, `StageRun(id, pipeline_run_id, stage_name, status, duration_ms, error)`, `Recommendation(id, repo_id, snapshot_id, category, title, body, validated, dismissed, created_at)`, `LLMUsage(id, provider, date, call_count)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_models.py
from app.db import Base, engine, SessionLocal
from app.models import Repo


def test_create_and_query_repo():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()

    fetched = db.query(Repo).filter_by(owner="octocat", name="hello-world").first()
    assert fetched is not None
    assert fetched.name == "hello-world"
    assert fetched.tracked_since is not None
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write `app/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Write `app/models.py`**

```python
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


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    tracked_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
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
    source_repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
    full_name: Mapped[str] = mapped_column(String(255))
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Referrer(Base):
    __tablename__ = "referrers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
    date: Mapped[date] = mapped_column(Date)
    referrer: Mapped[str] = mapped_column(String(255))
    count: Mapped[int] = mapped_column(Integer, default=0)
    uniques: Mapped[int] = mapped_column(Integer, default=0)


class PopularPath(Base):
    __tablename__ = "popular_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
    date: Mapped[date] = mapped_column(Date)
    path: Mapped[str] = mapped_column(String(500))
    count: Mapped[int] = mapped_column(Integer, default=0)
    uniques: Mapped[int] = mapped_column(Integer, default=0)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running")


class StageRun(Base):
    __tablename__ = "stage_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"))
    stage_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"))
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("snapshots.id"), nullable=True)
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

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Set up Alembic for real (Postgres) migrations**

Run: `cd backend && alembic init alembic`

Edit `backend/alembic/env.py` — replace the `target_metadata = None` line and add imports at top:

```python
# add near the top, after existing imports
from app.db import Base
from app.models import *  # noqa: F401,F403  (registers all models on Base.metadata)
from app.config import get_settings

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", get_settings().database_url)
```

Run: `cd backend && alembic revision --autogenerate -m "initial schema"`
Expected: generates `backend/alembic/versions/0001_initial.py` (or similarly named) with `op.create_table(...)` for all 9 tables.

- [ ] **Step 7: Commit**

```bash
git add backend/app/db.py backend/app/models.py backend/alembic.ini backend/alembic/
git commit -m "feat(backend): add SQLAlchemy models and Alembic migrations"
```

---

### Task 3: Repos CRUD API

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/repos.py`
- Create: `backend/app/deps.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_repos_api.py`

**Interfaces:**
- Consumes: `app.db.get_db` (Task 2), `app.models.Repo` (Task 2), `app.config.get_settings` (Task 1).
- Produces: `app.deps.require_api_key` (FastAPI dependency checking `Authorization: Bearer` header), router mounted at `/repos` with `GET /repos`, `POST /repos`, `GET /repos/{id}`, `DELETE /repos/{id}`.

- [ ] **Step 1: Add auth header to test client fixture**

```python
# backend/tests/conftest.py — replace the client fixture with:
@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    test_client = TestClient(app)
    test_client.headers.update({"Authorization": "Bearer test-key"})
    return test_client


@pytest.fixture(autouse=True)
def _reset_db():
    from app.db import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_repos_api.py
def test_create_list_get_delete_repo(client):
    create_resp = client.post("/repos", json={"owner": "octocat", "name": "hello-world"})
    assert create_resp.status_code == 201
    repo_id = create_resp.json()["id"]

    list_resp = client.get("/repos")
    assert list_resp.status_code == 200
    assert any(r["id"] == repo_id for r in list_resp.json())

    get_resp = client.get(f"/repos/{repo_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["owner"] == "octocat"

    delete_resp = client.delete(f"/repos/{repo_id}")
    assert delete_resp.status_code == 204

    missing_resp = client.get(f"/repos/{repo_id}")
    assert missing_resp.status_code == 404


def test_requires_api_key():
    from fastapi.testclient import TestClient
    from app.main import app
    unauthenticated = TestClient(app)
    resp = unauthenticated.get("/repos")
    assert resp.status_code == 401
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_repos_api.py -v`
Expected: FAIL — 404 on `/repos` (router not mounted).

- [ ] **Step 4: Write `app/deps.py`**

```python
from fastapi import Header, HTTPException

from app.config import get_settings


def require_api_key(authorization: str = Header(default="")) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.api_key}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
```

- [ ] **Step 5: Write `app/api/repos.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import Repo

router = APIRouter(prefix="/repos", tags=["repos"], dependencies=[Depends(require_api_key)])


class RepoCreate(BaseModel):
    owner: str
    name: str


class RepoOut(BaseModel):
    id: int
    owner: str
    name: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[RepoOut])
def list_repos(db: Session = Depends(get_db)) -> list[Repo]:
    return db.query(Repo).all()


@router.post("", response_model=RepoOut, status_code=201)
def create_repo(payload: RepoCreate, db: Session = Depends(get_db)) -> Repo:
    repo = Repo(owner=payload.owner, name=payload.name)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


@router.get("/{repo_id}", response_model=RepoOut)
def get_repo(repo_id: int, db: Session = Depends(get_db)) -> Repo:
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo


@router.delete("/{repo_id}", status_code=204)
def delete_repo(repo_id: int, db: Session = Depends(get_db)) -> None:
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    db.delete(repo)
    db.commit()
```

- [ ] **Step 6: Mount the router in `app/main.py`**

```python
# app/main.py — add import and include_router call
from app.api.repos import router as repos_router

app.include_router(repos_router)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_repos_api.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/deps.py backend/app/api/ backend/app/main.py backend/tests/
git commit -m "feat(backend): add repos CRUD API with API-key auth"
```

---

### Task 4: GitHub client

**Files:**
- Create: `backend/app/github_client.py`
- Test: `backend/tests/test_github_client.py`

**Interfaces:**
- Consumes: nothing new (plain `httpx.Client`, GitHub token string).
- Produces: `app.github_client.GitHubClient` with methods `get_repo(owner, name) -> dict`, `get_traffic_views(owner, name) -> dict`, `get_traffic_clones(owner, name) -> dict`, `get_referrers(owner, name) -> list[dict]`, `get_popular_paths(owner, name) -> list[dict]`, `get_readme(owner, name) -> str | None`, `has_file(owner, name, path) -> bool`, `search_similar_repos(language, topic, limit=5) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_github_client.py
import httpx
import pytest

from app.github_client import GitHubClient


@pytest.fixture
def mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octocat/hello-world":
            return httpx.Response(200, json={"stargazers_count": 42, "forks_count": 7, "watchers_count": 42, "open_issues_count": 3})
        if request.url.path == "/repos/octocat/hello-world/traffic/views":
            return httpx.Response(200, json={"count": 100, "uniques": 50})
        if request.url.path == "/repos/octocat/hello-world/traffic/clones":
            return httpx.Response(200, json={"count": 20, "uniques": 10})
        if request.url.path == "/repos/octocat/hello-world/traffic/popular/referrers":
            return httpx.Response(200, json=[{"referrer": "google.com", "count": 5, "uniques": 3}])
        if request.url.path == "/repos/octocat/hello-world/traffic/popular/paths":
            return httpx.Response(200, json=[{"path": "/", "count": 10, "uniques": 8}])
        if request.url.path == "/repos/octocat/hello-world/readme":
            return httpx.Response(200, json={"content": "SGVsbG8="})
        if request.url.path == "/repos/octocat/hello-world/contents/LICENSE":
            return httpx.Response(200, json={})
        if request.url.path == "/search/repositories":
            return httpx.Response(200, json={"items": [{"full_name": "similar/repo", "stargazers_count": 100, "forks_count": 20, "topics": ["python"]}]})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def gh_client(mock_transport):
    http = httpx.Client(base_url="https://api.github.com", transport=mock_transport)
    return GitHubClient(token="fake-token", http_client=http)


def test_get_repo(gh_client):
    data = gh_client.get_repo("octocat", "hello-world")
    assert data["stargazers_count"] == 42


def test_get_traffic_views(gh_client):
    data = gh_client.get_traffic_views("octocat", "hello-world")
    assert data["count"] == 100


def test_get_readme_decodes_base64(gh_client):
    text = gh_client.get_readme("octocat", "hello-world")
    assert text == "Hello"


def test_has_file_true(gh_client):
    assert gh_client.has_file("octocat", "hello-world", "LICENSE") is True


def test_has_file_false(gh_client):
    assert gh_client.has_file("octocat", "hello-world", "CONTRIBUTING.md") is False


def test_search_similar_repos(gh_client):
    results = gh_client.search_similar_repos(language="python", topic="cli", limit=5)
    assert results[0]["full_name"] == "similar/repo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_github_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.github_client'`

- [ ] **Step 3: Write `app/github_client.py`**

```python
import base64

import httpx


class GitHubClient:
    def __init__(self, token: str, http_client: httpx.Client | None = None):
        self._http = http_client or httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=15.0,
        )

    def get_repo(self, owner: str, name: str) -> dict:
        resp = self._http.get(f"/repos/{owner}/{name}")
        resp.raise_for_status()
        return resp.json()

    def get_traffic_views(self, owner: str, name: str) -> dict:
        resp = self._http.get(f"/repos/{owner}/{name}/traffic/views")
        resp.raise_for_status()
        return resp.json()

    def get_traffic_clones(self, owner: str, name: str) -> dict:
        resp = self._http.get(f"/repos/{owner}/{name}/traffic/clones")
        resp.raise_for_status()
        return resp.json()

    def get_referrers(self, owner: str, name: str) -> list[dict]:
        resp = self._http.get(f"/repos/{owner}/{name}/traffic/popular/referrers")
        resp.raise_for_status()
        return resp.json()

    def get_popular_paths(self, owner: str, name: str) -> list[dict]:
        resp = self._http.get(f"/repos/{owner}/{name}/traffic/popular/paths")
        resp.raise_for_status()
        return resp.json()

    def get_readme(self, owner: str, name: str) -> str | None:
        resp = self._http.get(f"/repos/{owner}/{name}/readme")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        content = resp.json().get("content", "")
        return base64.b64decode(content).decode("utf-8", errors="replace")

    def has_file(self, owner: str, name: str, path: str) -> bool:
        resp = self._http.get(f"/repos/{owner}/{name}/contents/{path}")
        return resp.status_code == 200

    def search_similar_repos(self, language: str, topic: str, limit: int = 5) -> list[dict]:
        query = f"language:{language} topic:{topic}"
        resp = self._http.get("/search/repositories", params={"q": query, "sort": "stars", "per_page": limit})
        resp.raise_for_status()
        return resp.json().get("items", [])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_github_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/github_client.py backend/tests/test_github_client.py
git commit -m "feat(backend): add GitHub REST API client"
```

---

### Task 5: Pipeline base, Extractor, Preprocessor stages

**Files:**
- Create: `backend/app/pipeline/__init__.py`
- Create: `backend/app/pipeline/base.py`
- Create: `backend/app/pipeline/extractor.py`
- Create: `backend/app/pipeline/preprocessor.py`
- Test: `backend/tests/test_extractor_preprocessor.py`

**Interfaces:**
- Consumes: `app.github_client.GitHubClient` (Task 4), `app.models.Repo`, `app.models.Snapshot` (Task 2).
- Produces: `PipelineContext(repo, raw=dict, normalized=dict, findings=list, ranked_findings=list, narrative=str|None, recommendations=list, errors=list)`, `Stage` base class with `name: str` and `run(self, ctx: PipelineContext) -> PipelineContext`, `Extractor(gh_client)`, `Preprocessor(db_session)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_extractor_preprocessor.py
from datetime import date
from unittest.mock import MagicMock

from app.db import Base, SessionLocal, engine
from app.models import Repo, Snapshot
from app.pipeline.base import PipelineContext
from app.pipeline.extractor import Extractor
from app.pipeline.preprocessor import Preprocessor


def _fake_gh_client():
    gh = MagicMock()
    gh.get_repo.return_value = {"stargazers_count": 110, "forks_count": 12, "watchers_count": 110, "open_issues_count": 4, "description": "A tool", "topics": ["cli"], "language": "Python"}
    gh.get_traffic_views.return_value = {"count": 200, "uniques": 90}
    gh.get_traffic_clones.return_value = {"count": 30, "uniques": 15}
    gh.get_referrers.return_value = [{"referrer": "news.ycombinator.com", "count": 40, "uniques": 30}]
    gh.get_popular_paths.return_value = [{"path": "/", "count": 50, "uniques": 40}]
    gh.get_readme.return_value = "# My Repo"
    gh.has_file.return_value = False
    gh.search_similar_repos.return_value = [{"full_name": "other/repo", "stargazers_count": 500, "forks_count": 50, "topics": ["cli"]}]
    return gh


def test_extractor_populates_raw():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()
    db.refresh(repo)

    ctx = PipelineContext(repo=repo)
    extractor = Extractor(gh_client=_fake_gh_client())
    ctx = extractor.run(ctx)

    assert ctx.raw["repo"]["stargazers_count"] == 110
    assert ctx.raw["traffic_views"]["count"] == 200
    assert ctx.raw["benchmarks"][0]["full_name"] == "other/repo"
    assert ctx.raw["has_license"] is False
    db.close()


def test_preprocessor_diffs_against_previous_snapshot():
    db = SessionLocal()
    repo = db.query(Repo).first()
    db.add(Snapshot(repo_id=repo.id, date=date(2026, 7, 19), stars=100, forks=10, watchers=100, open_issues=5))
    db.commit()

    ctx = PipelineContext(repo=repo)
    ctx.raw = {
        "repo": {"stargazers_count": 110, "forks_count": 12, "watchers_count": 110, "open_issues_count": 4},
        "traffic_views": {"count": 200, "uniques": 90},
        "traffic_clones": {"count": 30, "uniques": 15},
        "referrers": [{"referrer": "news.ycombinator.com", "count": 40, "uniques": 30}],
        "popular_paths": [{"path": "/", "count": 50, "uniques": 40}],
        "benchmarks": [{"full_name": "other/repo", "stargazers_count": 500, "forks_count": 50, "topics": ["cli"]}],
        "has_license": False,
        "has_contributing": False,
        "readme": "# My Repo",
        "topics": ["cli"],
    }

    preprocessor = Preprocessor(db_session=db)
    ctx = preprocessor.run(ctx)

    assert ctx.normalized["stars"] == 110
    assert ctx.normalized["stars_delta"] == 10
    assert ctx.normalized["forks_delta"] == 2
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_extractor_preprocessor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline'`

- [ ] **Step 3: Write `app/pipeline/base.py`**

```python
from dataclasses import dataclass, field
from typing import Any

from app.models import Repo


@dataclass
class PipelineContext:
    repo: Repo
    raw: dict[str, Any] = field(default_factory=dict)
    normalized: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    ranked_findings: list[dict[str, Any]] = field(default_factory=list)
    narrative: str | None = None
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Stage:
    name: str = "stage"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        raise NotImplementedError
```

- [ ] **Step 4: Write `app/pipeline/extractor.py`**

```python
from app.github_client import GitHubClient
from app.pipeline.base import PipelineContext, Stage


class Extractor(Stage):
    name = "extractor"

    def __init__(self, gh_client: GitHubClient):
        self.gh_client = gh_client

    def run(self, ctx: PipelineContext) -> PipelineContext:
        owner, name = ctx.repo.owner, ctx.repo.name
        repo_data = self.gh_client.get_repo(owner, name)

        ctx.raw = {
            "repo": repo_data,
            "traffic_views": self.gh_client.get_traffic_views(owner, name),
            "traffic_clones": self.gh_client.get_traffic_clones(owner, name),
            "referrers": self.gh_client.get_referrers(owner, name),
            "popular_paths": self.gh_client.get_popular_paths(owner, name),
            "readme": self.gh_client.get_readme(owner, name),
            "has_license": self.gh_client.has_file(owner, name, "LICENSE"),
            "has_contributing": self.gh_client.has_file(owner, name, "CONTRIBUTING.md"),
            "topics": repo_data.get("topics", []),
            "benchmarks": self._get_benchmarks(repo_data),
        }
        return ctx

    def _get_benchmarks(self, repo_data: dict) -> list[dict]:
        language = repo_data.get("language") or ""
        topics = repo_data.get("topics") or []
        if not language or not topics:
            return []
        return self.gh_client.search_similar_repos(language=language, topic=topics[0], limit=5)
```

- [ ] **Step 5: Write `app/pipeline/preprocessor.py`**

```python
from datetime import date, timezone, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Snapshot
from app.pipeline.base import PipelineContext, Stage


class Preprocessor(Stage):
    name = "preprocessor"

    def __init__(self, db_session: Session):
        self.db = db_session

    def run(self, ctx: PipelineContext) -> PipelineContext:
        repo_data = ctx.raw["repo"]
        stars = repo_data.get("stargazers_count", 0)
        forks = repo_data.get("forks_count", 0)
        watchers = repo_data.get("watchers_count", 0)
        open_issues = repo_data.get("open_issues_count", 0)

        previous = (
            self.db.execute(
                select(Snapshot)
                .where(Snapshot.repo_id == ctx.repo.id)
                .order_by(Snapshot.date.desc())
            )
            .scalars()
            .first()
        )

        ctx.normalized = {
            "date": datetime.now(timezone.utc).date(),
            "stars": stars,
            "forks": forks,
            "watchers": watchers,
            "open_issues": open_issues,
            "stars_delta": stars - previous.stars if previous else 0,
            "forks_delta": forks - previous.forks if previous else 0,
            "views_14d": ctx.raw["traffic_views"].get("count", 0),
            "unique_views_14d": ctx.raw["traffic_views"].get("uniques", 0),
            "clones_14d": ctx.raw["traffic_clones"].get("count", 0),
            "unique_clones_14d": ctx.raw["traffic_clones"].get("uniques", 0),
            "referrers": ctx.raw["referrers"],
            "popular_paths": ctx.raw["popular_paths"],
            "benchmarks": ctx.raw["benchmarks"],
            "has_license": ctx.raw["has_license"],
            "has_contributing": ctx.raw["has_contributing"],
            "readme": ctx.raw["readme"],
            "topics": ctx.raw["topics"],
        }
        return ctx
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_extractor_preprocessor.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/pipeline/ backend/tests/test_extractor_preprocessor.py
git commit -m "feat(backend): add pipeline base, Extractor and Preprocessor stages"
```

---

### Task 6: Analyzer and Optimizer stages

**Files:**
- Create: `backend/app/pipeline/analyzer.py`
- Create: `backend/app/pipeline/optimizer.py`
- Test: `backend/tests/test_analyzer_optimizer.py`

**Interfaces:**
- Consumes: `PipelineContext.normalized` dict (Task 5, exact keys: `stars`, `stars_delta`, `forks_delta`, `benchmarks`, `has_license`, `has_contributing`, `topics`, `referrers`).
- Produces: `Analyzer` (fills `ctx.findings: list[dict]`, each `{"category": str, "message": str, "impact": int, "effort": int}`), `Optimizer` (fills `ctx.ranked_findings: list[dict]`, same shape, sorted by `impact - effort` descending, top 10 only).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_analyzer_optimizer.py
from app.models import Repo
from app.pipeline.analyzer import Analyzer
from app.pipeline.base import PipelineContext
from app.pipeline.optimizer import Optimizer


def _ctx_with_normalized(**overrides) -> PipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = PipelineContext(repo=repo)
    ctx.normalized = {
        "stars": 110,
        "stars_delta": 10,
        "forks_delta": 2,
        "benchmarks": [{"full_name": "other/repo", "stargazers_count": 500, "forks_count": 50, "topics": ["cli"]}],
        "has_license": False,
        "has_contributing": False,
        "topics": [],
        "referrers": [{"referrer": "news.ycombinator.com", "count": 400, "uniques": 300}],
    }
    ctx.normalized.update(overrides)
    return ctx


def test_analyzer_flags_missing_license_and_topics():
    ctx = _ctx_with_normalized()
    ctx = Analyzer().run(ctx)

    categories = {f["category"] for f in ctx.findings}
    assert "missing_license" in categories
    assert "missing_topics" in categories
    assert "referrer_spike" in categories


def test_analyzer_percentile_vs_benchmarks():
    ctx = _ctx_with_normalized()
    ctx = Analyzer().run(ctx)
    percentile_finding = next(f for f in ctx.findings if f["category"] == "benchmark_gap")
    assert "500" in percentile_finding["message"]


def test_optimizer_ranks_and_caps_at_ten():
    ctx = _ctx_with_normalized()
    ctx = Analyzer().run(ctx)
    ctx = Optimizer().run(ctx)

    assert len(ctx.ranked_findings) <= 10
    impacts = [f["impact"] - f["effort"] for f in ctx.ranked_findings]
    assert impacts == sorted(impacts, reverse=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_analyzer_optimizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.analyzer'`

- [ ] **Step 3: Write `app/pipeline/analyzer.py`**

```python
from app.pipeline.base import PipelineContext, Stage


class Analyzer(Stage):
    name = "analyzer"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        n = ctx.normalized
        findings: list[dict] = []

        if not n.get("has_license"):
            findings.append({"category": "missing_license", "message": "This repo has no LICENSE file, which discourages adoption and contributions.", "impact": 7, "effort": 1})

        if not n.get("has_contributing"):
            findings.append({"category": "missing_contributing", "message": "No CONTRIBUTING.md — first-time contributors have no guidance.", "impact": 4, "effort": 2})

        if not n.get("topics"):
            findings.append({"category": "missing_topics", "message": "No repository topics set, which hurts GitHub search discoverability.", "impact": 6, "effort": 1})

        benchmarks = n.get("benchmarks", [])
        if benchmarks:
            avg_benchmark_stars = sum(b["stargazers_count"] for b in benchmarks) / len(benchmarks)
            if avg_benchmark_stars > n.get("stars", 0):
                findings.append({
                    "category": "benchmark_gap",
                    "message": f"Similar repos average {int(avg_benchmark_stars)} stars vs. this repo's {n.get('stars', 0)}.",
                    "impact": 5,
                    "effort": 5,
                })

        referrers = n.get("referrers", [])
        if referrers:
            top_referrer = max(referrers, key=lambda r: r["count"])
            if top_referrer["count"] >= 100:
                findings.append({
                    "category": "referrer_spike",
                    "message": f"Traffic spike from {top_referrer['referrer']} ({top_referrer['count']} views) — worth capitalizing on.",
                    "impact": 6,
                    "effort": 3,
                })

        ctx.findings = findings
        return ctx
```

- [ ] **Step 4: Write `app/pipeline/optimizer.py`**

```python
from app.pipeline.base import PipelineContext, Stage


class Optimizer(Stage):
    name = "optimizer"
    max_findings = 10

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ranked = sorted(ctx.findings, key=lambda f: f["impact"] - f["effort"], reverse=True)
        ctx.ranked_findings = ranked[: self.max_findings]
        return ctx
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_analyzer_optimizer.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/pipeline/analyzer.py backend/app/pipeline/optimizer.py backend/tests/test_analyzer_optimizer.py
git commit -m "feat(backend): add Analyzer and Optimizer pipeline stages"
```

---

### Task 7: LLM Router (multi-provider fallback)

**Files:**
- Create: `backend/app/llm_router.py`
- Test: `backend/tests/test_llm_router.py`

**Interfaces:**
- Consumes: `app.config.Settings` (Task 1), `app.models.LLMUsage` (Task 2), SQLAlchemy `Session`.
- Produces: `LLMRouter(settings, db_session)` with `chat_completion(messages: list[dict[str, str]]) -> str`, raising `LLMRouterError` only if every provider fails.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_llm_router.py
import httpx
import pytest

from app.config import Settings
from app.db import Base, SessionLocal, engine
from app.llm_router import LLMRouter, LLMRouterError


def _settings(**overrides) -> Settings:
    base = dict(
        database_url="sqlite:///:memory:",
        api_key="k",
        github_token="t",
        groq_api_key="groq-key",
        gemini_api_key="gemini-key",
        openrouter_api_key="",
        huggingface_api_key="",
        cloudflare_api_key="",
        cloudflare_account_id="",
        vercel_ai_gateway_key="",
    )
    base.update(overrides)
    return Settings(**base)


def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def test_uses_first_provider_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "groq.com" in str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello from groq"}}]})

    router = LLMRouter(settings=_settings(), db_session=_db(), transport=httpx.MockTransport(handler))
    result = router.chat_completion([{"role": "user", "content": "hi"}])
    assert result == "hello from groq"


def test_falls_back_to_next_provider_on_429():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "groq.com" in str(request.url):
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello from gemini"}}]})

    router = LLMRouter(settings=_settings(), db_session=_db(), transport=httpx.MockTransport(handler))
    result = router.chat_completion([{"role": "user", "content": "hi"}])
    assert result == "hello from gemini"
    assert any("groq.com" in c for c in calls)
    assert any("generativelanguage" in c for c in calls)


def test_raises_when_all_providers_fail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    router = LLMRouter(settings=_settings(), db_session=_db(), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMRouterError):
        router.chat_completion([{"role": "user", "content": "hi"}])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_llm_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm_router'`

- [ ] **Step 3: Write `app/llm_router.py`**

```python
from dataclasses import dataclass
from datetime import date, timezone, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import LLMUsage


class LLMRouterError(Exception):
    pass


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    models: list[str]
    headers_extra: dict[str, str] | None = None


class LLMRouter:
    def __init__(self, settings: Settings, db_session: Session, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.db = db_session
        self._http = httpx.Client(transport=transport, timeout=30.0)

    def _providers(self) -> list[ProviderConfig]:
        s = self.settings
        candidates = [
            ProviderConfig("groq", "https://api.groq.com/openai/v1", s.groq_api_key,
                            ["openai/gpt-oss-120b", "qwen/qwen3.6-27b", "openai/gpt-oss-20b"]),
            ProviderConfig("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", s.gemini_api_key,
                            ["gemini-2.5-flash"]),
            ProviderConfig("openrouter", "https://openrouter.ai/api/v1", s.openrouter_api_key,
                            ["meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-chat-v3-0324:free"]),
            ProviderConfig("huggingface", "https://router.huggingface.co/v1", s.huggingface_api_key,
                            ["Qwen/Qwen3-Coder-30B-A3B-Instruct"]),
            ProviderConfig("cloudflare",
                            f"https://api.cloudflare.com/client/v4/accounts/{s.cloudflare_account_id}/ai/v1",
                            s.cloudflare_api_key, ["@cf/meta/llama-3.3-70b-instruct-fp8-fast"]),
            ProviderConfig("vercel-ai-gateway", "https://ai-gateway.vercel.sh/v1", s.vercel_ai_gateway_key,
                            ["openai/gpt-oss-20b"]),
        ]
        return [p for p in candidates if p.api_key]

    def chat_completion(self, messages: list[dict[str, str]]) -> str:
        last_error: Exception | None = None

        for provider in self._providers():
            if self._is_near_limit(provider.name):
                continue
            for model in provider.models:
                try:
                    result = self._call(provider, model, messages)
                    self._record_usage(provider.name)
                    return result
                except _RetryableError as exc:
                    last_error = exc
                    continue
                except Exception as exc:  # non-retryable provider error
                    last_error = exc
                    break

        raise LLMRouterError(f"All LLM providers failed: {last_error}")

    def _call(self, provider: ProviderConfig, model: str, messages: list[dict[str, str]]) -> str:
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        if provider.headers_extra:
            headers.update(provider.headers_extra)

        response = self._http.post(
            f"{provider.base_url}/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages, "temperature": 0.4},
        )

        if response.status_code == 429 or response.status_code >= 500:
            raise _RetryableError(f"{provider.name}/{model} returned {response.status_code}")

        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not content:
            raise _RetryableError(f"{provider.name}/{model} returned empty content")
        return content

    def _is_near_limit(self, provider_name: str, daily_ceiling: int = 500) -> bool:
        today = datetime.now(timezone.utc).date()
        usage = self.db.execute(
            select(LLMUsage).where(LLMUsage.provider == provider_name, LLMUsage.date == today)
        ).scalar_one_or_none()
        return bool(usage and usage.call_count >= daily_ceiling)

    def _record_usage(self, provider_name: str) -> None:
        today = datetime.now(timezone.utc).date()
        usage = self.db.execute(
            select(LLMUsage).where(LLMUsage.provider == provider_name, LLMUsage.date == today)
        ).scalar_one_or_none()
        if usage is None:
            usage = LLMUsage(provider=provider_name, date=today, call_count=0)
            self.db.add(usage)
        usage.call_count += 1
        self.db.commit()


class _RetryableError(Exception):
    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_llm_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm_router.py backend/tests/test_llm_router.py
git commit -m "feat(backend): add multi-provider LLM router with fallback"
```

---

### Task 8: Synthesizer and Validator stages

**Files:**
- Create: `backend/app/pipeline/synthesizer.py`
- Create: `backend/app/pipeline/validator.py`
- Test: `backend/tests/test_synthesizer_validator.py`

**Interfaces:**
- Consumes: `LLMRouter.chat_completion` (Task 7), `PipelineContext.ranked_findings` (Task 6).
- Produces: `Synthesizer(llm_router)` (fills `ctx.narrative: str`, `ctx.recommendations: list[dict]` each `{"category", "title", "body"}`), `Validator()` (sets `finding["validated"]: bool` per recommendation by checking any numbers in `body` appear in `ctx.normalized`/`ctx.ranked_findings` source data; drops unvalidated ones into `ctx.errors` instead of failing the stage).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_synthesizer_validator.py
import re
from unittest.mock import MagicMock

from app.models import Repo
from app.pipeline.base import PipelineContext
from app.pipeline.synthesizer import Synthesizer
from app.pipeline.validator import Validator


def _ctx_with_findings() -> PipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = PipelineContext(repo=repo)
    ctx.normalized = {"stars": 110, "stars_delta": 10}
    ctx.ranked_findings = [
        {"category": "missing_license", "message": "This repo has no LICENSE file.", "impact": 7, "effort": 1},
    ]
    return ctx


def test_synthesizer_produces_recommendations_from_llm():
    ctx = _ctx_with_findings()
    fake_llm = MagicMock()
    fake_llm.chat_completion.return_value = (
        '[{"title": "Add a LICENSE file", "body": "Your repo gained 10 stars but has no LICENSE file. Add one to encourage adoption.", "category": "missing_license"}]'
    )

    ctx = Synthesizer(llm_router=fake_llm).run(ctx)

    assert len(ctx.recommendations) == 1
    assert ctx.recommendations[0]["title"] == "Add a LICENSE file"
    assert "10 stars" in ctx.recommendations[0]["body"]


def test_validator_accepts_claims_backed_by_data():
    ctx = _ctx_with_findings()
    ctx.recommendations = [
        {"category": "missing_license", "title": "Add a LICENSE file", "body": "Your repo gained 10 stars but has no LICENSE file."}
    ]
    ctx = Validator().run(ctx)
    assert ctx.recommendations[0]["validated"] is True


def test_validator_rejects_fabricated_numbers():
    ctx = _ctx_with_findings()
    ctx.recommendations = [
        {"category": "missing_license", "title": "Add a LICENSE file", "body": "Your repo gained 9999 stars this week!"}
    ]
    ctx = Validator().run(ctx)
    assert ctx.recommendations[0]["validated"] is False
    assert len(ctx.errors) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_synthesizer_validator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.synthesizer'`

- [ ] **Step 3: Write `app/pipeline/synthesizer.py`**

```python
import json

from app.llm_router import LLMRouter
from app.pipeline.base import PipelineContext, Stage


class Synthesizer(Stage):
    name = "synthesizer"

    def __init__(self, llm_router: LLMRouter):
        self.llm_router = llm_router

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.ranked_findings:
            ctx.recommendations = []
            return ctx

        prompt = self._build_prompt(ctx)
        raw_response = self.llm_router.chat_completion([
            {"role": "system", "content": "You are a precise GitHub repo growth analyst. Respond with strict JSON only: a list of objects with keys title, body, category. Every number in body must come from the provided data — never invent numbers."},
            {"role": "user", "content": prompt},
        ])

        try:
            ctx.recommendations = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError):
            ctx.recommendations = []
            ctx.errors.append("synthesizer: LLM response was not valid JSON")

        return ctx

    def _build_prompt(self, ctx: PipelineContext) -> str:
        return (
            f"Repo: {ctx.repo.owner}/{ctx.repo.name}\n"
            f"Metrics: {ctx.normalized}\n"
            f"Findings to turn into recommendations: {ctx.ranked_findings}\n"
            "Write one recommendation per finding."
        )
```

- [ ] **Step 4: Write `app/pipeline/validator.py`**

```python
import re

from app.pipeline.base import PipelineContext, Stage


class Validator(Stage):
    name = "validator"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        known_numbers = self._known_numbers(ctx)

        for rec in ctx.recommendations:
            body_numbers = {int(n) for n in re.findall(r"\d+", rec.get("body", ""))}
            unverified = body_numbers - known_numbers
            rec["validated"] = len(unverified) == 0
            if not rec["validated"]:
                ctx.errors.append(
                    f"validator: recommendation '{rec.get('title')}' cites unverified numbers {unverified}"
                )

        return ctx

    def _known_numbers(self, ctx: PipelineContext) -> set[int]:
        numbers: set[int] = set()
        for value in ctx.normalized.values():
            if isinstance(value, int):
                numbers.add(value)
        for finding in ctx.ranked_findings:
            numbers.update(int(n) for n in re.findall(r"\d+", finding.get("message", "")))
        return numbers
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_synthesizer_validator.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/pipeline/synthesizer.py backend/app/pipeline/validator.py backend/tests/test_synthesizer_validator.py
git commit -m "feat(backend): add Synthesizer and Validator pipeline stages"
```

---

### Task 9: Assembler stage and PipelineRunner

**Files:**
- Create: `backend/app/pipeline/assembler.py`
- Create: `backend/app/pipeline/runner.py`
- Test: `backend/tests/test_runner.py`

**Interfaces:**
- Consumes: all prior stages (Tasks 5–8), `app.models.Snapshot`, `Recommendation`, `PipelineRun`, `StageRun` (Task 2).
- Produces: `Assembler(db_session)` (persists `Snapshot` + validated `Recommendation` rows, sets `ctx.raw["snapshot_id"]`), `PipelineRunner(stages: list[Stage], db_session)` with `run_for_repo(repo: Repo) -> PipelineContext`, which creates a `PipelineRun` row, runs each stage inside a `StageRun` row (status `ok`/`error`, duration_ms, error text), and never lets one stage's exception stop the rest.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_runner.py
from unittest.mock import MagicMock

from app.db import Base, SessionLocal, engine
from app.models import PipelineRun, Recommendation, Repo, Snapshot, StageRun
from app.pipeline.base import PipelineContext, Stage
from app.pipeline.runner import PipelineRunner


class _BoomStage(Stage):
    name = "boom"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        raise RuntimeError("simulated failure")


class _SetsNormalizedStage(Stage):
    name = "sets_normalized"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.normalized = {"stars": 5, "forks": 1, "watchers": 5, "open_issues": 0, "views_14d": 0, "unique_views_14d": 0, "clones_14d": 0, "unique_clones_14d": 0}
        ctx.recommendations = [{"category": "x", "title": "t", "body": "b", "validated": True}]
        return ctx


def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return db, repo


def test_runner_persists_run_and_stage_rows_even_on_stage_failure():
    db, repo = _db()
    from app.pipeline.assembler import Assembler
    runner = PipelineRunner(stages=[_BoomStage(), _SetsNormalizedStage(), Assembler(db_session=db)], db_session=db)

    ctx = runner.run_for_repo(repo)

    assert ctx.errors  # boom stage recorded an error, run continued
    run_row = db.query(PipelineRun).first()
    assert run_row.status == "degraded"
    stage_rows = db.query(StageRun).filter_by(pipeline_run_id=run_row.id).all()
    assert {s.stage_name for s in stage_rows} == {"boom", "sets_normalized", "assembler"}
    boom_row = next(s for s in stage_rows if s.stage_name == "boom")
    assert boom_row.status == "error"
    assert "simulated failure" in boom_row.error

    snapshot = db.query(Snapshot).filter_by(repo_id=repo.id).first()
    assert snapshot.stars == 5

    rec = db.query(Recommendation).filter_by(repo_id=repo.id).first()
    assert rec.title == "t"
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.runner'`

- [ ] **Step 3: Write `app/pipeline/assembler.py`**

```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Recommendation, Snapshot
from app.pipeline.base import PipelineContext, Stage


class Assembler(Stage):
    name = "assembler"

    def __init__(self, db_session: Session):
        self.db = db_session

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.normalized:
            return ctx

        snapshot = Snapshot(
            repo_id=ctx.repo.id,
            date=datetime.now(timezone.utc).date(),
            stars=ctx.normalized.get("stars", 0),
            forks=ctx.normalized.get("forks", 0),
            watchers=ctx.normalized.get("watchers", 0),
            open_issues=ctx.normalized.get("open_issues", 0),
            views_14d=ctx.normalized.get("views_14d", 0),
            unique_views_14d=ctx.normalized.get("unique_views_14d", 0),
            clones_14d=ctx.normalized.get("clones_14d", 0),
            unique_clones_14d=ctx.normalized.get("unique_clones_14d", 0),
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        ctx.raw["snapshot_id"] = snapshot.id

        for rec in ctx.recommendations:
            if not rec.get("validated", False):
                continue
            self.db.add(Recommendation(
                repo_id=ctx.repo.id,
                snapshot_id=snapshot.id,
                category=rec.get("category", "general"),
                title=rec.get("title", ""),
                body=rec.get("body", ""),
                validated=True,
            ))
        self.db.commit()
        return ctx
```

- [ ] **Step 4: Write `app/pipeline/runner.py`**

```python
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import PipelineRun, Repo, StageRun
from app.pipeline.base import PipelineContext, Stage


class PipelineRunner:
    def __init__(self, stages: list[Stage], db_session: Session):
        self.stages = stages
        self.db = db_session

    def run_for_repo(self, repo: Repo) -> PipelineContext:
        run_row = PipelineRun(status="running")
        self.db.add(run_row)
        self.db.commit()
        self.db.refresh(run_row)

        ctx = PipelineContext(repo=repo)
        had_error = False

        for stage in self.stages:
            start = time.monotonic()
            status = "ok"
            error_text: str | None = None
            try:
                ctx = stage.run(ctx)
            except Exception as exc:  # a stage failure must not stop the pipeline
                status = "error"
                error_text = str(exc)
                ctx.errors.append(f"{stage.name}: {exc}")
                had_error = True
            duration_ms = int((time.monotonic() - start) * 1000)

            self.db.add(StageRun(
                pipeline_run_id=run_row.id,
                stage_name=stage.name,
                status=status,
                duration_ms=duration_ms,
                error=error_text,
            ))
            self.db.commit()

        run_row.status = "degraded" if had_error else "ok"
        run_row.finished_at = datetime.now(timezone.utc)
        self.db.commit()

        return ctx
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_runner.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/pipeline/assembler.py backend/app/pipeline/runner.py backend/tests/test_runner.py
git commit -m "feat(backend): add Assembler stage and PipelineRunner with degraded-run handling"
```

---

### Task 10: Read endpoints (insights, benchmarks, recommendations, runs, providers)

**Files:**
- Create: `backend/app/api/insights.py`
- Create: `backend/app/api/recommendations.py`
- Create: `backend/app/api/runs.py`
- Create: `backend/app/api/providers.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_read_endpoints.py`

**Interfaces:**
- Consumes: `app.deps.require_api_key`, `app.db.get_db`, all models (Task 2), `PipelineRunner`, `GitHubClient`, `LLMRouter` (Tasks 4, 7, 9).
- Produces: `GET /repos/{id}/snapshots`, `GET /repos/{id}/insights`, `GET /repos/{id}/benchmarks`, `GET /recommendations`, `PATCH /recommendations/{id}`, `GET /runs`, `POST /runs`, `GET /providers/status`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_read_endpoints.py
from datetime import date

from app.db import SessionLocal
from app.models import PipelineRun, Recommendation, Repo, Snapshot


def _seed():
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()
    db.refresh(repo)

    db.add(Snapshot(repo_id=repo.id, date=date(2026, 7, 19), stars=100, forks=10, watchers=100, open_issues=2))
    snap = Snapshot(repo_id=repo.id, date=date(2026, 7, 20), stars=110, forks=12, watchers=110, open_issues=3)
    db.add(snap)
    db.commit()
    db.refresh(snap)

    db.add(Recommendation(repo_id=repo.id, snapshot_id=snap.id, category="missing_license", title="Add a LICENSE", body="No LICENSE file found.", validated=True))
    db.add(PipelineRun(status="ok"))
    db.commit()
    db.close()
    return repo.id


def test_snapshots_and_insights_and_recommendations_and_runs(client):
    repo_id = _seed()

    snapshots_resp = client.get(f"/repos/{repo_id}/snapshots")
    assert snapshots_resp.status_code == 200
    assert len(snapshots_resp.json()) == 2

    insights_resp = client.get(f"/repos/{repo_id}/insights")
    assert insights_resp.status_code == 200
    assert insights_resp.json()["latest_stars"] == 110

    recs_resp = client.get("/recommendations")
    assert recs_resp.status_code == 200
    rec_id = recs_resp.json()[0]["id"]

    dismiss_resp = client.patch(f"/recommendations/{rec_id}", json={"dismissed": True})
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["dismissed"] is True

    runs_resp = client.get("/runs")
    assert runs_resp.status_code == 200
    assert len(runs_resp.json()) == 1

    providers_resp = client.get("/providers/status")
    assert providers_resp.status_code == 200
    assert isinstance(providers_resp.json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_read_endpoints.py -v`
Expected: FAIL — 404 on `/repos/{id}/snapshots`.

- [ ] **Step 3: Write `app/api/insights.py`** (handles `/repos/{id}/snapshots`, `/repos/{id}/insights`, `/repos/{id}/benchmarks`)

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import BenchmarkRepo, Recommendation, Repo, Snapshot

router = APIRouter(prefix="/repos", tags=["insights"], dependencies=[Depends(require_api_key)])


class SnapshotOut(BaseModel):
    id: int
    date: object
    stars: int
    forks: int
    watchers: int
    open_issues: int
    views_14d: int
    unique_views_14d: int
    clones_14d: int
    unique_clones_14d: int

    model_config = {"from_attributes": True}


@router.get("/{repo_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(repo_id: int, db: Session = Depends(get_db)) -> list[Snapshot]:
    _require_repo(repo_id, db)
    return db.execute(select(Snapshot).where(Snapshot.repo_id == repo_id).order_by(Snapshot.date)).scalars().all()


@router.get("/{repo_id}/insights")
def get_insights(repo_id: int, db: Session = Depends(get_db)) -> dict:
    _require_repo(repo_id, db)
    latest = db.execute(
        select(Snapshot).where(Snapshot.repo_id == repo_id).order_by(Snapshot.date.desc())
    ).scalars().first()
    recommendations = db.execute(
        select(Recommendation).where(Recommendation.repo_id == repo_id, Recommendation.dismissed.is_(False))
    ).scalars().all()

    return {
        "latest_stars": latest.stars if latest else 0,
        "latest_forks": latest.forks if latest else 0,
        "recommendation_count": len(recommendations),
    }


@router.get("/{repo_id}/benchmarks")
def list_benchmarks(repo_id: int, db: Session = Depends(get_db)) -> list[dict]:
    _require_repo(repo_id, db)
    rows = db.execute(select(BenchmarkRepo).where(BenchmarkRepo.source_repo_id == repo_id)).scalars().all()
    return [{"full_name": r.full_name, "stars": r.stars, "forks": r.forks, "topics": r.topics} for r in rows]


def _require_repo(repo_id: int, db: Session) -> Repo:
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo
```

- [ ] **Step 4: Write `app/api/recommendations.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import Recommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"], dependencies=[Depends(require_api_key)])


class RecommendationOut(BaseModel):
    id: int
    repo_id: int
    category: str
    title: str
    body: str
    validated: bool
    dismissed: bool

    model_config = {"from_attributes": True}


class RecommendationPatch(BaseModel):
    dismissed: bool


@router.get("", response_model=list[RecommendationOut])
def list_recommendations(db: Session = Depends(get_db)) -> list[Recommendation]:
    return db.execute(select(Recommendation).order_by(Recommendation.created_at.desc())).scalars().all()


@router.patch("/{recommendation_id}", response_model=RecommendationOut)
def update_recommendation(recommendation_id: int, payload: RecommendationPatch, db: Session = Depends(get_db)) -> Recommendation:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.dismissed = payload.dismissed
    db.commit()
    db.refresh(rec)
    return rec
```

- [ ] **Step 5: Write `app/api/runs.py`**

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import PipelineRun

router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(require_api_key)])


class PipelineRunOut(BaseModel):
    id: int
    status: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[PipelineRunOut])
def list_runs(db: Session = Depends(get_db)) -> list[PipelineRun]:
    return db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc())).scalars().all()


@router.post("", response_model=list[PipelineRunOut], status_code=202)
def trigger_run(db: Session = Depends(get_db)) -> list[PipelineRun]:
    from app.pipeline.jobs import run_pipeline_for_all_repos
    run_pipeline_for_all_repos(db)
    return db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1)).scalars().all()
```

- [ ] **Step 6: Write `app/api/providers.py`**

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import LLMUsage

router = APIRouter(prefix="/providers", tags=["providers"], dependencies=[Depends(require_api_key)])


@router.get("/status")
def provider_status(db: Session = Depends(get_db)) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    rows = db.execute(select(LLMUsage).where(LLMUsage.date == today)).scalars().all()
    return [{"provider": r.provider, "calls_today": r.call_count} for r in rows]
```

- [ ] **Step 7: Write `app/pipeline/jobs.py`** (shared helper wiring stages + LLM router + GitHub client together — used by `POST /runs` above and by the scheduler in Task 11)

```python
from sqlalchemy.orm import Session

from app.config import get_settings
from app.github_client import GitHubClient
from app.llm_router import LLMRouter
from app.models import Repo
from app.pipeline.analyzer import Analyzer
from app.pipeline.assembler import Assembler
from app.pipeline.extractor import Extractor
from app.pipeline.optimizer import Optimizer
from app.pipeline.preprocessor import Preprocessor
from app.pipeline.runner import PipelineRunner
from app.pipeline.synthesizer import Synthesizer
from app.pipeline.validator import Validator


def build_stages(db: Session) -> list:
    settings = get_settings()
    gh_client = GitHubClient(token=settings.github_token)
    llm_router = LLMRouter(settings=settings, db_session=db)
    return [
        Extractor(gh_client=gh_client),
        Preprocessor(db_session=db),
        Analyzer(),
        Optimizer(),
        Synthesizer(llm_router=llm_router),
        Validator(),
        Assembler(db_session=db),
    ]


def run_pipeline_for_all_repos(db: Session) -> None:
    repos = db.query(Repo).all()
    for repo in repos:
        runner = PipelineRunner(stages=build_stages(db), db_session=db)
        runner.run_for_repo(repo)
```

- [ ] **Step 8: Mount routers in `app/main.py`**

```python
# app/main.py — add imports and include_router calls
from app.api.insights import router as insights_router
from app.api.recommendations import router as recommendations_router
from app.api.runs import router as runs_router
from app.api.providers import router as providers_router

app.include_router(insights_router)
app.include_router(recommendations_router)
app.include_router(runs_router)
app.include_router(providers_router)
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_read_endpoints.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add backend/app/api/insights.py backend/app/api/recommendations.py backend/app/api/runs.py backend/app/api/providers.py backend/app/pipeline/jobs.py backend/app/main.py backend/tests/test_read_endpoints.py
git commit -m "feat(backend): add insights, recommendations, runs, and provider-status endpoints"
```

---

### Task 11: SSE events endpoint and APScheduler daily trigger

**Files:**
- Create: `backend/app/events.py`
- Create: `backend/app/api/events.py`
- Modify: `backend/app/api/recommendations.py`
- Modify: `backend/app/api/repos.py`
- Modify: `backend/app/api/runs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_events.py`

**Interfaces:**
- Consumes: `app.deps.require_api_key`.
- Produces: `app.events.broadcaster` (module-level `EventBroadcaster` with `publish(event_type: str, payload: dict) -> None` and `subscribe() -> asyncio.Queue`), `GET /events` (SSE stream), APScheduler job registered on FastAPI startup calling `run_pipeline_for_all_repos` once every 24 hours.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_events.py
import asyncio

from app.events import EventBroadcaster


def test_publish_delivers_to_subscriber():
    async def scenario():
        broadcaster = EventBroadcaster()
        queue = broadcaster.subscribe()
        broadcaster.publish("recommendation_dismissed", {"id": 1})
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event["type"] == "recommendation_dismissed"
        assert event["payload"] == {"id": 1}

    asyncio.run(scenario())


def test_events_endpoint_requires_api_key(client_without_auth):
    resp = client_without_auth.get("/events")
    assert resp.status_code == 401
```

Add the missing fixture:

```python
# backend/tests/conftest.py — add
@pytest.fixture
def client_without_auth():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.events'`

- [ ] **Step 3: Write `app/events.py`**

```python
import asyncio
from typing import Any


class EventBroadcaster:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload}
        for queue in list(self._subscribers):
            queue.put_nowait(event)


broadcaster = EventBroadcaster()
```

- [ ] **Step 4: Write `app/api/events.py`**

```python
import asyncio
import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.deps import require_api_key
from app.events import broadcaster

router = APIRouter(tags=["events"], dependencies=[Depends(require_api_key)])


@router.get("/events")
async def stream_events():
    queue = broadcaster.subscribe()

    async def event_generator():
        try:
            while True:
                event = await queue.get()
                yield {"event": event["type"], "data": json.dumps(event["payload"])}
        finally:
            broadcaster.unsubscribe(queue)

    return EventSourceResponse(event_generator())
```

Add `sse-starlette==2.2.1` to `backend/requirements.txt`.

- [ ] **Step 5: Wire `publish()` calls into existing mutation endpoints**

In `app/api/recommendations.py`, inside `update_recommendation`, after `db.refresh(rec)`:

```python
from app.events import broadcaster
# ... inside update_recommendation, right before `return rec`:
broadcaster.publish("recommendation_updated", {"id": rec.id, "dismissed": rec.dismissed})
```

In `app/api/repos.py`, inside `create_repo` (before `return repo`) and `delete_repo` (before returning):

```python
from app.events import broadcaster
# create_repo, before return repo:
broadcaster.publish("repo_added", {"id": repo.id})
# delete_repo, before returning:
broadcaster.publish("repo_removed", {"id": repo_id})
```

In `app/api/runs.py`, inside `trigger_run`, after calling `run_pipeline_for_all_repos(db)`:

```python
from app.events import broadcaster
# after run_pipeline_for_all_repos(db):
broadcaster.publish("run_completed", {})
```

- [ ] **Step 6: Mount events router and register APScheduler in `app/main.py`**

```python
# app/main.py — add imports
from apscheduler.schedulers.background import BackgroundScheduler

from app.api.events import router as events_router
from app.db import SessionLocal
from app.pipeline.jobs import run_pipeline_for_all_repos

app.include_router(events_router)

scheduler = BackgroundScheduler()


def _scheduled_pipeline_run() -> None:
    db = SessionLocal()
    try:
        run_pipeline_for_all_repos(db)
    finally:
        db.close()


@app.on_event("startup")
def start_scheduler() -> None:
    scheduler.add_job(_scheduled_pipeline_run, "interval", hours=24, id="daily_pipeline_run")
    scheduler.start()


@app.on_event("shutdown")
def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_events.py -v`
Expected: PASS

- [ ] **Step 8: Run the full test suite**

Run: `cd backend && python -m pytest -v`
Expected: all tests PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/events.py backend/app/api/events.py backend/app/api/recommendations.py backend/app/api/repos.py backend/app/api/runs.py backend/app/main.py backend/requirements.txt backend/tests/test_events.py backend/tests/conftest.py
git commit -m "feat(backend): add SSE event stream and daily APScheduler trigger"
```

---

## Self-Review Notes

- **Spec coverage:** All 7 pipeline stages (Task 5, 6, 7 via LLM router, 8, 9), data model (Task 2), API surface with keyword-safe naming (Tasks 3, 10, 11), LLM fallback order and deprecated-model avoidance (Task 7, Global Constraints), degraded-run handling (Task 9), SSE + CRUD invalidation hooks (Task 11), Dockerfile per playbook (Task 1) are all covered. Alembic migration matches Task 2. Deferred: actual Coolify subdomain/DNS setup and Postgres provisioning are deployment-time steps, not code — left as the spec's "open items," not a coding task.
- **Placeholder scan:** No TODOs; every step has complete, runnable code.
- **Type consistency:** `PipelineContext` fields (`raw`, `normalized`, `findings`, `ranked_findings`, `narrative`, `recommendations`, `errors`) defined in Task 5 are used with the same names in Tasks 6, 8, 9. `Stage.name`/`Stage.run()` defined in Task 5 is implemented identically by every stage class. `LLMRouter.chat_completion(messages) -> str` defined in Task 7 matches its usage in Task 8's `Synthesizer`.
