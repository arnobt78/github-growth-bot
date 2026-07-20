# GitHub Growth Bot — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Next.js App Router dashboard for the GitHub Growth Bot (REQ-0010–REQ-0014): a fast, professional, real-time personal analytics dashboard consuming the already-built and Gate-2-approved FastAPI backend, covering every page and feature in the approved design spec (`docs/superpowers/specs/2026-07-20-github-growth-bot-design.md`).

**Architecture:** Next.js 15 App Router, SSR data-fetching directly in `page.tsx` via a server-only typed backend client, hydrated into TanStack Query on the client for instant mutation-driven updates. A thin Route Handler proxy layer (`app/api/*`) is the *only* thing the browser ever talks to for client-initiated calls (mutations, refetches, the SSE stream) — it holds the backend API key server-side so the browser never sees it. An SSE subscription invalidates TanStack Query keys on any backend-side CRUD event, so every open tab updates instantly with no polling and no page refresh.

**Tech Stack:** Next.js 15 (App Router, TypeScript strict), Tailwind CSS + shadcn/ui, TanStack Query v5, Recharts (charts/sparklines), `openapi-typescript` (type generation from the backend's `/openapi.json`), lucide-react (icons), Vitest + React Testing Library (component tests).

Two small, additive backend endpoint gaps were found while planning REQ-0010's data needs (referrers/popular-paths were persisted by the Assembler per CAPA-0002 but never exposed via any endpoint; pipeline-run timestamps and per-stage detail were never exposed either, though `StageRun` rows exist). Tasks 1–2 close those gaps before any frontend code depends on them — this is the same class of fix as CAPA-0002 (data computed/persisted but not exposed), caught now instead of after the frontend is built against an incomplete API.

## Global Constraints

- Endpoint paths never contain `analytics`, `analysis`, `tracking`, `performance`, or `metrics` — use `insights`/`snapshots`/`benchmarks`/`runs`/`referrers`/`popular-paths` instead.
- Every backend endpoint except `GET /api/health` requires `Authorization: Bearer <API_KEY>`.
- No secrets committed — `.env.example` / `.env.local.example` hold placeholders only.
- SSR data-fetching goes directly in `page.tsx` (Server Components); only genuinely interactive code lives in `"use client"` components.
- No `loading.tsx` files. Page shell (headers, labels, icons, buttons, card frames) renders instantly; only data-bearing regions show inline skeletons matching the real content's dimensions.
- Independent server prefetches run in parallel (`Promise.all`), never sequential `await`s.
- Every title/subtitle/label/button carries a `lucide-react` icon with semantic color tied to what it represents.
- Shared structure: `lib/`, `hooks/`, `providers/`, `types/` (generated from the backend's OpenAPI schema — never hand-duplicated), `components/ui/`.
- The browser never holds the backend's API key — Next.js Route Handlers proxy every backend call server-side.
- CRUD mutations use TanStack Query + SSE-driven cache invalidation so every open tab updates instantly without a page refresh.
- Strict TypeScript throughout; no dead code, no unused dependencies; `npm audit` clean and `npm run lint`/`npm run build` clean before considering this done.
- No auto-starring/forking/following or artificial engagement inflation anywhere (standing project non-goal, REQ-0000 — not applicable to any frontend code here, but no task in this plan may add write-capable GitHub calls).

---

## Task 1: Expose referrers, popular paths, and typed insights/benchmarks/repo schemas

**Files:**
- Modify: `backend/app/api/insights.py`
- Modify: `backend/app/api/repos.py`
- Test: `backend/tests/test_insights_extra_endpoints.py`

**Interfaces:**
- Consumes: `app.models.Referrer`, `app.models.PopularPath`, `app.models.BenchmarkRepo`, `app.models.Repo`, `app.models.Snapshot`, `app.models.Recommendation` (all pre-existing).
- Produces: `GET /repos/{id}/referrers` → `list[ReferrerOut]`, `GET /repos/{id}/popular-paths` → `list[PopularPathOut]`, `GET /repos/{id}/insights` → `InsightsOut` (now response_model-typed instead of a bare `dict`), `GET /repos/{id}/benchmarks` → `list[BenchmarkOut]` (now typed), `RepoOut.tracked_since: datetime` (new field). These schema names (`ReferrerOut`, `PopularPathOut`, `InsightsOut`, `BenchmarkOut`) are what Task 4's `openapi-typescript` run will generate as TypeScript types — later frontend tasks reference these exact names.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_insights_extra_endpoints.py`:

```python
from datetime import date

from app.db import SessionLocal
from app.models import BenchmarkRepo, PopularPath, Referrer, Repo


def _seed_repo_with_traffic_data():
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world")
    db.add(repo)
    db.commit()
    db.refresh(repo)
    repo_id = repo.id

    db.add(Referrer(repo_id=repo_id, date=date(2026, 7, 20), referrer="github.com", count=50, uniques=30))
    db.add(PopularPath(repo_id=repo_id, date=date(2026, 7, 20), path="/", count=100, uniques=60))
    db.add(BenchmarkRepo(source_repo_id=repo_id, full_name="torvalds/linux", stars=999, forks=100, topics=["kernel"]))
    db.commit()
    db.close()
    return repo_id


def test_repo_out_includes_tracked_since(client):
    resp = client.post("/repos", json={"owner": "octocat", "name": "hello-world"})
    assert resp.status_code == 201
    assert "tracked_since" in resp.json()


def test_referrers_endpoint_returns_seeded_rows(client):
    repo_id = _seed_repo_with_traffic_data()

    resp = client.get(f"/repos/{repo_id}/referrers")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["referrer"] == "github.com"
    assert body[0]["uniques"] == 30


def test_popular_paths_endpoint_returns_seeded_rows(client):
    repo_id = _seed_repo_with_traffic_data()

    resp = client.get(f"/repos/{repo_id}/popular-paths")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["path"] == "/"
    assert body[0]["count"] == 100


def test_benchmarks_endpoint_uses_typed_schema(client):
    repo_id = _seed_repo_with_traffic_data()

    resp = client.get(f"/repos/{repo_id}/benchmarks")
    assert resp.status_code == 200
    assert resp.json() == [{"full_name": "torvalds/linux", "stars": 999, "forks": 100, "topics": ["kernel"]}]


def test_insights_endpoint_uses_typed_schema(client):
    repo_id = _seed_repo_with_traffic_data()

    resp = client.get(f"/repos/{repo_id}/insights")
    assert resp.status_code == 200
    assert resp.json() == {"latest_stars": 0, "latest_forks": 0, "recommendation_count": 0}


def test_unknown_repo_returns_404_for_new_endpoints(client):
    assert client.get("/repos/999999/referrers").status_code == 404
    assert client.get("/repos/999999/popular-paths").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_insights_extra_endpoints.py -v`
Expected: FAIL — `404` for `/referrers`/`/popular-paths` (routes don't exist yet), `tracked_since` `KeyError`, benchmarks/insights assertions fail on shape.

- [ ] **Step 3: Implement — rewrite `backend/app/api/insights.py`**

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.models import BenchmarkRepo, PopularPath, Recommendation, Referrer, Repo, Snapshot

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
def list_snapshots(repo_id: int, db: Session = Depends(get_db)) -> list[Snapshot]:
    _require_repo(repo_id, db)
    return db.execute(select(Snapshot).where(Snapshot.repo_id == repo_id).order_by(Snapshot.date)).scalars().all()


@router.get("/{repo_id}/insights", response_model=InsightsOut)
def get_insights(repo_id: int, db: Session = Depends(get_db)) -> InsightsOut:
    _require_repo(repo_id, db)
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
def list_benchmarks(repo_id: int, db: Session = Depends(get_db)) -> list[BenchmarkOut]:
    _require_repo(repo_id, db)
    rows = db.execute(select(BenchmarkRepo).where(BenchmarkRepo.source_repo_id == repo_id)).scalars().all()
    return [BenchmarkOut(full_name=r.full_name, stars=r.stars, forks=r.forks, topics=r.topics) for r in rows]


@router.get("/{repo_id}/referrers", response_model=list[ReferrerOut])
def list_referrers(repo_id: int, db: Session = Depends(get_db)) -> list[Referrer]:
    _require_repo(repo_id, db)
    return db.execute(
        select(Referrer).where(Referrer.repo_id == repo_id).order_by(Referrer.date.desc())
    ).scalars().all()


@router.get("/{repo_id}/popular-paths", response_model=list[PopularPathOut])
def list_popular_paths(repo_id: int, db: Session = Depends(get_db)) -> list[PopularPath]:
    _require_repo(repo_id, db)
    return db.execute(
        select(PopularPath).where(PopularPath.repo_id == repo_id).order_by(PopularPath.date.desc())
    ).scalars().all()


def _require_repo(repo_id: int, db: Session) -> Repo:
    repo = db.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo
```

- [ ] **Step 4: Implement — add `tracked_since` to `backend/app/api/repos.py`**

Rewrite `backend/app/api/repos.py`:

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.events import broadcaster
from app.models import Repo

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
def list_repos(db: Session = Depends(get_db)) -> list[Repo]:
    return db.query(Repo).all()


@router.post("", response_model=RepoOut, status_code=201)
def create_repo(payload: RepoCreate, db: Session = Depends(get_db)) -> Repo:
    repo = Repo(owner=payload.owner, name=payload.name)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    broadcaster.publish("repo_added", {"id": repo.id})
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
    broadcaster.publish("repo_removed", {"id": repo_id})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_insights_extra_endpoints.py -v`
Expected: PASS (6/6)

- [ ] **Step 6: Run full backend suite to confirm no regressions**

Run: `cd backend && .venv/bin/python -m pytest -v`
Expected: PASS, all tests (should be 36/36 — 30 pre-existing + 6 new)

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/insights.py backend/app/api/repos.py backend/tests/test_insights_extra_endpoints.py
git commit -m "feat(backend): expose referrers/popular-paths and type insights/benchmarks/repo schemas"
```

---

## Task 2: Expose pipeline-run timestamps, per-stage detail, and recommendation timestamps

**Files:**
- Modify: `backend/app/api/runs.py`
- Modify: `backend/app/api/recommendations.py`
- Test: `backend/tests/test_runs_extra_endpoints.py`

**Interfaces:**
- Consumes: `app.models.PipelineRun`, `app.models.StageRun`, `app.models.Recommendation` (pre-existing).
- Produces: `PipelineRunOut.started_at`/`finished_at: datetime | None` (new fields), `GET /runs/{id}/stages` → `list[StageRunOut]` (new endpoint), `RecommendationOut.created_at: datetime` (new field). Later frontend tasks' `types/api.d.ts` will contain `StageRunOut` and the extended `PipelineRunOut`/`RecommendationOut` shapes from this task.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_runs_extra_endpoints.py`:

```python
from app.db import SessionLocal
from app.models import PipelineRun, Recommendation, StageRun


def _seed_run_with_stages():
    db = SessionLocal()
    run = PipelineRun(status="ok")
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id

    db.add(StageRun(pipeline_run_id=run_id, stage_name="extractor", status="ok", duration_ms=120))
    db.add(StageRun(pipeline_run_id=run_id, stage_name="synthesizer", status="error", duration_ms=45, error="LLM router exhausted"))
    db.commit()
    db.close()
    return run_id


def test_run_out_includes_timestamps(client):
    db = SessionLocal()
    db.add(PipelineRun(status="ok"))
    db.commit()
    db.close()

    resp = client.get("/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert "started_at" in body[0]
    assert "finished_at" in body[0]


def test_run_stages_endpoint_returns_seeded_rows_in_order(client):
    run_id = _seed_run_with_stages()

    resp = client.get(f"/runs/{run_id}/stages")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["stage_name"] == "extractor"
    assert body[0]["status"] == "ok"
    assert body[1]["stage_name"] == "synthesizer"
    assert body[1]["error"] == "LLM router exhausted"


def test_run_stages_returns_404_for_unknown_run(client):
    assert client.get("/runs/999999/stages").status_code == 404


def test_recommendation_out_includes_created_at(client):
    repo_resp = client.post("/repos", json={"owner": "octocat", "name": "hello-world"})
    repo_id = repo_resp.json()["id"]

    db = SessionLocal()
    db.add(Recommendation(
        repo_id=repo_id,
        category="missing_license",
        title="Add a LICENSE",
        body="No LICENSE file found.",
        validated=True,
    ))
    db.commit()
    db.close()

    resp = client.get("/recommendations")
    assert resp.status_code == 200
    assert "created_at" in resp.json()[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_runs_extra_endpoints.py -v`
Expected: FAIL — missing `started_at`/`finished_at`/`created_at` keys, `404` for `/runs/{id}/stages` (route doesn't exist).

- [ ] **Step 3: Implement — rewrite `backend/app/api/runs.py`**

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.events import broadcaster
from app.models import PipelineRun, StageRun

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


@router.get("", response_model=list[PipelineRunOut])
def list_runs(db: Session = Depends(get_db)) -> list[PipelineRun]:
    return db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc())).scalars().all()


@router.post("", response_model=list[PipelineRunOut], status_code=202)
def trigger_run(db: Session = Depends(get_db)) -> list[PipelineRun]:
    from app.pipeline.jobs import run_pipeline_for_all_repos
    run_pipeline_for_all_repos(db)
    broadcaster.publish("run_completed", {})
    return db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1)).scalars().all()


@router.get("/{run_id}/stages", response_model=list[StageRunOut])
def list_run_stages(run_id: int, db: Session = Depends(get_db)) -> list[StageRun]:
    run = db.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return db.execute(
        select(StageRun).where(StageRun.pipeline_run_id == run_id).order_by(StageRun.id)
    ).scalars().all()
```

- [ ] **Step 4: Implement — add `created_at` to `backend/app/api/recommendations.py`**

Rewrite `backend/app/api/recommendations.py`:

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_api_key
from app.events import broadcaster
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
    created_at: datetime

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
    broadcaster.publish("recommendation_updated", {"id": rec.id, "dismissed": rec.dismissed})
    return rec
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_runs_extra_endpoints.py -v`
Expected: PASS (4/4)

- [ ] **Step 6: Run full backend suite to confirm no regressions**

Run: `cd backend && .venv/bin/python -m pytest -v`
Expected: PASS, all tests (40/40 — 36 from Task 1 + 4 new)

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/runs.py backend/app/api/recommendations.py backend/tests/test_runs_extra_endpoints.py
git commit -m "feat(backend): expose pipeline run timestamps, per-stage detail, recommendation timestamps"
```

---

## Task 3: Scaffold the Next.js app

**Files:**
- Create: `frontend/` (via `create-next-app`)
- Create: `frontend/.env.local.example`
- Modify: `frontend/tsconfig.json` (strict mode confirmation)
- Create: `frontend/lib/utils.ts`

**Interfaces:**
- Produces: the `frontend/` project root every later task builds inside; the `cn()` utility (`lib/utils.ts`) that every `components/ui/*` file imports; the `@/*` import alias.

- [ ] **Step 1: Scaffold with create-next-app**

Run (from the repo root):

```bash
npx create-next-app@latest frontend \
  --typescript --tailwind --eslint --app \
  --src-dir=false --import-alias "@/*" --turbopack --yes
```

- [ ] **Step 2: Verify strict TypeScript is enabled**

Open `frontend/tsconfig.json` and confirm `"strict": true` is present under `compilerOptions` (this is `create-next-app`'s default — if it is ever missing, add it).

- [ ] **Step 3: Initialize shadcn/ui**

Run:

```bash
cd frontend && npx shadcn@latest init -d
```

This creates `components.json` and `lib/utils.ts` (the `cn()` helper combining `clsx` + `tailwind-merge`) automatically.

- [ ] **Step 4: Create the directory skeleton**

Run:

```bash
cd frontend && mkdir -p app/api hooks providers types tests
```

- [ ] **Step 5: Create the env example file**

Create `frontend/.env.local.example`:

```
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=change-me
```

- [ ] **Step 6: Verify the scaffold builds**

Run: `cd frontend && npm run build`
Expected: build succeeds (default Next.js starter page).

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "chore(frontend): scaffold Next.js app with Tailwind, shadcn/ui, strict TypeScript"
```

---

## Task 4: Generate types from the backend OpenAPI schema

**Files:**
- Modify: `frontend/package.json` (add `generate:types` script + `openapi-typescript` dev dependency)
- Create: `frontend/types/api.d.ts` (generated, committed)
- Create: `frontend/lib/api-types.ts`

**Interfaces:**
- Consumes: the backend's `/openapi.json`, which now (after Tasks 1–2) includes `RepoOut`, `SnapshotOut`, `InsightsOut`, `BenchmarkOut`, `ReferrerOut`, `PopularPathOut`, `RecommendationOut`, `PipelineRunOut`, `StageRunOut`.
- Produces: `Repo`, `Snapshot`, `Insights`, `Benchmark`, `Referrer`, `PopularPath`, `Recommendation`, `PipelineRun`, `StageRun` — the exact type names every later frontend task imports from `@/lib/api-types`.

- [ ] **Step 1: Install openapi-typescript**

Run: `cd frontend && npm install -D openapi-typescript`

- [ ] **Step 2: Add the generation script to `frontend/package.json`**

In the `"scripts"` block, add:

```json
"generate:types": "openapi-typescript http://localhost:8000/openapi.json -o types/api.d.ts"
```

- [ ] **Step 3: Start the backend locally**

Run (separate terminal, from `backend/`): `.venv/bin/uvicorn app.main:app --reload`

- [ ] **Step 4: Generate the types**

Run: `cd frontend && npm run generate:types`
Expected: `types/api.d.ts` is created/updated, containing a `components.schemas` object with `RepoOut`, `SnapshotOut`, `InsightsOut`, `BenchmarkOut`, `ReferrerOut`, `PopularPathOut`, `RecommendationOut`, `PipelineRunOut`, `StageRunOut`.

- [ ] **Step 5: Create the friendly type re-export layer**

Create `frontend/lib/api-types.ts`:

```ts
import type { components } from "@/types/api";

export type Repo = components["schemas"]["RepoOut"];
export type Snapshot = components["schemas"]["SnapshotOut"];
export type Insights = components["schemas"]["InsightsOut"];
export type Benchmark = components["schemas"]["BenchmarkOut"];
export type Referrer = components["schemas"]["ReferrerOut"];
export type PopularPath = components["schemas"]["PopularPathOut"];
export type Recommendation = components["schemas"]["RecommendationOut"];
export type PipelineRun = components["schemas"]["PipelineRunOut"];
export type StageRun = components["schemas"]["StageRunOut"];
export type RepoCreate = components["schemas"]["RepoCreate"];
```

- [ ] **Step 6: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/types/api.d.ts frontend/lib/api-types.ts
git commit -m "feat(frontend): generate typed API layer from backend OpenAPI schema"
```

**Note for future schema changes:** re-run `npm run generate:types` (with the backend running) any time a backend endpoint's request/response shape changes, and commit the regenerated `types/api.d.ts` alongside the change — never hand-edit it.

---

## Task 5: Server-only backend client

**Files:**
- Create: `frontend/lib/backend-client.ts`
- Create: `frontend/lib/api.ts`

**Interfaces:**
- Consumes: `Repo`, `Snapshot`, `Insights`, `Benchmark`, `Referrer`, `PopularPath`, `Recommendation`, `PipelineRun`, `StageRun`, `RepoCreate` (from Task 4's `@/lib/api-types`).
- Produces: `BackendError` class and the `api` object (`api.listRepos()`, `api.getRepo(id)`, `api.createRepo(payload)`, `api.deleteRepo(id)`, `api.listSnapshots(id)`, `api.getInsights(id)`, `api.listBenchmarks(id)`, `api.listReferrers(id)`, `api.listPopularPaths(id)`, `api.listRecommendations()`, `api.dismissRecommendation(id, dismissed)`, `api.listRuns()`, `api.triggerRun()`, `api.listRunStages(id)`, `api.providerStatus()`) — consumed directly by `page.tsx` Server Components (Tasks 13–17) and by every Route Handler (Task 6).

- [ ] **Step 1: Install the `server-only` guard package**

Run: `cd frontend && npm install server-only`

- [ ] **Step 2: Create `frontend/lib/backend-client.ts`**

```ts
import "server-only";

const BASE_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const API_KEY = process.env.BACKEND_API_KEY ?? "";

export class BackendError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function backendFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new BackendError(res.status, text || res.statusText);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}
```

- [ ] **Step 3: Create `frontend/lib/api.ts`**

```ts
import { backendFetch } from "@/lib/backend-client";
import type {
  Benchmark,
  Insights,
  PipelineRun,
  PopularPath,
  Recommendation,
  Referrer,
  Repo,
  RepoCreate,
  Snapshot,
  StageRun,
} from "@/lib/api-types";

type ProviderStatus = { provider: string; calls_today: number };

export const api = {
  listRepos: () => backendFetch<Repo[]>("/repos"),
  getRepo: (id: number) => backendFetch<Repo>(`/repos/${id}`),
  createRepo: (payload: RepoCreate) =>
    backendFetch<Repo>("/repos", { method: "POST", body: JSON.stringify(payload) }),
  deleteRepo: (id: number) => backendFetch<void>(`/repos/${id}`, { method: "DELETE" }),

  listSnapshots: (id: number) => backendFetch<Snapshot[]>(`/repos/${id}/snapshots`),
  getInsights: (id: number) => backendFetch<Insights>(`/repos/${id}/insights`),
  listBenchmarks: (id: number) => backendFetch<Benchmark[]>(`/repos/${id}/benchmarks`),
  listReferrers: (id: number) => backendFetch<Referrer[]>(`/repos/${id}/referrers`),
  listPopularPaths: (id: number) => backendFetch<PopularPath[]>(`/repos/${id}/popular-paths`),

  listRecommendations: () => backendFetch<Recommendation[]>("/recommendations"),
  dismissRecommendation: (id: number, dismissed: boolean) =>
    backendFetch<Recommendation>(`/recommendations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ dismissed }),
    }),

  listRuns: () => backendFetch<PipelineRun[]>("/runs"),
  triggerRun: () => backendFetch<PipelineRun[]>("/runs", { method: "POST" }),
  listRunStages: (id: number) => backendFetch<StageRun[]>(`/runs/${id}/stages`),

  providerStatus: () => backendFetch<ProviderStatus[]>("/providers/status"),
};
```

- [ ] **Step 4: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/backend-client.ts frontend/lib/api.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add server-only typed backend client"
```

---

## Task 6: Route Handler proxy layer

**Files:**
- Create: `frontend/lib/route-handler.ts`
- Create: `frontend/app/api/repos/route.ts`
- Create: `frontend/app/api/repos/[id]/route.ts`
- Create: `frontend/app/api/repos/[id]/snapshots/route.ts`
- Create: `frontend/app/api/repos/[id]/insights/route.ts`
- Create: `frontend/app/api/repos/[id]/benchmarks/route.ts`
- Create: `frontend/app/api/repos/[id]/referrers/route.ts`
- Create: `frontend/app/api/repos/[id]/popular-paths/route.ts`
- Create: `frontend/app/api/recommendations/route.ts`
- Create: `frontend/app/api/recommendations/[id]/route.ts`
- Create: `frontend/app/api/runs/route.ts`
- Create: `frontend/app/api/runs/[id]/stages/route.ts`
- Create: `frontend/app/api/providers/status/route.ts`
- Create: `frontend/app/api/events/route.ts`

**Interfaces:**
- Consumes: `api` (Task 5's `@/lib/api`), `BackendError` (Task 5's `@/lib/backend-client`).
- Produces: the full `/api/*` surface that Task 9's `hooks/*` and Task 8's SSE hook call from the browser — every path here has an exact 1:1 relative-URL counterpart the client code will fetch.

- [ ] **Step 1: Create the shared proxy helper — `frontend/lib/route-handler.ts`**

```ts
import { NextResponse } from "next/server";
import { BackendError } from "@/lib/backend-client";

export async function proxyRoute<T>(fn: () => Promise<T>, successStatus = 200) {
  try {
    const data = await fn();
    if (data === undefined) {
      return new NextResponse(null, { status: 204 });
    }
    return NextResponse.json(data, { status: successStatus });
  } catch (error) {
    if (error instanceof BackendError) {
      return NextResponse.json({ error: error.message }, { status: error.status });
    }
    throw error;
  }
}
```

- [ ] **Step 2: `frontend/app/api/repos/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";
import type { RepoCreate } from "@/lib/api-types";

export async function GET() {
  return proxyRoute(() => api.listRepos());
}

export async function POST(request: Request) {
  const payload = (await request.json()) as RepoCreate;
  return proxyRoute(() => api.createRepo(payload), 201);
}
```

- [ ] **Step 3: `frontend/app/api/repos/[id]/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyRoute(() => api.getRepo(Number(id)));
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyRoute(() => api.deleteRepo(Number(id)));
}
```

- [ ] **Step 4: `frontend/app/api/repos/[id]/snapshots/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyRoute(() => api.listSnapshots(Number(id)));
}
```

- [ ] **Step 5: `frontend/app/api/repos/[id]/insights/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyRoute(() => api.getInsights(Number(id)));
}
```

- [ ] **Step 6: `frontend/app/api/repos/[id]/benchmarks/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyRoute(() => api.listBenchmarks(Number(id)));
}
```

- [ ] **Step 7: `frontend/app/api/repos/[id]/referrers/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyRoute(() => api.listReferrers(Number(id)));
}
```

- [ ] **Step 8: `frontend/app/api/repos/[id]/popular-paths/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyRoute(() => api.listPopularPaths(Number(id)));
}
```

- [ ] **Step 9: `frontend/app/api/recommendations/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET() {
  return proxyRoute(() => api.listRecommendations());
}
```

- [ ] **Step 10: `frontend/app/api/recommendations/[id]/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const payload = (await request.json()) as { dismissed: boolean };
  return proxyRoute(() => api.dismissRecommendation(Number(id), payload.dismissed));
}
```

- [ ] **Step 11: `frontend/app/api/runs/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET() {
  return proxyRoute(() => api.listRuns());
}

export async function POST() {
  return proxyRoute(() => api.triggerRun(), 202);
}
```

- [ ] **Step 12: `frontend/app/api/runs/[id]/stages/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyRoute(() => api.listRunStages(Number(id)));
}
```

- [ ] **Step 13: `frontend/app/api/providers/status/route.ts`**

```ts
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function GET() {
  return proxyRoute(() => api.providerStatus());
}
```

- [ ] **Step 14: `frontend/app/api/events/route.ts` (SSE passthrough)**

```ts
export const dynamic = "force-dynamic";

export async function GET() {
  const baseUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  const apiKey = process.env.BACKEND_API_KEY ?? "";

  const backendResponse = await fetch(`${baseUrl}/events`, {
    headers: { Authorization: `Bearer ${apiKey}` },
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

- [ ] **Step 15: Verify the whole proxy layer builds and responds**

Run: `cd frontend && npm run build`
Expected: build succeeds, all 13 routes listed in the build output.

With the backend running (`uvicorn app.main:app --reload` in `backend/`) and the frontend dev server running (`npm run dev` in `frontend/`), verify: `curl -s http://localhost:3000/api/repos` returns `[]` (empty array, no auth header needed from the browser side — the Route Handler injects it).

- [ ] **Step 16: Commit**

```bash
git add frontend/lib/route-handler.ts frontend/app/api
git commit -m "feat(frontend): add Route Handler proxy layer for every backend endpoint"
```

---

## Task 7: TanStack Query provider and query keys

**Files:**
- Create: `frontend/lib/query-keys.ts`
- Create: `frontend/providers/query-provider.tsx`

**Interfaces:**
- Produces: `queryKeys` object (`queryKeys.repos.all`, `.detail(id)`, `.snapshots(id)`, `.insights(id)`, `.benchmarks(id)`, `.referrers(id)`, `.popularPaths(id)`; `queryKeys.recommendations.all`; `queryKeys.runs.all`, `.stages(id)`; `queryKeys.providers.status`) and `<QueryProvider>` — consumed by every hook (Task 9), the SSE hook (Task 8), and the root layout (Task 12).

- [ ] **Step 1: Install TanStack Query**

Run: `cd frontend && npm install @tanstack/react-query`

- [ ] **Step 2: Create `frontend/lib/query-keys.ts`**

```ts
export const queryKeys = {
  repos: {
    all: ["repos"] as const,
    detail: (id: number) => ["repos", id] as const,
    snapshots: (id: number) => ["repos", id, "snapshots"] as const,
    insights: (id: number) => ["repos", id, "insights"] as const,
    benchmarks: (id: number) => ["repos", id, "benchmarks"] as const,
    referrers: (id: number) => ["repos", id, "referrers"] as const,
    popularPaths: (id: number) => ["repos", id, "popular-paths"] as const,
  },
  recommendations: {
    all: ["recommendations"] as const,
  },
  runs: {
    all: ["runs"] as const,
    stages: (id: number) => ["runs", id, "stages"] as const,
  },
  providers: {
    status: ["providers", "status"] as const,
  },
};
```

- [ ] **Step 3: Create `frontend/providers/query-provider.tsx`**

```tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

export function QueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
```

- [ ] **Step 4: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/query-keys.ts frontend/providers/query-provider.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add TanStack Query provider and shared query keys"
```

---

## Task 8: SSE live-events provider and hook

**Files:**
- Create: `frontend/hooks/use-live-events.ts`
- Create: `frontend/providers/live-events-provider.tsx`

**Interfaces:**
- Consumes: `queryKeys` (Task 7).
- Produces: `useLiveEvents()` hook and `<LiveEventsProvider>` — mounted once in the root layout (Task 12); this is what makes every open tab react instantly to a backend-side `repo_added`/`repo_removed`/`recommendation_updated`/`run_completed` event (REQ-0008/REQ-0011).

- [ ] **Step 1: Create `frontend/hooks/use-live-events.ts`**

```ts
"use client";

import { useEffect } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";

const EVENT_QUERY_MAP: Record<string, QueryKey[]> = {
  repo_added: [queryKeys.repos.all],
  repo_removed: [queryKeys.repos.all],
  recommendation_updated: [queryKeys.recommendations.all],
  run_completed: [queryKeys.runs.all, queryKeys.repos.all],
};

export function useLiveEvents() {
  const queryClient = useQueryClient();

  useEffect(() => {
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
  }, [queryClient]);
}
```

- [ ] **Step 2: Create `frontend/providers/live-events-provider.tsx`**

```tsx
"use client";

import type { ReactNode } from "react";
import { useLiveEvents } from "@/hooks/use-live-events";

export function LiveEventsProvider({ children }: { children: ReactNode }) {
  useLiveEvents();
  return <>{children}</>;
}
```

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/hooks/use-live-events.ts frontend/providers/live-events-provider.tsx
git commit -m "feat(frontend): add SSE-driven live-events provider for cross-tab cache invalidation"
```

---

## Task 9: Shared UI primitives (icon/color conventions + shadcn base components)

**Files:**
- Create: `frontend/components/ui/section-heading.tsx`
- Create: `frontend/components/ui/stat-badge.tsx`
- Create: `frontend/components/ui/delta-badge.tsx`
- Create: `frontend/components/ui/empty-state.tsx`
- Modify: `frontend/components/ui/` (shadcn base components added via CLI)

**Interfaces:**
- Consumes: `cn` (Task 3's `@/lib/utils`).
- Produces: `<SectionHeading icon title subtitle? />`, `<StatBadge icon label value color />`, `<DeltaBadge value />`, `<EmptyState icon title description action? />` — used by every page (Tasks 13–17) to satisfy the "every title/label/button carries a meaningful icon with semantic color" convention in one place instead of repeating markup per page.

- [ ] **Step 1: Install shadcn/ui base components**

Run: `cd frontend && npx shadcn@latest add button card skeleton dialog table input label sonner`

(Only components actually consumed by a later task are installed here — this plan uses custom `StatBadge`/`DeltaBadge` wrappers instead of shadcn's base `Badge`, and Phase 1 has no tabbed view, so `badge` and `tabs` are deliberately omitted to avoid unused dependencies.)

- [ ] **Step 2: Install lucide-react**

Run: `cd frontend && npm install lucide-react`

- [ ] **Step 3: Create `frontend/components/ui/section-heading.tsx`**

```tsx
import type { LucideIcon } from "lucide-react";

export function SectionHeading({
  icon: Icon,
  title,
  subtitle,
  iconColor = "text-sky-500",
}: {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  iconColor?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className={`h-5 w-5 ${iconColor}`} aria-hidden="true" />
      <div>
        <h2 className="text-lg font-semibold leading-tight">{title}</h2>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/components/ui/stat-badge.tsx`**

```tsx
import type { LucideIcon } from "lucide-react";

export function StatBadge({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <span className="flex items-center gap-1 text-sm" aria-label={label}>
      <Icon className={`h-4 w-4 ${color}`} aria-hidden="true" />
      {value}
    </span>
  );
}
```

- [ ] **Step 5: Create `frontend/components/ui/delta-badge.tsx`**

```tsx
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

export function DeltaBadge({ value, label }: { value: number; label: string }) {
  if (value === 0) {
    return (
      <span className="flex items-center gap-1 text-sm text-muted-foreground" aria-label={`${label}: no change`}>
        <Minus className="h-4 w-4" aria-hidden="true" />0
      </span>
    );
  }

  const trending = value > 0;

  return (
    <span
      className={`flex items-center gap-1 text-sm ${trending ? "text-emerald-500" : "text-red-500"}`}
      aria-label={`${label}: ${trending ? "up" : "down"} ${Math.abs(value)}`}
    >
      {trending ? <ArrowUpRight className="h-4 w-4" aria-hidden="true" /> : <ArrowDownRight className="h-4 w-4" aria-hidden="true" />}
      {trending ? "+" : ""}
      {value}
    </span>
  );
}
```

- [ ] **Step 6: Create `frontend/components/ui/empty-state.tsx`**

```tsx
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed py-16 text-center">
      <Icon className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
      <div>
        <p className="font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  );
}
```

- [ ] **Step 7: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/components/ui frontend/package.json frontend/package-lock.json frontend/components.json
git commit -m "feat(frontend): add shared icon/color UI primitives and shadcn base components"
```

---

## Task 10: SafeImage component

**Files:**
- Create: `frontend/components/safe-image.tsx`
- Modify: `frontend/next.config.ts` (add GitHub avatar remote pattern)

**Interfaces:**
- Produces: `<SafeImage src alt width height className? fill? priority? />` — used by Task 13's `RepoCard` and Task 14's repo-detail header for GitHub owner avatars, per `docs/SAFE_IMAGE_REUSABLE_COMPONENT.md`.

- [ ] **Step 1: Add the GitHub avatar remote pattern to `frontend/next.config.ts`**

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [{ protocol: "https", hostname: "avatars.githubusercontent.com", pathname: "/**" }],
  },
};

export default nextConfig;
```

- [ ] **Step 2: Create `frontend/components/safe-image.tsx`**

(Ported verbatim from `docs/SAFE_IMAGE_REUSABLE_COMPONENT.md`, with the import path adjusted to this project's `@/lib/utils`.)

```tsx
"use client";

import { cn } from "@/lib/utils";
import Image, { type ImageProps } from "next/image";
import { useCallback, useState, type SyntheticEvent } from "react";

type SafeImageProps = ImageProps;

export function SafeImage({
  alt,
  src,
  className,
  fill,
  width,
  height,
  onError,
  priority,
  loading,
  ...rest
}: SafeImageProps) {
  const [useNative, setUseNative] = useState(false);
  const resolvedSrc = typeof src === "string" ? src : "";

  const handleError = useCallback(
    (e: SyntheticEvent<HTMLImageElement, Event>) => {
      onError?.(e);
      if (resolvedSrc) setUseNative(true);
    },
    [onError, resolvedSrc],
  );

  const eager = Boolean(priority || loading === "eager");

  if (useNative && resolvedSrc) {
    if (fill) {
      return (
        // eslint-disable-next-line @next/next/no-img-element -- fallback when /_next/image fails (e.g. 402)
        <img
          alt={alt}
          src={resolvedSrc}
          className={cn("absolute inset-0 h-full w-full", className)}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          sizes={typeof rest.sizes === "string" ? rest.sizes : undefined}
        />
      );
    }
    return (
      // eslint-disable-next-line @next/next/no-img-element -- fallback when /_next/image fails (e.g. 402)
      <img
        alt={alt}
        src={resolvedSrc}
        width={typeof width === "number" ? width : undefined}
        height={typeof height === "number" ? height : undefined}
        className={cn(className)}
        loading={eager ? "eager" : "lazy"}
        decoding="async"
      />
    );
  }

  return (
    <Image
      {...rest}
      alt={alt}
      src={src}
      className={className}
      fill={fill}
      width={width}
      height={height}
      priority={priority}
      loading={loading}
      onError={handleError}
    />
  );
}
```

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/safe-image.tsx frontend/next.config.ts
git commit -m "feat(frontend): add SafeImage component for GitHub avatars"
```

---

## Task 11: Typed TanStack Query data hooks

**Files:**
- Create: `frontend/lib/fetch-json.ts`
- Create: `frontend/hooks/use-repos.ts`
- Create: `frontend/hooks/use-repo-snapshots.ts`
- Create: `frontend/hooks/use-repo-insights.ts`
- Create: `frontend/hooks/use-repo-benchmarks.ts`
- Create: `frontend/hooks/use-repo-referrers.ts`
- Create: `frontend/hooks/use-repo-popular-paths.ts`
- Create: `frontend/hooks/use-recommendations.ts`
- Create: `frontend/hooks/use-runs.ts`
- Create: `frontend/hooks/use-run-stages.ts`
- Create: `frontend/hooks/use-provider-status.ts`

**Interfaces:**
- Consumes: `queryKeys` (Task 7), the `Repo`/`Snapshot`/`Insights`/`Benchmark`/`Referrer`/`PopularPath`/`Recommendation`/`PipelineRun`/`StageRun` types (Task 4's `@/lib/api-types`), the `/api/*` routes (Task 6).
- Produces: `useRepos()`, `useAddRepo()`, `useDeleteRepo()`, `useRepoSnapshots(id)`, `useRepoInsights(id)`, `useRepoBenchmarks(id)`, `useRepoReferrers(id)`, `useRepoPopularPaths(id)`, `useRecommendations()`, `useDismissRecommendation()`, `useRuns()`, `useTriggerRun()`, `useRunStages(id)`, `useProviderStatus()` — every page component (Tasks 13–17) consumes these by name.

- [ ] **Step 1: Create `frontend/lib/fetch-json.ts`**

```ts
export class ClientFetchError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new ClientFetchError(res.status, body.error ?? res.statusText);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}
```

- [ ] **Step 2: Create `frontend/hooks/use-repos.ts`**

```ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Repo, RepoCreate } from "@/lib/api-types";

export function useRepos() {
  return useQuery({
    queryKey: queryKeys.repos.all,
    queryFn: () => fetchJson<Repo[]>("/api/repos"),
  });
}

export function useAddRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RepoCreate) =>
      fetchJson<Repo>("/api/repos", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (repo) => {
      queryClient.setQueryData<Repo[]>(queryKeys.repos.all, (current) => [...(current ?? []), repo]);
    },
  });
}

export function useDeleteRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => fetchJson<void>(`/api/repos/${id}`, { method: "DELETE" }),
    onSuccess: (_data, id) => {
      queryClient.setQueryData<Repo[]>(queryKeys.repos.all, (current) => current?.filter((r) => r.id !== id) ?? []);
    },
  });
}
```

- [ ] **Step 3: Create `frontend/hooks/use-repo-snapshots.ts`**

```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Snapshot } from "@/lib/api-types";

export function useRepoSnapshots(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.snapshots(repoId),
    queryFn: () => fetchJson<Snapshot[]>(`/api/repos/${repoId}/snapshots`),
  });
}
```

- [ ] **Step 4: Create `frontend/hooks/use-repo-insights.ts`**

```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Insights } from "@/lib/api-types";

export function useRepoInsights(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.insights(repoId),
    queryFn: () => fetchJson<Insights>(`/api/repos/${repoId}/insights`),
  });
}
```

- [ ] **Step 5: Create `frontend/hooks/use-repo-benchmarks.ts`**

```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Benchmark } from "@/lib/api-types";

export function useRepoBenchmarks(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.benchmarks(repoId),
    queryFn: () => fetchJson<Benchmark[]>(`/api/repos/${repoId}/benchmarks`),
  });
}
```

- [ ] **Step 6: Create `frontend/hooks/use-repo-referrers.ts`**

```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Referrer } from "@/lib/api-types";

export function useRepoReferrers(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.referrers(repoId),
    queryFn: () => fetchJson<Referrer[]>(`/api/repos/${repoId}/referrers`),
  });
}
```

- [ ] **Step 7: Create `frontend/hooks/use-repo-popular-paths.ts`**

```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { PopularPath } from "@/lib/api-types";

export function useRepoPopularPaths(repoId: number) {
  return useQuery({
    queryKey: queryKeys.repos.popularPaths(repoId),
    queryFn: () => fetchJson<PopularPath[]>(`/api/repos/${repoId}/popular-paths`),
  });
}
```

- [ ] **Step 8: Create `frontend/hooks/use-recommendations.ts`**

```ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { Recommendation } from "@/lib/api-types";

export function useRecommendations() {
  return useQuery({
    queryKey: queryKeys.recommendations.all,
    queryFn: () => fetchJson<Recommendation[]>("/api/recommendations"),
  });
}

export function useDismissRecommendation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, dismissed }: { id: number; dismissed: boolean }) =>
      fetchJson<Recommendation>(`/api/recommendations/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ dismissed }),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData<Recommendation[]>(queryKeys.recommendations.all, (current) =>
        current?.map((r) => (r.id === updated.id ? updated : r)) ?? [],
      );
    },
  });
}
```

- [ ] **Step 9: Create `frontend/hooks/use-runs.ts`**

```ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { PipelineRun } from "@/lib/api-types";

export function useRuns() {
  return useQuery({
    queryKey: queryKeys.runs.all,
    queryFn: () => fetchJson<PipelineRun[]>("/api/runs"),
  });
}

export function useTriggerRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => fetchJson<PipelineRun[]>("/api/runs", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
    },
  });
}
```

- [ ] **Step 10: Create `frontend/hooks/use-run-stages.ts`**

```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";
import type { StageRun } from "@/lib/api-types";

export function useRunStages(runId: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.runs.stages(runId),
    queryFn: () => fetchJson<StageRun[]>(`/api/runs/${runId}/stages`),
    enabled,
  });
}
```

- [ ] **Step 11: Create `frontend/hooks/use-provider-status.ts`**

```ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/fetch-json";
import { queryKeys } from "@/lib/query-keys";

type ProviderStatus = { provider: string; calls_today: number };

export function useProviderStatus() {
  return useQuery({
    queryKey: queryKeys.providers.status,
    queryFn: () => fetchJson<ProviderStatus[]>("/api/providers/status"),
  });
}
```

- [ ] **Step 12: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 13: Commit**

```bash
git add frontend/lib/fetch-json.ts frontend/hooks
git commit -m "feat(frontend): add typed TanStack Query hooks for every backend resource"
```

---

## Task 12: Root layout, navigation shell, theme toggle

**Files:**
- Modify: `frontend/app/layout.tsx`
- Create: `frontend/providers/theme-provider.tsx`
- Create: `frontend/components/theme-toggle.tsx`
- Create: `frontend/components/nav-sidebar.tsx`

**Interfaces:**
- Consumes: `QueryProvider` (Task 7), `LiveEventsProvider` (Task 8).
- Produces: the app shell every page (Tasks 13–17) renders inside — this is what makes the shell (nav, header, icons) render instantly with no `loading.tsx` while individual pages handle their own data skeletons.

- [ ] **Step 1: Install `next-themes`**

Run: `cd frontend && npm install next-themes`

- [ ] **Step 2: Create `frontend/providers/theme-provider.tsx`**

```tsx
"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ReactNode } from "react";

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem>
      {children}
    </NextThemesProvider>
  );
}
```

- [ ] **Step 3: Create `frontend/components/theme-toggle.tsx`**

```tsx
"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle dark mode"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      <Sun className="h-4 w-4 text-amber-500 dark:hidden" aria-hidden="true" />
      <Moon className="hidden h-4 w-4 text-indigo-400 dark:block" aria-hidden="true" />
    </Button>
  );
}
```

- [ ] **Step 4: Create `frontend/components/nav-sidebar.tsx`**

```tsx
"use client";

import { Bell, History, LayoutDashboard, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard, color: "text-sky-500" },
  { href: "/recommendations", label: "Recommendations", icon: Bell, color: "text-amber-500" },
  { href: "/runs", label: "Pipeline Runs", icon: History, color: "text-violet-500" },
  { href: "/settings", label: "Settings", icon: Settings, color: "text-slate-500" },
];

export function NavSidebar() {
  const pathname = usePathname();

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
    </nav>
  );
}
```

- [ ] **Step 5: Rewrite `frontend/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
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
      </body>
    </html>
  );
}
```

- [ ] **Step 6: Verify the shell renders**

Run: `cd frontend && npm run dev`, open `http://localhost:3000`.
Expected: sidebar with 4 icon-labeled links, header with title + theme toggle, no console errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/layout.tsx frontend/providers/theme-provider.tsx frontend/components/theme-toggle.tsx frontend/components/nav-sidebar.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add root layout, nav sidebar, and theme toggle"
```

---

## Task 13: Overview page

**Files:**
- Modify: `frontend/app/page.tsx`
- Create: `frontend/components/overview/overview-client.tsx`
- Create: `frontend/components/overview/repo-card.tsx`
- Create: `frontend/components/overview/add-repo-dialog.tsx`

**Interfaces:**
- Consumes: `api` (Task 5), `queryKeys` (Task 7), `useRepos`/`useAddRepo`/`useDeleteRepo` (Task 11), `useRepoSnapshots`/`useRepoInsights` (Task 11), `SectionHeading`/`DeltaBadge`/`StatBadge`/`EmptyState` (Task 9), `SafeImage` (Task 10).
- Produces: `/` route — tracked-repos card grid with sparklines, delta badges, and open-recommendation counts; add/remove repo flow.

- [ ] **Step 1: Install Recharts**

Run: `cd frontend && npm install recharts`

- [ ] **Step 2: Create `frontend/components/overview/repo-card.tsx`**

```tsx
"use client";

import { ExternalLink, Eye, GitFork, Lightbulb, Star, Trash2 } from "lucide-react";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DeltaBadge } from "@/components/ui/delta-badge";
import { StatBadge } from "@/components/ui/stat-badge";
import { SafeImage } from "@/components/safe-image";
import { useRepoSnapshots } from "@/hooks/use-repo-snapshots";
import { useRepoInsights } from "@/hooks/use-repo-insights";
import { useDeleteRepo } from "@/hooks/use-repos";
import type { Repo } from "@/lib/api-types";

export function RepoCard({ repo }: { repo: Repo }) {
  const { data: snapshots, isPending } = useRepoSnapshots(repo.id);
  const { data: insights } = useRepoInsights(repo.id);
  const deleteRepo = useDeleteRepo();

  const latest = snapshots?.at(-1);
  const previous = snapshots?.at(-2);
  const starDelta = latest && previous ? latest.stars - previous.stars : 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <Link href={`/repos/${repo.id}`} className="flex items-center gap-2 font-medium hover:underline">
          <SafeImage
            src={`https://avatars.githubusercontent.com/${repo.owner}`}
            alt={`${repo.owner} avatar`}
            width={20}
            height={20}
            className="rounded-full"
          />
          {repo.owner}/{repo.name}
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
        </Link>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Stop tracking ${repo.owner}/${repo.name}`}
          onClick={() => deleteRepo.mutate(repo.id)}
          disabled={deleteRepo.isPending}
        >
          <Trash2 className="h-4 w-4 text-red-500" aria-hidden="true" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isPending ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="h-16">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={snapshots}>
                <Line type="monotone" dataKey="stars" stroke="#0ea5e9" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="flex items-center justify-between">
          <StatBadge icon={Star} label="Stars" value={latest?.stars ?? 0} color="text-amber-500" />
          <StatBadge icon={GitFork} label="Forks" value={latest?.forks ?? 0} color="text-violet-500" />
          <StatBadge icon={Eye} label="Watchers" value={latest?.watchers ?? 0} color="text-emerald-500" />
          <DeltaBadge value={starDelta} label="Stars change since last snapshot" />
        </div>
        {insights && insights.recommendation_count > 0 && (
          <StatBadge
            icon={Lightbulb}
            label="Open recommendations"
            value={`${insights.recommendation_count} open recommendation${insights.recommendation_count === 1 ? "" : "s"}`}
            color="text-amber-500"
          />
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Create `frontend/components/overview/add-repo-dialog.tsx`**

```tsx
"use client";

import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAddRepo } from "@/hooks/use-repos";

export function AddRepoDialog() {
  const [open, setOpen] = useState(false);
  const [owner, setOwner] = useState("");
  const [name, setName] = useState("");
  const addRepo = useAddRepo();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    addRepo.mutate(
      { owner, name },
      {
        onSuccess: () => {
          toast.success(`Now tracking ${owner}/${name}`);
          setOwner("");
          setName("");
          setOpen(false);
        },
        onError: () => toast.error("Could not add that repo — check the owner/name and try again."),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Track a repo
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Track a new repo</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="owner">Owner</Label>
              <Input id="owner" value={owner} onChange={(e) => setOwner(e.target.value)} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="name">Repo name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={addRepo.isPending}>
              {addRepo.isPending ? "Adding..." : "Add"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Create `frontend/components/overview/overview-client.tsx`**

```tsx
"use client";

import { FolderGit2 } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { useRepos } from "@/hooks/use-repos";
import { AddRepoDialog } from "@/components/overview/add-repo-dialog";
import { RepoCard } from "@/components/overview/repo-card";

export function OverviewClient() {
  const { data: repos } = useRepos();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SectionHeading icon={FolderGit2} title="Tracked repos" subtitle="Star/fork/watcher trends at a glance" />
        <AddRepoDialog />
      </div>
      {repos && repos.length === 0 ? (
        <EmptyState
          icon={FolderGit2}
          title="No repos tracked yet"
          description="Add a repo to start tracking its growth."
          action={<AddRepoDialog />}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {repos?.map((repo) => <RepoCard key={repo.id} repo={repo} />)}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Rewrite `frontend/app/page.tsx`**

```tsx
import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { OverviewClient } from "@/components/overview/overview-client";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const queryClient = new QueryClient();

  const repos = await api.listRepos();
  queryClient.setQueryData(queryKeys.repos.all, repos);

  await Promise.all(
    repos.flatMap((repo) => [
      queryClient.prefetchQuery({
        queryKey: queryKeys.repos.snapshots(repo.id),
        queryFn: () => api.listSnapshots(repo.id),
      }),
      queryClient.prefetchQuery({
        queryKey: queryKeys.repos.insights(repo.id),
        queryFn: () => api.getInsights(repo.id),
      }),
    ]),
  );

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <OverviewClient />
    </HydrationBoundary>
  );
}
```

- [ ] **Step 6: Manual verification**

Run: `cd frontend && npm run dev`, open `http://localhost:3000`.
Expected: empty state with icon + "Track a repo" button when no repos exist; adding a repo via the dialog shows a toast and the card appears instantly (no reload); deleting a repo removes its card instantly.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/page.tsx frontend/components/overview frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): build Overview page with sparklines, delta badges, add/remove repo"
```

---

## Task 14: Repo detail page

**Files:**
- Create: `frontend/app/repos/[id]/page.tsx`
- Create: `frontend/components/repo-detail/repo-detail-client.tsx`
- Create: `frontend/components/repo-detail/trend-chart.tsx`
- Create: `frontend/components/repo-detail/benchmark-table.tsx`
- Create: `frontend/components/repo-detail/referrers-table.tsx`
- Create: `frontend/components/repo-detail/popular-paths-table.tsx`
- Create: `frontend/components/repo-detail/repo-recommendations.tsx`

**Interfaces:**
- Consumes: `api` (Task 5), `queryKeys` (Task 7), `useRepoSnapshots`/`useRepoBenchmarks`/`useRepoReferrers`/`useRepoPopularPaths`/`useRecommendations`/`useDismissRecommendation` (Task 11), `SectionHeading`/`EmptyState` (Task 9).
- Produces: `/repos/[id]` route — trend chart, benchmark comparison, referrers, popular paths, and this repo's own recommendations (filtered client-side from the cross-repo feed by `repo_id`, since REQ-0010's cross-repo inbox and this scoped view share the same underlying `GET /recommendations` data).

- [ ] **Step 1: Create `frontend/components/repo-detail/trend-chart.tsx`**

```tsx
"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { useRepoSnapshots } from "@/hooks/use-repo-snapshots";

export function TrendChart({ repoId }: { repoId: number }) {
  const { data: snapshots, isPending } = useRepoSnapshots(repoId);

  if (isPending) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={snapshots}>
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line type="monotone" dataKey="stars" stroke="#f59e0b" strokeWidth={2} dot={false} name="Stars" />
          <Line type="monotone" dataKey="forks" stroke="#8b5cf6" strokeWidth={2} dot={false} name="Forks" />
          <Line type="monotone" dataKey="views_14d" stroke="#0ea5e9" strokeWidth={2} dot={false} name="Views (14d)" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/components/repo-detail/benchmark-table.tsx`**

```tsx
"use client";

import { Trophy } from "lucide-react";
import { SectionHeading } from "@/components/ui/section-heading";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useRepoBenchmarks } from "@/hooks/use-repo-benchmarks";

export function BenchmarkTable({ repoId }: { repoId: number }) {
  const { data: benchmarks, isPending } = useRepoBenchmarks(repoId);

  return (
    <div className="space-y-3">
      <SectionHeading icon={Trophy} title="Benchmark repos" subtitle="Similar public repos, for comparison" iconColor="text-amber-500" />
      {isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : benchmarks && benchmarks.length === 0 ? (
        <EmptyState icon={Trophy} title="No benchmarks yet" description="These populate on the next pipeline run." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Repo</TableHead>
              <TableHead>Stars</TableHead>
              <TableHead>Forks</TableHead>
              <TableHead>Topics</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {benchmarks?.map((b) => (
              <TableRow key={b.full_name}>
                <TableCell>{b.full_name}</TableCell>
                <TableCell>{b.stars}</TableCell>
                <TableCell>{b.forks}</TableCell>
                <TableCell>{b.topics.join(", ")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/components/repo-detail/referrers-table.tsx`**

```tsx
"use client";

import { Link2 } from "lucide-react";
import { SectionHeading } from "@/components/ui/section-heading";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useRepoReferrers } from "@/hooks/use-repo-referrers";

export function ReferrersTable({ repoId }: { repoId: number }) {
  const { data: referrers, isPending } = useRepoReferrers(repoId);

  return (
    <div className="space-y-3">
      <SectionHeading icon={Link2} title="Referrers" subtitle="Where traffic is coming from" iconColor="text-emerald-500" />
      {isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : referrers && referrers.length === 0 ? (
        <EmptyState icon={Link2} title="No referrer data yet" description="GitHub's traffic API is a rolling 14-day window." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Source</TableHead>
              <TableHead>Views</TableHead>
              <TableHead>Uniques</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {referrers?.map((r) => (
              <TableRow key={r.id}>
                <TableCell>{r.referrer}</TableCell>
                <TableCell>{r.count}</TableCell>
                <TableCell>{r.uniques}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/components/repo-detail/popular-paths-table.tsx`**

```tsx
"use client";

import { Route } from "lucide-react";
import { SectionHeading } from "@/components/ui/section-heading";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useRepoPopularPaths } from "@/hooks/use-repo-popular-paths";

export function PopularPathsTable({ repoId }: { repoId: number }) {
  const { data: paths, isPending } = useRepoPopularPaths(repoId);

  return (
    <div className="space-y-3">
      <SectionHeading icon={Route} title="Popular content" subtitle="Most-viewed paths in this repo" iconColor="text-sky-500" />
      {isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : paths && paths.length === 0 ? (
        <EmptyState icon={Route} title="No path data yet" description="GitHub's traffic API is a rolling 14-day window." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Path</TableHead>
              <TableHead>Views</TableHead>
              <TableHead>Uniques</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paths?.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-mono text-xs">{p.path}</TableCell>
                <TableCell>{p.count}</TableCell>
                <TableCell>{p.uniques}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create `frontend/components/repo-detail/repo-recommendations.tsx`**

```tsx
"use client";

import { CheckCircle2, Lightbulb, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { useDismissRecommendation, useRecommendations } from "@/hooks/use-recommendations";

export function RepoRecommendations({ repoId }: { repoId: number }) {
  const { data: recommendations, isPending } = useRecommendations();
  const dismiss = useDismissRecommendation();

  const scoped = recommendations?.filter((r) => r.repo_id === repoId && !r.dismissed);

  return (
    <div className="space-y-3">
      <SectionHeading icon={Lightbulb} title="Recommendations" subtitle="Fact-checked suggestions for this repo" iconColor="text-amber-500" />
      {isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : scoped && scoped.length === 0 ? (
        <EmptyState icon={CheckCircle2} title="All caught up" description="No open recommendations for this repo." />
      ) : (
        <div className="space-y-2">
          {scoped?.map((rec) => (
            <Card key={rec.id}>
              <CardContent className="flex items-start justify-between gap-4 py-4">
                <div>
                  <p className="font-medium">{rec.title}</p>
                  <p className="text-sm text-muted-foreground">{rec.body}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Dismiss recommendation"
                  onClick={() => dismiss.mutate({ id: rec.id, dismissed: true })}
                >
                  <X className="h-4 w-4 text-red-500" aria-hidden="true" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Create `frontend/components/repo-detail/repo-detail-client.tsx`**

```tsx
"use client";

import { GitBranch } from "lucide-react";
import { SectionHeading } from "@/components/ui/section-heading";
import { TrendChart } from "@/components/repo-detail/trend-chart";
import { BenchmarkTable } from "@/components/repo-detail/benchmark-table";
import { ReferrersTable } from "@/components/repo-detail/referrers-table";
import { PopularPathsTable } from "@/components/repo-detail/popular-paths-table";
import { RepoRecommendations } from "@/components/repo-detail/repo-recommendations";
import type { Repo } from "@/lib/api-types";

export function RepoDetailClient({ repo }: { repo: Repo }) {
  return (
    <div className="space-y-8">
      <SectionHeading icon={GitBranch} title={`${repo.owner}/${repo.name}`} subtitle="Trends, benchmarks, and recommendations" />
      <TrendChart repoId={repo.id} />
      <BenchmarkTable repoId={repo.id} />
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <ReferrersTable repoId={repo.id} />
        <PopularPathsTable repoId={repo.id} />
      </div>
      <RepoRecommendations repoId={repo.id} />
    </div>
  );
}
```

- [ ] **Step 7: Create `frontend/app/repos/[id]/page.tsx`**

```tsx
import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { BackendError } from "@/lib/backend-client";
import { queryKeys } from "@/lib/query-keys";
import { RepoDetailClient } from "@/components/repo-detail/repo-detail-client";

export const dynamic = "force-dynamic";

export default async function RepoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const repoId = Number(id);
  const queryClient = new QueryClient();

  let repo;
  try {
    repo = await api.getRepo(repoId);
  } catch (error) {
    if (error instanceof BackendError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  await Promise.all([
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.snapshots(repoId), queryFn: () => api.listSnapshots(repoId) }),
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.benchmarks(repoId), queryFn: () => api.listBenchmarks(repoId) }),
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.referrers(repoId), queryFn: () => api.listReferrers(repoId) }),
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.popularPaths(repoId), queryFn: () => api.listPopularPaths(repoId) }),
    queryClient.prefetchQuery({ queryKey: queryKeys.recommendations.all, queryFn: () => api.listRecommendations() }),
  ]);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <RepoDetailClient repo={repo} />
    </HydrationBoundary>
  );
}
```

- [ ] **Step 8: Manual verification**

Run: `cd frontend && npm run dev`, add a repo on the Overview page, click into its detail page.
Expected: trend chart, benchmark/referrer/path tables (each with their own empty state until the pipeline runs), and scoped recommendations render; visiting `/repos/999999` renders the Next.js not-found page.

- [ ] **Step 9: Commit**

```bash
git add frontend/app/repos frontend/components/repo-detail
git commit -m "feat(frontend): build Repo detail page with trends, benchmarks, referrers, recommendations"
```

---

## Task 15: Recommendations inbox page

**Files:**
- Create: `frontend/app/recommendations/page.tsx`
- Create: `frontend/components/recommendations/recommendations-client.tsx`

**Interfaces:**
- Consumes: `api` (Task 5), `queryKeys` (Task 7), `useRecommendations`/`useDismissRecommendation` (Task 11), `useRepos` (Task 11, for owner/name display), `SectionHeading`/`EmptyState` (Task 9).
- Produces: `/recommendations` route — cross-repo feed with filter/sort and dismiss, per REQ-0010.

- [ ] **Step 1: Create `frontend/components/recommendations/recommendations-client.tsx`**

```tsx
"use client";

import { CheckCircle2, Filter, Lightbulb, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { useDismissRecommendation, useRecommendations } from "@/hooks/use-recommendations";
import { useRepos } from "@/hooks/use-repos";

export function RecommendationsClient() {
  const { data: recommendations } = useRecommendations();
  const { data: repos } = useRepos();
  const dismiss = useDismissRecommendation();
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const repoNameById = useMemo(() => {
    const map = new Map<number, string>();
    repos?.forEach((r) => map.set(r.id, `${r.owner}/${r.name}`));
    return map;
  }, [repos]);

  const categories = useMemo(
    () => Array.from(new Set(recommendations?.map((r) => r.category) ?? [])),
    [recommendations],
  );

  const visible = recommendations?.filter(
    (r) => !r.dismissed && (categoryFilter === null || r.category === categoryFilter),
  );

  return (
    <div className="space-y-6">
      <SectionHeading icon={Lightbulb} title="Recommendations inbox" subtitle="Fact-checked suggestions across every tracked repo" iconColor="text-amber-500" />

      {categories.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <Button variant={categoryFilter === null ? "default" : "outline"} size="sm" onClick={() => setCategoryFilter(null)}>
            All
          </Button>
          {categories.map((category) => (
            <Button
              key={category}
              variant={categoryFilter === category ? "default" : "outline"}
              size="sm"
              onClick={() => setCategoryFilter(category)}
            >
              {category}
            </Button>
          ))}
        </div>
      )}

      {visible && visible.length === 0 ? (
        <EmptyState icon={CheckCircle2} title="Inbox zero" description="No open recommendations right now." />
      ) : (
        <div className="space-y-2">
          {visible?.map((rec) => (
            <Card key={rec.id}>
              <CardContent className="flex items-start justify-between gap-4 py-4">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">{repoNameById.get(rec.repo_id) ?? `repo #${rec.repo_id}`}</p>
                  <p className="font-medium">{rec.title}</p>
                  <p className="text-sm text-muted-foreground">{rec.body}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Dismiss recommendation"
                  onClick={() => dismiss.mutate({ id: rec.id, dismissed: true })}
                >
                  <X className="h-4 w-4 text-red-500" aria-hidden="true" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/app/recommendations/page.tsx`**

```tsx
import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { RecommendationsClient } from "@/components/recommendations/recommendations-client";

export const dynamic = "force-dynamic";

export default async function RecommendationsPage() {
  const queryClient = new QueryClient();

  await Promise.all([
    queryClient.prefetchQuery({ queryKey: queryKeys.recommendations.all, queryFn: () => api.listRecommendations() }),
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.all, queryFn: () => api.listRepos() }),
  ]);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <RecommendationsClient />
    </HydrationBoundary>
  );
}
```

- [ ] **Step 3: Manual verification**

Run: `cd frontend && npm run dev`, open `http://localhost:3000/recommendations`.
Expected: category filter buttons appear once recommendations exist; dismissing one removes it instantly from this page and would also remove it from the repo detail page's scoped list (same query key).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/recommendations frontend/components/recommendations
git commit -m "feat(frontend): build Recommendations inbox page with category filter"
```

---

## Task 16: Pipeline runs history page

**Files:**
- Create: `frontend/app/runs/page.tsx`
- Create: `frontend/components/runs/runs-client.tsx`
- Create: `frontend/components/runs/run-row.tsx`

**Interfaces:**
- Consumes: `api` (Task 5), `queryKeys` (Task 7), `useRuns`/`useTriggerRun`/`useRunStages` (Task 11), `SectionHeading`/`EmptyState` (Task 9).
- Produces: `/runs` route — execution history with expandable per-stage status, and a manual "Run now" trigger, per REQ-0010.

- [ ] **Step 1: Create `frontend/components/runs/run-row.tsx`**

```tsx
"use client";

import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunStages } from "@/hooks/use-run-stages";
import type { PipelineRun } from "@/lib/api-types";

const STATUS_META = {
  ok: { icon: CheckCircle2, color: "text-emerald-500", label: "OK" },
  degraded: { icon: AlertTriangle, color: "text-amber-500", label: "Degraded" },
  running: { icon: Loader2, color: "text-sky-500", label: "Running" },
} as const;

export function RunRow({ run }: { run: PipelineRun }) {
  const [expanded, setExpanded] = useState(false);
  const { data: stages, isPending } = useRunStages(run.id, expanded);
  const meta = STATUS_META[run.status as keyof typeof STATUS_META] ?? STATUS_META.running;
  const StatusIcon = meta.icon;

  return (
    <Card>
      <CardContent className="py-3">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex w-full items-center justify-between text-left"
          aria-expanded={expanded}
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            {expanded ? <ChevronDown className="h-4 w-4" aria-hidden="true" /> : <ChevronRight className="h-4 w-4" aria-hidden="true" />}
            Run #{run.id}
          </span>
          <span className={`flex items-center gap-1 text-sm ${meta.color}`}>
            <StatusIcon className="h-4 w-4" aria-hidden="true" />
            {meta.label}
          </span>
        </button>
        {expanded && (
          <div className="mt-3 space-y-1 border-t pt-3">
            {isPending ? (
              <Skeleton className="h-20 w-full" />
            ) : (
              stages?.map((stage) => (
                <div key={stage.id} className="text-sm">
                  <div className="flex items-center justify-between">
                    <span>{stage.stage_name}</span>
                    <span className="flex items-center gap-2 text-muted-foreground">
                      {stage.duration_ms}ms
                      <span className={stage.status === "ok" ? "text-emerald-500" : "text-red-500"}>{stage.status}</span>
                    </span>
                  </div>
                  {stage.error && <p className="mt-0.5 text-xs text-red-500">{stage.error}</p>}
                </div>
              ))
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Create `frontend/components/runs/runs-client.tsx`**

```tsx
"use client";

import { History, Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { useRuns, useTriggerRun } from "@/hooks/use-runs";
import { RunRow } from "@/components/runs/run-row";

export function RunsClient() {
  const { data: runs } = useRuns();
  const triggerRun = useTriggerRun();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SectionHeading icon={History} title="Pipeline runs" subtitle="Execution history, per-stage status" iconColor="text-violet-500" />
        <Button
          onClick={() =>
            triggerRun.mutate(undefined, {
              onSuccess: () => toast.success("Pipeline run triggered"),
              onError: () => toast.error("Could not trigger a run"),
            })
          }
          disabled={triggerRun.isPending}
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {triggerRun.isPending ? "Running..." : "Run now"}
        </Button>
      </div>
      {runs && runs.length === 0 ? (
        <EmptyState icon={History} title="No runs yet" description="Trigger one manually or wait for the daily schedule." />
      ) : (
        <div className="space-y-2">{runs?.map((run) => <RunRow key={run.id} run={run} />)}</div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/app/runs/page.tsx`**

```tsx
import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { RunsClient } from "@/components/runs/runs-client";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  const queryClient = new QueryClient();

  await queryClient.prefetchQuery({ queryKey: queryKeys.runs.all, queryFn: () => api.listRuns() });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <RunsClient />
    </HydrationBoundary>
  );
}
```

- [ ] **Step 4: Manual verification**

Run: `cd frontend && npm run dev`, open `http://localhost:3000/runs`.
Expected: "Run now" triggers a toast; clicking a run row expands to show per-stage status/duration, fetched lazily (`enabled: expanded`) so collapsed rows never fetch stage detail.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/runs frontend/components/runs
git commit -m "feat(frontend): build Pipeline runs history page with expandable stage detail"
```

---

## Task 17: Settings page

**Files:**
- Create: `frontend/app/settings/page.tsx`
- Create: `frontend/components/settings/settings-client.tsx`
- Create: `frontend/components/settings/provider-status-table.tsx`

**Interfaces:**
- Consumes: `api` (Task 5), `queryKeys` (Task 7), `useRepos`/`useAddRepo`/`useDeleteRepo` (Task 11), `useProviderStatus` (Task 11), `AddRepoDialog` (Task 13), `SectionHeading`/`EmptyState` (Task 9).
- Produces: `/settings` route — manage tracked repos (reusing the Overview's add/remove) and LLM provider health/usage, per REQ-0010.

- [ ] **Step 1: Create `frontend/components/settings/provider-status-table.tsx`**

```tsx
"use client";

import { Cpu } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProviderStatus } from "@/hooks/use-provider-status";

export function ProviderStatusTable() {
  const { data: statuses, isPending } = useProviderStatus();

  return (
    <div className="space-y-3">
      <SectionHeading icon={Cpu} title="LLM provider usage" subtitle="Calls made today, per free-tier provider" iconColor="text-sky-500" />
      {isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : statuses && statuses.length === 0 ? (
        <EmptyState icon={Cpu} title="No usage yet today" description="Provider usage resets daily." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Provider</TableHead>
              <TableHead>Calls today</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {statuses?.map((s) => (
              <TableRow key={s.provider}>
                <TableCell>{s.provider}</TableCell>
                <TableCell>{s.calls_today}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/components/settings/settings-client.tsx`**

```tsx
"use client";

import { FolderGit2, Settings as SettingsIcon, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { AddRepoDialog } from "@/components/overview/add-repo-dialog";
import { ProviderStatusTable } from "@/components/settings/provider-status-table";
import { useDeleteRepo, useRepos } from "@/hooks/use-repos";

export function SettingsClient() {
  const { data: repos } = useRepos();
  const deleteRepo = useDeleteRepo();

  return (
    <div className="space-y-8">
      <SectionHeading icon={SettingsIcon} title="Settings" subtitle="Manage tracked repos and provider health" />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <SectionHeading icon={FolderGit2} title="Tracked repos" iconColor="text-sky-500" />
          <AddRepoDialog />
        </div>
        {repos && repos.length === 0 ? (
          <EmptyState icon={FolderGit2} title="No repos tracked yet" description="Add a repo to get started." />
        ) : (
          <div className="space-y-2">
            {repos?.map((repo) => (
              <Card key={repo.id}>
                <CardContent className="flex items-center justify-between py-3">
                  <span>
                    {repo.owner}/{repo.name}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Stop tracking ${repo.owner}/${repo.name}`}
                    onClick={() => deleteRepo.mutate(repo.id)}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" aria-hidden="true" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <ProviderStatusTable />
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/app/settings/page.tsx`**

```tsx
import { QueryClient, dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { SettingsClient } from "@/components/settings/settings-client";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const queryClient = new QueryClient();

  await Promise.all([
    queryClient.prefetchQuery({ queryKey: queryKeys.repos.all, queryFn: () => api.listRepos() }),
    queryClient.prefetchQuery({ queryKey: queryKeys.providers.status, queryFn: () => api.providerStatus() }),
  ]);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <SettingsClient />
    </HydrationBoundary>
  );
}
```

- [ ] **Step 4: Manual verification**

Run: `cd frontend && npm run dev`, open `http://localhost:3000/settings`.
Expected: tracked-repo list with remove buttons, "Track a repo" dialog reused from Overview, LLM provider usage table (empty state until any pipeline run has made an LLM call today).

- [ ] **Step 5: Commit**

```bash
git add frontend/app/settings frontend/components/settings
git commit -m "feat(frontend): build Settings page with repo management and LLM provider usage"
```

---

## Task 18: Vercel production guardrails

**Files:**
- Modify: `frontend/next.config.ts`
- Create: `frontend/vercel.json`
- Create: `frontend/app/robots.ts`

**Interfaces:**
- Produces: security headers, immutable static-asset caching, and a single-source no-crawl `robots.ts`, per `docs/VERCEL_PRODUCTION_GUARDRAILS.md` and REQ-0014.

- [ ] **Step 1: Rewrite `frontend/next.config.ts`**

```ts
import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-XSS-Protection", value: "1; mode=block" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [{ protocol: "https", hostname: "avatars.githubusercontent.com", pathname: "/**" }],
  },
  async headers() {
    return [
      { source: "/(.*)", headers: securityHeaders },
      {
        source: "/_next/static/(.*)",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 2: Create `frontend/vercel.json`**

```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), geolocation=()" }
      ]
    },
    {
      "source": "/_next/static/(.*)",
      "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }]
    }
  ]
}
```

- [ ] **Step 3: Create `frontend/app/robots.ts`**

```ts
import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", disallow: "/" }],
  };
}
```

- [ ] **Step 4: Verify no conflicting robots source exists**

Run: `ls frontend/public/robots.txt 2>/dev/null || echo "no static robots.txt — single source confirmed"`
Expected: `no static robots.txt — single source confirmed` (a static `public/robots.txt` would conflict with `app/robots.ts`; `create-next-app` doesn't generate one, so this should already be clean).

- [ ] **Step 5: Verify the build applies headers**

Run: `cd frontend && npm run build && npm run start &` then `curl -sI http://localhost:3000/ | grep -i x-frame-options`
Expected: `X-Frame-Options: DENY` present. Stop the server afterward (`kill %1`).

- [ ] **Step 6: Commit**

```bash
git add frontend/next.config.ts frontend/vercel.json frontend/app/robots.ts
git commit -m "feat(frontend): add Vercel production guardrails (security headers, immutable caching, no-crawl robots)"
```

**Manual step for the user at deploy time (not part of this task's automated verification):** enable Bot Protection + AI Bot blocking in the Vercel dashboard under Firewall → Bot Management, per `docs/VERCEL_PRODUCTION_GUARDRAILS.md` §1.

---

## Task 19: Component tests (Vitest + React Testing Library) and SSE smoke test

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/tests/setup.ts`
- Create: `frontend/tests/delta-badge.test.tsx`
- Create: `frontend/tests/empty-state.test.tsx`
- Create: `frontend/tests/use-live-events.test.tsx`

**Interfaces:**
- Consumes: `DeltaBadge`, `EmptyState` (Task 9), `useLiveEvents` (Task 8), `queryKeys` (Task 7).
- Produces: the automated frontend test suite required by the approved spec's §6 testing approach (component tests for shared primitives + an SSE-invalidation smoke test).

- [ ] **Step 1: Install test dependencies**

Run: `cd frontend && npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom`

- [ ] **Step 2: Create `frontend/vitest.config.ts`**

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
  resolve: {
    alias: { "@": new URL(".", import.meta.url).pathname },
  },
});
```

- [ ] **Step 3: Create `frontend/tests/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 4: Add the `test` script to `frontend/package.json`**

```json
"test": "vitest run"
```

- [ ] **Step 5: Write the failing test — `frontend/tests/delta-badge.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DeltaBadge } from "@/components/ui/delta-badge";

describe("DeltaBadge", () => {
  it("shows a positive delta with a plus sign", () => {
    render(<DeltaBadge value={5} label="Stars change" />);
    expect(screen.getByText("+5")).toBeInTheDocument();
  });

  it("shows a negative delta without a plus sign", () => {
    render(<DeltaBadge value={-3} label="Stars change" />);
    expect(screen.getByText("-3")).toBeInTheDocument();
  });

  it("shows zero with no change", () => {
    render(<DeltaBadge value={0} label="Stars change" />);
    expect(screen.getByLabelText("Stars change: no change")).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Write the failing test — `frontend/tests/empty-state.test.tsx`**

```tsx
import { FolderGit2 } from "lucide-react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "@/components/ui/empty-state";

describe("EmptyState", () => {
  it("renders the title and description", () => {
    render(<EmptyState icon={FolderGit2} title="No repos tracked yet" description="Add a repo to get started." />);
    expect(screen.getByText("No repos tracked yet")).toBeInTheDocument();
    expect(screen.getByText("Add a repo to get started.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Write the failing SSE smoke test — `frontend/tests/use-live-events.test.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/lib/query-keys";
import { useLiveEvents } from "@/hooks/use-live-events";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners: Record<string, ((event: MessageEvent) => void)[]> = {};

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: MessageEvent) => void) {
    this.listeners[type] = [...(this.listeners[type] ?? []), handler];
  }

  emit(type: string, data: unknown) {
    for (const handler of this.listeners[type] ?? []) {
      handler({ type, data: JSON.stringify(data) } as MessageEvent);
    }
  }

  close() {}
}

function Harness() {
  useLiveEvents();
  return null;
}

describe("useLiveEvents", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("invalidates the repos query when a repo_added event arrives", () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    render(
      <QueryClientProvider client={queryClient}>
        <Harness />
      </QueryClientProvider>,
    );

    const source = FakeEventSource.instances[0];
    source.emit("repo_added", { id: 1 });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.repos.all });
  });
});
```

- [ ] **Step 8: Run tests to verify they fail (before this is the first run, confirm the harness itself works)**

Run: `cd frontend && npm test`
Expected: all 5 tests pass on first run once the files above exist (these primitives already exist from Tasks 8–9, so this step is the standard "run once to confirm the new test files are wired correctly," not a red/green cycle against not-yet-written app code).

- [ ] **Step 9: Commit**

```bash
git add frontend/vitest.config.ts frontend/tests frontend/package.json frontend/package-lock.json
git commit -m "test(frontend): add component tests and SSE-invalidation smoke test"
```

---

## Task 20: Final polish — lint/build/audit clean, manual verification pass

**Files:**
- Modify: any file flagged by lint/build/audit in Steps 1–3 (fixes only, no new features)

**Interfaces:**
- Consumes: the entire frontend built in Tasks 3–19.
- Produces: nothing new — this task is the acceptance gate for REQ-0010–REQ-0014, mirroring the backend's final whole-branch review discipline (CAPA-0002 pattern: check whole-codebase behavior, not just per-task diffs).

- [ ] **Step 1: Run lint clean**

Run: `cd frontend && npm run lint`
Expected: no errors. Fix any that appear (do not disable rules to silence them, except the pre-existing documented `SafeImage` `@next/next/no-img-element` disables from Task 10).

- [ ] **Step 2: Run the build clean**

Run: `cd frontend && npm run build`
Expected: build succeeds with no warnings about unused exports/dependencies.

- [ ] **Step 3: Run a dependency audit**

Run: `cd frontend && npm audit`
Expected: 0 vulnerabilities. If any appear, run `npm audit fix` and re-verify the build/tests still pass.

- [ ] **Step 4: Run the full test suite**

Run: `cd frontend && npm test`
Expected: all tests pass.

- [ ] **Step 5: Manual browser verification — golden path**

With the backend running (`uvicorn app.main:app --reload`) and frontend running (`npm run dev`):
1. Open `/` — empty state shows.
2. Add a repo via the dialog — card appears instantly, no reload.
3. Click into the repo's detail page — trend chart, benchmark/referrer/path tables, recommendations render (empty states expected until the first pipeline run).
4. Go to `/runs`, click "Run now" — toast appears; once it completes, expand the new run row to see per-stage status.
5. Go to `/recommendations` — any recommendations produced by the run above appear; dismiss one — it disappears instantly here and would also disappear from the repo detail page (same query key, confirmed by Task 14's scoped filter reading the same cache entry).
6. Open the app in two browser tabs; dismiss a recommendation in one tab — confirm the other tab updates without a refresh (SSE invalidation working end-to-end).
7. Toggle dark mode — confirm all pages remain legible (icons, semantic colors, tables, charts).

- [ ] **Step 6: Manual browser verification — edge cases**

1. With zero repos tracked, confirm every page (Overview, Recommendations, Runs, Settings) shows a coherent empty state, not a blank page or console error.
2. Stop the backend process, reload any page — confirm a clear error surfaces (not a silent blank page); this exercises `BackendError`/`ClientFetchError` propagating through `proxyRoute`/`fetchJson` rather than swallowing the failure.
3. Add a repo with an owner/name that isn't a real GitHub repo — confirm the toast error path fires rather than a crash (the backend's own `GitHubClient` read calls will fail gracefully in a later pipeline run; the add-repo call itself only writes an `owner`/`name` pair, so this specifically tests that a subsequent pipeline run against a nonexistent repo degrades — check the run's stage detail on `/runs` shows an `error` on the Extractor stage rather than crashing the whole run, per RISK-0002/CAPA-0001's existing backend guarantee).

- [ ] **Step 7: Update traceability**

Update `.agile-v/REQUIREMENTS.md`: change REQ-0010–REQ-0014 status lines from `approved [C1], not started` to `implemented [C1]`, listing the primary artifacts (the `frontend/app`, `frontend/components`, `frontend/hooks`, `frontend/lib` paths built in this plan).

- [ ] **Step 8: Commit**

```bash
git add frontend .agile-v/REQUIREMENTS.md
git commit -m "chore(frontend): final polish — lint/build/audit clean, traceability updated"
```

---

## Post-plan note (not a task — flag for the next Agile-V gate)

This plan's completion is the natural point for a **Gate 2** decision on the frontend sub-scope (REQ-0010–REQ-0014), mirroring `GATE-0001` for the backend. Per `POLICY.yaml` POL-0006, do not deploy to Vercel until that gate is explicitly logged as Approved in `.agile-v/APPROVALS.md`, and until RISK-0005/RISK-0006 (CORS env var, manual Alembic migration) are resolved in the deploy runbook, per the backend's still-open pre-deploy items.
