# Phase 4B: Content Generation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a second `Stage`/`PipelineRunner` pipeline that generates README, missing-doc, topic, and SEO-description `Draft` suggestions via best-of-3 candidate generation + LLM-as-judge validation, triggered both manually and on a staggered daily schedule, rendered properly in the existing Drafts inbox.

**Architecture:** Mirrors the existing 7-stage analytics pipeline (`backend/app/pipeline/*.py`) with a parallel `backend/app/pipeline/content/*.py` package sharing the same `Stage` contract (`Stage.run(ctx) -> ctx`) and the same `PipelineRunner`, extended with a `context_factory` param so it can build a `ContentPipelineContext` instead of the analytics `PipelineContext`. `LLMRouter` gains a `skip_providers` param so the Synthesizer can force 3 candidates onto 3 different providers. `PipelineRun` gains a `pipeline_kind` column so the two pipelines' history stays distinguishable in the UI.

**Tech Stack:** FastAPI/SQLAlchemy/Alembic (backend, unchanged), Next.js 16 App Router/TanStack Query/TypeScript (frontend, unchanged). No new dependencies on either side.

## Global Constraints

- Every new/changed endpoint keeps `dependencies=[Depends(require_api_key)]` + `require_user` scoping; every query filtered by `user_id`; 404 (never 403) on cross-user access.
- No endpoint path contains `analytics`/`analysis`/`tracking`/`performance`/`metrics`.
- Every existing call site of `LLMRouter.chat_completion`, `PipelineRunner.__init__`/`run_for_repo`, and `PipelineRun`/`PipelineRunOut` must keep working unchanged — all new parameters/columns are additive with defaults matching current behavior (`skip_providers=None`, `context_factory=PipelineContext`, `pipeline_kind="analytics"`).
- Every CRUD/generation action invalidates the relevant TanStack Query key everywhere via SSE — no page refresh, current tab and all other open tabs.
- SSR data-fetching stays in `page.tsx`; only genuinely interactive code in `"use client"` components.
- Frontend types come from the generated OpenAPI schema wherever the shape is expressible there (`frontend/lib/api-types.ts`); the per-kind `Draft.content` discriminated union is hand-written in `frontend/types/drafts.ts` since FastAPI's `content: dict` can't express it at the schema level.
- Comments explain WHY, never WHAT. No unrequested summary `.md` files. Never delete unrelated working code.
- Backend regression baseline: `cd backend && .venv/bin/python -m pytest -v` must stay 100% passing after every task. Frontend: `npx tsc --noEmit`, `npx eslint .`, `npx vitest run`, `npm run build` must all stay clean.

---

### Task 1: `LLMRouter.skip_providers` + `available_provider_names`

**Files:**
- Modify: `backend/app/llm_router.py`
- Test: `backend/tests/test_llm_router.py`

**Interfaces:**
- Produces: `LLMRouter.chat_completion(self, messages: list[dict[str, str]], skip_providers: set[str] | None = None) -> str` (extends existing signature, backward-compatible), `LLMRouter.available_provider_names(self) -> list[str]` (new method — returns configured provider names in fallback order, used by `ContentSynthesizer` in Task 6 to build progressively larger skip sets without hardcoding provider names).

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_llm_router.py`:

```python
def test_skip_providers_excludes_named_providers():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    router = LLMRouter(settings=_settings(), db_session=_db(), transport=httpx.MockTransport(handler))
    router.chat_completion([{"role": "user", "content": "hi"}], skip_providers={"groq"})

    assert not any("groq.com" in c for c in calls)
    assert any("generativelanguage" in c for c in calls)


def test_skip_providers_none_behaves_like_default():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "groq.com" in str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    router = LLMRouter(settings=_settings(), db_session=_db(), transport=httpx.MockTransport(handler))
    result = router.chat_completion([{"role": "user", "content": "hi"}], skip_providers=None)
    assert result == "hello"


def test_available_provider_names_reflects_configured_keys():
    router = LLMRouter(settings=_settings(), db_session=_db())
    assert router.available_provider_names() == ["groq", "gemini"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_llm_router.py -v`
Expected: FAIL — `chat_completion() got an unexpected keyword argument 'skip_providers'` and `'LLMRouter' object has no attribute 'available_provider_names'`.

- [ ] **Step 3: Implement**

In `backend/app/llm_router.py`, replace the `chat_completion` method and add `available_provider_names`:

```python
    def chat_completion(self, messages: list[dict[str, str]], skip_providers: set[str] | None = None) -> str:
        last_error: Exception | None = None
        skip_providers = skip_providers or set()

        for provider in self._providers():
            if provider.name in skip_providers:
                continue
            if self._is_near_limit(provider.name):
                continue
            for model in provider.models:
                try:
                    result = self._call(provider, model, messages)
                    self._record_usage(provider.name)
                    return result
                except Exception as exc:  # any failure: try the next model in this provider
                    last_error = exc
                    continue

        raise LLMRouterError(f"All LLM providers failed: {last_error}")

    def available_provider_names(self) -> list[str]:
        return [p.name for p in self._providers()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_llm_router.py -v`
Expected: PASS (7/7 — the 4 existing tests plus the 3 new ones).

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm_router.py backend/tests/test_llm_router.py
git commit -m "feat(llm_router): add skip_providers and available_provider_names"
```

---

### Task 2: `PipelineRun.pipeline_kind` + `PipelineRunner` context factory

**Files:**
- Modify: `backend/app/models.py`, `backend/app/pipeline/runner.py`, `backend/app/api/runs.py`
- Create: `backend/alembic/versions/<autogenerated>_add_pipeline_kind_to_pipeline_runs.py` (via `alembic revision --autogenerate`)
- Test: `backend/tests/test_runner.py`, `backend/tests/test_runs_api.py`

**Interfaces:**
- Consumes: `app.pipeline.base.PipelineContext`, `app.pipeline.base.Stage` (unchanged).
- Produces: `PipelineRunner.__init__(self, stages: list[Stage], db_session: Session, context_factory: Callable[[Repo], Any] = PipelineContext, pipeline_kind: str = "analytics")`. `PipelineRun.pipeline_kind: Mapped[str]`. `PipelineRunOut.pipeline_kind: str`. Task 9's `content_jobs.py` passes `context_factory=ContentPipelineContext, pipeline_kind="content"`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_runner.py` (below the existing tests, same file):

```python
class _RecordsRepoStage(Stage):
    name = "records_repo"

    def run(self, ctx):
        ctx.raw["saw_repo_id"] = ctx.repo.id
        return ctx


def test_runner_defaults_to_analytics_pipeline_kind(seed_user):
    db, repo = _db(seed_user)
    runner = PipelineRunner(stages=[_RecordsRepoStage()], db_session=db)
    runner.run_for_repo(repo)

    run_row = db.query(PipelineRun).first()
    assert run_row.pipeline_kind == "analytics"
    db.close()


def test_runner_uses_custom_context_factory_and_pipeline_kind(seed_user):
    db, repo = _db(seed_user)

    class _FakeCtx:
        def __init__(self, repo):
            self.repo = repo
            self.raw = {}
            self.errors = []

    runner = PipelineRunner(
        stages=[_RecordsRepoStage()],
        db_session=db,
        context_factory=_FakeCtx,
        pipeline_kind="content",
    )
    ctx = runner.run_for_repo(repo)

    assert ctx.raw["saw_repo_id"] == repo.id
    run_row = db.query(PipelineRun).first()
    assert run_row.pipeline_kind == "content"
    db.close()
```

Add to `backend/tests/test_runs_api.py`:

```python
def test_list_runs_exposes_pipeline_kind(client):
    client.post("/repos", json={"owner": "octocat", "name": "hello-world"})
    with patch("app.pipeline.jobs.run_pipeline_for_all_repos"):
        client.post("/runs")

    from app.db import SessionLocal
    from app.models import PipelineRun
    db = SessionLocal()
    db.query(PipelineRun).update({"status": "ok"})
    db.commit()
    db.close()

    resp = client.get("/runs")
    assert resp.status_code == 200
    assert all("pipeline_kind" in run for run in resp.json())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_runner.py tests/test_runs_api.py -v`
Expected: FAIL — `PipelineRunner.__init__() got an unexpected keyword argument 'context_factory'` and `AttributeError`/`KeyError` on `pipeline_kind`.

- [ ] **Step 3: Implement**

In `backend/app/models.py`, add the column to `PipelineRun` (after `status`):

```python
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running")
    pipeline_kind: Mapped[str] = mapped_column(String(50), default="analytics")
```

Generate the migration:

```bash
cd backend && .venv/bin/alembic revision --autogenerate -m "add pipeline_kind to pipeline_runs"
```

Open the generated file and confirm `upgrade()` contains an `op.add_column('pipeline_runs', sa.Column('pipeline_kind', sa.String(length=50), nullable=False, server_default='analytics'))` (add `server_default='analytics'` by hand if autogenerate omits it — existing rows must backfill, and SQLite/Postgres both require a server default to add a NOT NULL column to a non-empty table). Confirm `downgrade()` drops the column. Apply it:

```bash
.venv/bin/alembic upgrade head
```

In `backend/app/pipeline/runner.py`, replace the class:

```python
from typing import Any, Callable
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import PipelineRun, Repo, StageRun
from app.pipeline.base import PipelineContext, Stage


class PipelineRunner:
    def __init__(
        self,
        stages: list[Stage],
        db_session: Session,
        context_factory: Callable[[Repo], Any] = PipelineContext,
        pipeline_kind: str = "analytics",
    ):
        self.stages = stages
        self.db = db_session
        self.context_factory = context_factory
        self.pipeline_kind = pipeline_kind

    def run_for_repo(self, repo: Repo) -> Any:
        run_row = PipelineRun(status="running", user_id=repo.user_id, pipeline_kind=self.pipeline_kind)
        self.db.add(run_row)
        self.db.commit()
        self.db.refresh(run_row)

        ctx = self.context_factory(repo)
        had_error = False

        for stage in self.stages:
            start = time.monotonic()
            status = "ok"
            error_text: str | None = None
            try:
                ctx = stage.run(ctx)
            except Exception as exc:  # a stage failure must not stop the pipeline
                self.db.rollback()  # reset a possibly-poisoned session before we log this stage
                status = "error"
                error_text = str(exc)
                ctx.errors.append(f"{stage.name}: {exc}")
                had_error = True
            duration_ms = int((time.monotonic() - start) * 1000)

            self.db.add(StageRun(
                user_id=repo.user_id,
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

Note `context_factory`'s default is `PipelineContext` itself (the class), called as `PipelineContext(repo)` — matches its existing single positional-or-keyword `repo` field, so this is a drop-in replacement for the old hardcoded `PipelineContext(repo=repo)`.

In `backend/app/api/runs.py`, add the field to `PipelineRunOut`:

```python
class PipelineRunOut(BaseModel):
    id: int
    status: str
    pipeline_kind: str
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest -v`
Expected: PASS, full suite (no regressions in any existing pipeline/runs test).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/pipeline/runner.py backend/app/api/runs.py backend/alembic/versions/ backend/tests/test_runner.py backend/tests/test_runs_api.py
git commit -m "feat(pipeline): add PipelineRun.pipeline_kind and PipelineRunner context_factory"
```

---

### Task 3: `content_base.py` + `ContentExtractor`

**Files:**
- Create: `backend/app/pipeline/content_base.py`, `backend/app/pipeline/content/__init__.py`, `backend/app/pipeline/content/extractor.py`
- Test: `backend/tests/test_content_extractor.py`

**Interfaces:**
- Consumes: `app.pipeline.base.Stage`, `app.github_client.GitHubClient`.
- Produces: `ContentTask` (dataclass: `kind: str, target: str, structured: bool, current: Any, source_material: dict[str, Any], candidates: list[Any], winner: Any, winner_reason: str | None, valid: bool`), `ContentPipelineContext` (dataclass: `repo: Repo, raw: dict, normalized: dict, tasks: list[ContentTask], errors: list[str]`) — both consumed by every later task in this plan. `ContentExtractor.__init__(self, gh_client: GitHubClient)`, populates `ctx.raw` with keys `repo, readme, topics, description, stars, missing_docs`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_content_extractor.py`:

```python
from unittest.mock import MagicMock

from app.models import Repo
from app.pipeline.content.extractor import ContentExtractor
from app.pipeline.content_base import ContentPipelineContext


def _fake_gh_client(missing: set[str] | None = None):
    missing = missing or set()
    gh = MagicMock()
    gh.get_repo.return_value = {
        "topics": ["cli", "python"],
        "description": "A tool",
        "stargazers_count": 42,
    }
    gh.get_readme.return_value = "# Hello"
    gh.has_file.side_effect = lambda owner, name, path: path not in missing
    return gh


def test_extractor_populates_raw_with_repo_material():
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    gh = _fake_gh_client()

    ctx = ContentExtractor(gh_client=gh).run(ctx)

    assert ctx.raw["readme"] == "# Hello"
    assert ctx.raw["topics"] == ["cli", "python"]
    assert ctx.raw["description"] == "A tool"
    assert ctx.raw["stars"] == 42
    assert ctx.raw["missing_docs"] == []


def test_extractor_detects_missing_standard_docs():
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    gh = _fake_gh_client(missing={"SECURITY.md", "CODE_OF_CONDUCT.md"})

    ctx = ContentExtractor(gh_client=gh).run(ctx)

    assert set(ctx.raw["missing_docs"]) == {"SECURITY.md", "CODE_OF_CONDUCT.md"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.content_base'`.

- [ ] **Step 3: Implement**

Create `backend/app/pipeline/content_base.py`:

```python
from dataclasses import dataclass, field
from typing import Any

from app.models import Repo


@dataclass
class ContentTask:
    kind: str            # "readme_suggestion" | "missing_doc_suggestion" | "topic_suggestion" | "seo_suggestion"
    target: str           # "readme" | "<filename>" | "topics" | "description"
    structured: bool      # False = free-text candidate; True = JSON candidate (topic/seo)
    current: Any          # existing value being improved (readme text, topics list, description str, or None)
    source_material: dict[str, Any] = field(default_factory=dict)
    candidates: list[Any] = field(default_factory=list)
    winner: Any = None
    winner_reason: str | None = None
    valid: bool = False


@dataclass
class ContentPipelineContext:
    repo: Repo
    raw: dict[str, Any] = field(default_factory=dict)
    tasks: list[ContentTask] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
```

Create `backend/app/pipeline/content/__init__.py` (empty file, matches `backend/app/pipeline/__init__.py`).

Create `backend/app/pipeline/content/extractor.py`:

```python
from app.github_client import GitHubClient
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext

# Beyond LICENSE/CONTRIBUTING.md (already checked by the analytics Extractor),
# these are the standard community-health files GitHub itself surfaces as
# "recommended community standards" — the natural next tier to auto-draft.
STANDARD_DOC_FILES = ["CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md"]


class ContentExtractor(Stage):
    name = "content_extractor"

    def __init__(self, gh_client: GitHubClient):
        self.gh_client = gh_client

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        owner, name = ctx.repo.owner, ctx.repo.name
        repo_data = self.gh_client.get_repo(owner, name)

        missing_docs = [f for f in STANDARD_DOC_FILES if not self.gh_client.has_file(owner, name, f)]

        ctx.raw = {
            "repo": repo_data,
            "readme": self.gh_client.get_readme(owner, name),
            "topics": repo_data.get("topics", []),
            "description": repo_data.get("description"),
            "stars": repo_data.get("stargazers_count", 0),
            "missing_docs": missing_docs,
        }
        return ctx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_extractor.py -v`
Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content_base.py backend/app/pipeline/content/ backend/tests/test_content_extractor.py
git commit -m "feat(content-pipeline): add ContentPipelineContext and ContentExtractor"
```

---

### Task 4: `ContentAnalyzer`

**Files:**
- Create: `backend/app/pipeline/content/analyzer.py`
- Test: `backend/tests/test_content_analyzer.py`

**Interfaces:**
- Consumes: `ContentPipelineContext`, `ContentTask` (Task 3).
- Produces: `ContentAnalyzer` (no `__init__`), populates `ctx.tasks: list[ContentTask]` — always one `readme_suggestion` and one `seo_suggestion` task; one `missing_doc_suggestion` task per entry in `ctx.raw["missing_docs"]`; one `topic_suggestion` task only if `len(ctx.raw["topics"]) < 5`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_content_analyzer.py`:

```python
from app.models import Repo
from app.pipeline.content.analyzer import ContentAnalyzer
from app.pipeline.content_base import ContentPipelineContext


def _ctx(**raw_overrides) -> ContentPipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.raw = {
        "readme": "# Hello",
        "topics": ["cli"],
        "description": "A tool",
        "missing_docs": ["SECURITY.md"],
    }
    ctx.raw.update(raw_overrides)
    return ctx


def test_analyzer_always_builds_readme_and_seo_tasks():
    ctx = ContentAnalyzer().run(_ctx())
    kinds = [t.kind for t in ctx.tasks]
    assert "readme_suggestion" in kinds
    assert "seo_suggestion" in kinds


def test_analyzer_builds_one_task_per_missing_doc():
    ctx = ContentAnalyzer().run(_ctx(missing_docs=["SECURITY.md", "CODE_OF_CONDUCT.md"]))
    doc_tasks = [t for t in ctx.tasks if t.kind == "missing_doc_suggestion"]
    assert {t.target for t in doc_tasks} == {"SECURITY.md", "CODE_OF_CONDUCT.md"}
    assert all(t.current is None and t.structured is False for t in doc_tasks)


def test_analyzer_skips_topic_task_when_already_well_tagged():
    ctx = ContentAnalyzer().run(_ctx(topics=["a", "b", "c", "d", "e"]))
    assert not any(t.kind == "topic_suggestion" for t in ctx.tasks)


def test_analyzer_builds_topic_task_when_under_tagged():
    ctx = ContentAnalyzer().run(_ctx(topics=["cli"]))
    topic_task = next(t for t in ctx.tasks if t.kind == "topic_suggestion")
    assert topic_task.current == ["cli"]
    assert topic_task.structured is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_analyzer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.content.analyzer'`.

- [ ] **Step 3: Implement**

Create `backend/app/pipeline/content/analyzer.py`:

```python
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext, ContentTask

_MIN_TOPICS = 5


class ContentAnalyzer(Stage):
    name = "content_analyzer"

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        raw = ctx.raw
        topics = raw.get("topics", [])
        tasks: list[ContentTask] = [
            ContentTask(
                kind="readme_suggestion",
                target="readme",
                structured=False,
                current=raw.get("readme"),
                source_material={"readme": raw.get("readme") or "", "topics": topics, "description": raw.get("description")},
            ),
        ]

        for filename in raw.get("missing_docs", []):
            tasks.append(ContentTask(
                kind="missing_doc_suggestion",
                target=filename,
                structured=False,
                current=None,
                source_material={"filename": filename, "readme": raw.get("readme") or ""},
            ))

        if len(topics) < _MIN_TOPICS:
            tasks.append(ContentTask(
                kind="topic_suggestion",
                target="topics",
                structured=True,
                current=topics,
                source_material={"topics": topics, "readme": raw.get("readme") or "", "description": raw.get("description")},
            ))

        tasks.append(ContentTask(
            kind="seo_suggestion",
            target="description",
            structured=True,
            current=raw.get("description"),
            source_material={"description": raw.get("description"), "readme": raw.get("readme") or "", "topics": topics},
        ))

        ctx.tasks = tasks
        return ctx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_analyzer.py -v`
Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content/analyzer.py backend/tests/test_content_analyzer.py
git commit -m "feat(content-pipeline): add ContentAnalyzer"
```

---

### Task 5: `ContentPreprocessor` + `ContentOptimizer`

**Files:**
- Create: `backend/app/pipeline/content/preprocessor.py`, `backend/app/pipeline/content/optimizer.py`
- Test: `backend/tests/test_content_preprocessor_optimizer.py`

**Interfaces:**
- Consumes: `ContentPipelineContext` (Task 3).
- Produces: `ContentPreprocessor` (no `__init__`) strips/truncates each task's `source_material["readme"]` to 6000 chars. `ContentOptimizer` (no `__init__`) further truncates to 4000 chars (token-budget trim, mirrors `Optimizer`'s simplicity). Both no-op on tasks without a `"readme"` key.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_content_preprocessor_optimizer.py`:

```python
from app.models import Repo
from app.pipeline.content.optimizer import ContentOptimizer
from app.pipeline.content.preprocessor import ContentPreprocessor
from app.pipeline.content_base import ContentPipelineContext, ContentTask


def _ctx_with_task(readme: str) -> ContentPipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [ContentTask(kind="readme_suggestion", target="readme", structured=False, current=readme, source_material={"readme": readme})]
    return ctx


def test_preprocessor_strips_whitespace_and_caps_length():
    ctx = _ctx_with_task("  \n# Hello  \n" + ("x" * 7000))
    ctx = ContentPreprocessor().run(ctx)
    readme = ctx.tasks[0].source_material["readme"]
    assert readme.startswith("# Hello")
    assert len(readme) <= 6000


def test_optimizer_caps_at_4000_chars():
    ctx = _ctx_with_task("y" * 10000)
    ctx = ContentPreprocessor().run(ctx)
    ctx = ContentOptimizer().run(ctx)
    assert len(ctx.tasks[0].source_material["readme"]) == 4000


def test_optimizer_noop_on_task_without_readme():
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [ContentTask(kind="missing_doc_suggestion", target="SECURITY.md", structured=False, current=None, source_material={"filename": "SECURITY.md"})]
    ctx = ContentOptimizer().run(ctx)
    assert "readme" not in ctx.tasks[0].source_material
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_preprocessor_optimizer.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `backend/app/pipeline/content/preprocessor.py`:

```python
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext

_MAX_README_CHARS = 6000


class ContentPreprocessor(Stage):
    name = "content_preprocessor"

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        for task in ctx.tasks:
            readme = task.source_material.get("readme")
            if readme:
                task.source_material["readme"] = readme.strip()[:_MAX_README_CHARS]
        return ctx
```

Create `backend/app/pipeline/content/optimizer.py`:

```python
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext

_MAX_SOURCE_CHARS = 4000


class ContentOptimizer(Stage):
    name = "content_optimizer"

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        for task in ctx.tasks:
            readme = task.source_material.get("readme")
            if readme and len(readme) > _MAX_SOURCE_CHARS:
                task.source_material["readme"] = readme[:_MAX_SOURCE_CHARS]
        return ctx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_preprocessor_optimizer.py -v`
Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content/preprocessor.py backend/app/pipeline/content/optimizer.py backend/tests/test_content_preprocessor_optimizer.py
git commit -m "feat(content-pipeline): add ContentPreprocessor and ContentOptimizer"
```

---

### Task 6: `ContentSynthesizer` (best-of-3 across providers)

**Files:**
- Create: `backend/app/pipeline/content/synthesizer.py`
- Test: `backend/tests/test_content_synthesizer.py`

**Interfaces:**
- Consumes: `ContentPipelineContext`, `ContentTask` (Task 3), `LLMRouter.chat_completion(messages, skip_providers=...)`, `LLMRouter.available_provider_names()` (Task 1).
- Produces: `ContentSynthesizer.__init__(self, llm_router: LLMRouter)`. For every task in `ctx.tasks`, appends up to 3 parsed candidates to `task.candidates` (raw text for `structured=False`, parsed+shape-checked JSON for `structured=True`); a candidate that fails to call or parse is simply omitted, never raises.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_content_synthesizer.py`:

```python
from unittest.mock import MagicMock

from app.models import Repo
from app.pipeline.content.synthesizer import ContentSynthesizer
from app.pipeline.content_base import ContentPipelineContext, ContentTask


def _ctx_with_task(task: ContentTask) -> ContentPipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [task]
    return ctx


def _fake_llm(responses: list[str]):
    llm = MagicMock()
    llm.available_provider_names.return_value = ["groq", "gemini", "openrouter"]
    llm.chat_completion.side_effect = responses
    return llm


def test_synthesizer_collects_three_free_text_candidates():
    task = ContentTask(kind="readme_suggestion", target="readme", structured=False, current="# Old", source_material={"readme": "# Old", "topics": [], "description": None})
    ctx = _ctx_with_task(task)
    llm = _fake_llm(["# New A", "# New B", "# New C"])

    ctx = ContentSynthesizer(llm_router=llm).run(ctx)

    assert ctx.tasks[0].candidates == ["# New A", "# New B", "# New C"]
    assert llm.chat_completion.call_count == 3
    skip_sets = [call.kwargs["skip_providers"] for call in llm.chat_completion.call_args_list]
    assert skip_sets == [set(), {"groq"}, {"groq", "gemini"}]


def test_synthesizer_parses_structured_topic_candidates():
    task = ContentTask(kind="topic_suggestion", target="topics", structured=True, current=["cli"], source_material={"topics": ["cli"], "readme": "", "description": None})
    ctx = _ctx_with_task(task)
    llm = _fake_llm(['["cli", "python", "automation"]', "not json", '["cli", "devtools"]'])

    ctx = ContentSynthesizer(llm_router=llm).run(ctx)

    assert ctx.tasks[0].candidates == [["cli", "python", "automation"], ["cli", "devtools"]]


def test_synthesizer_omits_candidate_on_call_failure():
    task = ContentTask(kind="readme_suggestion", target="readme", structured=False, current=None, source_material={"readme": "", "topics": [], "description": None})
    ctx = _ctx_with_task(task)
    llm = MagicMock()
    llm.available_provider_names.return_value = ["groq"]
    llm.chat_completion.side_effect = [RuntimeError("boom"), "# New B", RuntimeError("boom again")]

    ctx = ContentSynthesizer(llm_router=llm).run(ctx)

    assert ctx.tasks[0].candidates == ["# New B"]
    assert any("candidate call failed" in e for e in ctx.errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_synthesizer.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `backend/app/pipeline/content/synthesizer.py`:

```python
import json
from typing import Any

from app.llm_router import LLMRouter
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext, ContentTask

_KIND_PROMPTS = {
    "readme_suggestion": (
        "You are a technical writer improving a GitHub README. Given the current "
        "README, topics, and description below, write an improved full README in "
        "markdown. Respond with the improved README text only, no commentary.\n\n"
        "Current README:\n{readme}\n\nTopics: {topics}\nDescription: {description}"
    ),
    "missing_doc_suggestion": (
        "Write the full contents of {filename} for this GitHub repository, based on "
        "its README below. Respond with the file content only, no commentary.\n\n"
        "README:\n{readme}"
    ),
    "topic_suggestion": (
        "Suggest GitHub repository topics (lowercase, hyphenated, no '#') to improve "
        "discoverability. Respond with strict JSON only: a list of topic strings, 5-10 items.\n\n"
        "Current topics: {topics}\nDescription: {description}\nREADME:\n{readme}"
    ),
    "seo_suggestion": (
        'Write an SEO-friendly one-sentence repository description and 5-10 discovery '
        'keywords. Respond with strict JSON only: {{"description": "...", "keywords": ["...", "..."]}}.\n\n'
        "Current description: {description}\nTopics: {topics}\nREADME:\n{readme}"
    ),
}


class ContentSynthesizer(Stage):
    name = "content_synthesizer"

    def __init__(self, llm_router: LLMRouter):
        self.llm_router = llm_router

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        for task in ctx.tasks:
            self._generate_candidates(ctx, task)
        return ctx

    def _build_prompt(self, task: ContentTask) -> str:
        fields = {
            "readme": task.source_material.get("readme") or "",
            "topics": task.source_material.get("topics") or [],
            "description": task.source_material.get("description") or "",
            "filename": task.source_material.get("filename", ""),
        }
        return _KIND_PROMPTS[task.kind].format(**fields)

    def _generate_candidates(self, ctx: ContentPipelineContext, task: ContentTask) -> None:
        messages = [
            {"role": "system", "content": "You follow the requested output format exactly, with no extra commentary."},
            {"role": "user", "content": self._build_prompt(task)},
        ]
        provider_names = self.llm_router.available_provider_names()
        skip_progression = [set(), set(provider_names[:1]), set(provider_names[:2])]

        for skip in skip_progression:
            try:
                raw_response = self.llm_router.chat_completion(messages, skip_providers=skip)
            except Exception as exc:
                ctx.errors.append(f"content_synthesizer: candidate call failed for {task.kind}/{task.target}: {exc}")
                continue

            candidate = self._parse_candidate(task, raw_response)
            if candidate is not None:
                task.candidates.append(candidate)

    def _parse_candidate(self, task: ContentTask, raw_response: str) -> Any | None:
        if not task.structured:
            text = raw_response.strip()
            return text or None

        try:
            parsed = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError):
            return None

        if task.kind == "topic_suggestion":
            if isinstance(parsed, list) and parsed and all(isinstance(t, str) and t for t in parsed):
                return parsed
            return None

        if task.kind == "seo_suggestion":
            if (
                isinstance(parsed, dict)
                and isinstance(parsed.get("description"), str) and parsed["description"]
                and isinstance(parsed.get("keywords"), list) and parsed["keywords"]
                and all(isinstance(k, str) and k for k in parsed["keywords"])
            ):
                return {"description": parsed["description"], "keywords": parsed["keywords"]}
            return None

        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_synthesizer.py -v`
Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content/synthesizer.py backend/tests/test_content_synthesizer.py
git commit -m "feat(content-pipeline): add ContentSynthesizer with best-of-3 provider diversity"
```

---

### Task 7: `ContentValidator` (LLM-as-judge + kind-appropriate check)

**Files:**
- Create: `backend/app/pipeline/content/validator.py`
- Test: `backend/tests/test_content_validator.py`

**Interfaces:**
- Consumes: `ContentPipelineContext`, `ContentTask` (Task 3), `LLMRouter.chat_completion` (Task 1, no `skip_providers` needed for the single judge call).
- Produces: `ContentValidator.__init__(self, llm_router: LLMRouter)`. Sets `task.winner`, `task.winner_reason`, `task.valid` for every task with ≥1 candidate. Tasks with 0 candidates are left `valid=False` untouched.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_content_validator.py`:

```python
from unittest.mock import MagicMock

from app.models import Repo
from app.pipeline.content.validator import ContentValidator
from app.pipeline.content_base import ContentPipelineContext, ContentTask


def _ctx_with_task(task: ContentTask, raw: dict | None = None) -> ContentPipelineContext:
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    ctx.raw = raw or {}
    ctx.tasks = [task]
    return ctx


def test_validator_skips_task_with_no_candidates():
    task = ContentTask(kind="readme_suggestion", target="readme", structured=False, current=None, source_material={})
    ctx = _ctx_with_task(task)
    llm = MagicMock()

    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].valid is False
    llm.chat_completion.assert_not_called()


def test_validator_single_candidate_skips_judge_call():
    task = ContentTask(kind="readme_suggestion", target="readme", structured=False, current=None, source_material={}, candidates=["# Good README"])
    ctx = _ctx_with_task(task, raw={"stars": 5})

    llm = MagicMock()
    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].winner == "# Good README"
    assert ctx.tasks[0].valid is True
    llm.chat_completion.assert_not_called()


def test_validator_judges_multiple_free_text_candidates_and_checks_numbers():
    task = ContentTask(
        kind="readme_suggestion", target="readme", structured=False, current=None, source_material={},
        candidates=["This repo has 5 stars.", "This repo has 9999 stars!"],
    )
    ctx = _ctx_with_task(task, raw={"stars": 5})

    llm = MagicMock()
    llm.chat_completion.return_value = '{"best_index": 0, "reason": "accurate"}'
    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].winner == "This repo has 5 stars."
    assert ctx.tasks[0].winner_reason == "accurate"
    assert ctx.tasks[0].valid is True


def test_validator_rejects_winner_citing_unverified_numbers():
    task = ContentTask(
        kind="readme_suggestion", target="readme", structured=False, current=None, source_material={},
        candidates=["This repo has 5 stars.", "This repo has 9999 stars!"],
    )
    ctx = _ctx_with_task(task, raw={"stars": 5})

    llm = MagicMock()
    llm.chat_completion.return_value = '{"best_index": 1, "reason": "punchy"}'
    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].valid is False
    assert any("unverified numbers" in e for e in ctx.errors)


def test_validator_trusts_synthesizer_shape_check_for_structured_tasks():
    task = ContentTask(
        kind="topic_suggestion", target="topics", structured=True, current=["cli"], source_material={},
        candidates=[["cli", "python"], ["cli", "automation", "devtools"]],
    )
    ctx = _ctx_with_task(task)

    llm = MagicMock()
    llm.chat_completion.return_value = '{"best_index": 1, "reason": "broader coverage"}'
    ctx = ContentValidator(llm_router=llm).run(ctx)

    assert ctx.tasks[0].winner == ["cli", "automation", "devtools"]
    assert ctx.tasks[0].valid is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_validator.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `backend/app/pipeline/content/validator.py`:

```python
import json
import re

from app.llm_router import LLMRouter
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext, ContentTask


class ContentValidator(Stage):
    name = "content_validator"

    def __init__(self, llm_router: LLMRouter):
        self.llm_router = llm_router

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        known_numbers = self._known_numbers(ctx)

        for task in ctx.tasks:
            if not task.candidates:
                continue

            self._pick_winner(ctx, task)
            if task.winner is None:
                continue

            if task.structured:
                # Already shape-validated by ContentSynthesizer's _parse_candidate —
                # a topic/keyword list has no free-text number-hallucination risk.
                task.valid = True
            else:
                task.valid = self._numbers_ok(task.winner, known_numbers)
                if not task.valid:
                    ctx.errors.append(
                        f"content_validator: {task.kind}/{task.target} winner cites unverified numbers"
                    )

        return ctx

    def _pick_winner(self, ctx: ContentPipelineContext, task: ContentTask) -> None:
        if len(task.candidates) == 1:
            task.winner = task.candidates[0]
            task.winner_reason = "only candidate generated"
            return

        prompt = (
            f"You are judging {len(task.candidates)} candidate answers for a '{task.kind}' task. "
            "Pick the single best candidate. Respond with strict JSON only: "
            '{"best_index": <int>, "reason": "<one line>"}.\n\n'
            + "\n\n".join(f"Candidate {i}:\n{c}" for i, c in enumerate(task.candidates))
        )
        try:
            raw_response = self.llm_router.chat_completion([
                {"role": "system", "content": "Respond with strict JSON only."},
                {"role": "user", "content": prompt},
            ])
            verdict = json.loads(raw_response)
            best_index = verdict.get("best_index", -1)
            if not isinstance(best_index, int) or not (0 <= best_index < len(task.candidates)):
                return
            task.winner = task.candidates[best_index]
            task.winner_reason = verdict.get("reason")
        except Exception as exc:
            ctx.errors.append(f"content_validator: judge call failed for {task.kind}/{task.target}: {exc}")

    def _numbers_ok(self, candidate: str, known_numbers: set[int]) -> bool:
        cited = {int(n) for n in re.findall(r"\d+", candidate)}
        return cited.issubset(known_numbers)

    def _known_numbers(self, ctx: ContentPipelineContext) -> set[int]:
        return {value for value in ctx.raw.values() if isinstance(value, int)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_validator.py -v`
Expected: PASS (5/5).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content/validator.py backend/tests/test_content_validator.py
git commit -m "feat(content-pipeline): add ContentValidator with LLM-as-judge"
```

---

### Task 8: `ContentAssembler`

**Files:**
- Create: `backend/app/pipeline/content/assembler.py`
- Test: `backend/tests/test_content_assembler.py`

**Interfaces:**
- Consumes: `ContentPipelineContext`, `ContentTask` (Task 3), `app.models.Draft`.
- Produces: `ContentAssembler.__init__(self, db_session: Session)`. Writes one `Draft` row per `task.valid` task with the kind-specific `content` shape from the design spec (`readme_suggestion`/`topic_suggestion` → `{current, suggested, reason}`; `missing_doc_suggestion` → `{suggested, reason}`; `seo_suggestion` → `{current, suggested_description, keywords, reason}`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_content_assembler.py`:

```python
from app.db import SessionLocal
from app.models import Draft, Repo
from app.pipeline.content.assembler import ContentAssembler
from app.pipeline.content_base import ContentPipelineContext, ContentTask


def _db_and_repo(user_id: int):
    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=user_id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return db, repo


def test_assembler_writes_draft_per_valid_task(seed_user):
    db, repo = _db_and_repo(seed_user)
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [
        ContentTask(kind="readme_suggestion", target="readme", structured=False, current="# Old", winner="# New", winner_reason="clearer", valid=True),
        ContentTask(kind="missing_doc_suggestion", target="SECURITY.md", structured=False, current=None, winner="# Security Policy", winner_reason="standard template", valid=True),
        ContentTask(kind="topic_suggestion", target="topics", structured=True, current=["cli"], winner=["cli", "automation"], winner_reason="broader", valid=True),
        ContentTask(kind="seo_suggestion", target="description", structured=True, current="old desc", winner={"description": "new desc", "keywords": ["cli", "automation"]}, winner_reason="sharper", valid=True),
        ContentTask(kind="readme_suggestion", target="readme", structured=False, current="# Old", winner=None, winner_reason=None, valid=False),
    ]

    ctx = ContentAssembler(db_session=db).run(ctx)

    drafts = db.query(Draft).filter_by(repo_id=repo.id).all()
    assert len(drafts) == 4

    readme_draft = next(d for d in drafts if d.kind == "readme_suggestion")
    assert readme_draft.content == {"current": "# Old", "suggested": "# New", "reason": "clearer"}
    assert readme_draft.status == "pending"

    doc_draft = next(d for d in drafts if d.kind == "missing_doc_suggestion")
    assert doc_draft.target == "SECURITY.md"
    assert doc_draft.content == {"suggested": "# Security Policy", "reason": "standard template"}

    topic_draft = next(d for d in drafts if d.kind == "topic_suggestion")
    assert topic_draft.content == {"current": ["cli"], "suggested": ["cli", "automation"], "reason": "broader"}

    seo_draft = next(d for d in drafts if d.kind == "seo_suggestion")
    assert seo_draft.content == {"current": "old desc", "suggested_description": "new desc", "keywords": ["cli", "automation"], "reason": "sharper"}

    db.close()


def test_assembler_skips_invalid_tasks(seed_user):
    db, repo = _db_and_repo(seed_user)
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [ContentTask(kind="readme_suggestion", target="readme", structured=False, current=None, valid=False)]

    ctx = ContentAssembler(db_session=db).run(ctx)

    assert db.query(Draft).filter_by(repo_id=repo.id).count() == 0
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_assembler.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `backend/app/pipeline/content/assembler.py`:

```python
from sqlalchemy.orm import Session

from app.models import Draft
from app.pipeline.base import Stage
from app.pipeline.content_base import ContentPipelineContext, ContentTask


class ContentAssembler(Stage):
    name = "content_assembler"

    def __init__(self, db_session: Session):
        self.db = db_session

    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        for task in ctx.tasks:
            if not task.valid:
                continue
            self.db.add(Draft(
                user_id=ctx.repo.user_id,
                repo_id=ctx.repo.id,
                kind=task.kind,
                target=task.target,
                content=self._content_for(task),
                status="pending",
            ))
        self.db.commit()
        return ctx

    def _content_for(self, task: ContentTask) -> dict:
        if task.kind == "seo_suggestion":
            return {
                "current": task.current,
                "suggested_description": task.winner["description"],
                "keywords": task.winner["keywords"],
                "reason": task.winner_reason,
            }
        if task.kind == "missing_doc_suggestion":
            return {"suggested": task.winner, "reason": task.winner_reason}
        return {"current": task.current, "suggested": task.winner, "reason": task.winner_reason}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_assembler.py -v`
Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content/assembler.py backend/tests/test_content_assembler.py
git commit -m "feat(content-pipeline): add ContentAssembler writing kind-specific Draft rows"
```

---

### Task 9: `content_jobs.py` + scheduler wiring

**Files:**
- Create: `backend/app/pipeline/content_jobs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_content_jobs.py`

**Interfaces:**
- Consumes: every stage from Tasks 3-8, `PipelineRunner` (Task 2), `app.github_client.GitHubClient`/`GitHubAuthError`, `app.token_crypto.decrypt_token`, `app.events.broadcaster`.
- Produces: `build_content_stages(db: Session, gh_client: GitHubClient, llm_router: LLMRouter) -> list`, `run_content_pipeline_for_all_repos(db: Session, user_id: int | None = None) -> None` (publishes SSE `drafts_generated` per processed user, same circuit-breaker pattern as `run_pipeline_for_all_repos`). `main.py` gains a second staggered daily APScheduler job.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_content_jobs.py`:

```python
from unittest.mock import MagicMock, patch

from app.db import SessionLocal
from app.models import Draft, PipelineRun, Repo, User
from app.pipeline.content_jobs import run_content_pipeline_for_all_repos


def _fake_gh_client():
    gh = MagicMock()
    gh.get_repo.return_value = {"topics": ["cli"], "description": "A tool", "stargazers_count": 10}
    gh.get_readme.return_value = "# Hello"
    gh.has_file.return_value = True  # no missing docs, keeps this test focused
    return gh


def _fake_llm_router():
    llm = MagicMock()
    llm.available_provider_names.return_value = ["groq"]
    llm.chat_completion.return_value = "# Improved README"
    return llm


@patch("app.pipeline.content_jobs.broadcaster.publish")
@patch("app.pipeline.content_jobs.GitHubClient")
@patch("app.pipeline.content_jobs.LLMRouter")
def test_runs_content_pipeline_and_publishes_per_user(mock_llm_cls, mock_gh_cls, mock_publish, seed_user):
    mock_gh_cls.return_value = _fake_gh_client()
    mock_llm_cls.return_value = _fake_llm_router()

    db = SessionLocal()
    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    run_content_pipeline_for_all_repos(db, user_id=seed_user)

    run_row = db.query(PipelineRun).filter_by(pipeline_kind="content").first()
    assert run_row is not None

    drafts = db.query(Draft).filter_by(repo_id=repo.id).all()
    assert len(drafts) >= 1  # at least the readme_suggestion task

    mock_publish.assert_called_once_with("drafts_generated", {}, user_id=seed_user)
    db.close()


@patch("app.pipeline.content_jobs.broadcaster.publish")
def test_skips_repos_for_user_with_undecryptable_token(mock_publish, seed_user):
    db = SessionLocal()
    user = db.get(User, seed_user)
    user.access_token_encrypted = "not-valid-fernet-ciphertext"
    db.commit()

    repo = Repo(owner="octocat", name="hello-world", user_id=seed_user)
    db.add(repo)
    db.commit()

    run_content_pipeline_for_all_repos(db, user_id=seed_user)

    assert db.query(Draft).count() == 0
    mock_publish.assert_not_called()
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.content_jobs'`.

- [ ] **Step 3: Implement**

Create `backend/app/pipeline/content_jobs.py`:

```python
from sqlalchemy.orm import Session

from app.config import get_settings
from app.events import broadcaster
from app.github_client import GitHubClient
from app.llm_router import LLMRouter
from app.models import Repo, User
from app.pipeline.content.analyzer import ContentAnalyzer
from app.pipeline.content.assembler import ContentAssembler
from app.pipeline.content.extractor import ContentExtractor
from app.pipeline.content.optimizer import ContentOptimizer
from app.pipeline.content.preprocessor import ContentPreprocessor
from app.pipeline.content.synthesizer import ContentSynthesizer
from app.pipeline.content.validator import ContentValidator
from app.pipeline.content_base import ContentPipelineContext
from app.pipeline.runner import PipelineRunner
from app.token_crypto import decrypt_token


def build_content_stages(db: Session, gh_client: GitHubClient, llm_router: LLMRouter) -> list:
    return [
        ContentExtractor(gh_client=gh_client),
        ContentAnalyzer(),
        ContentPreprocessor(),
        ContentOptimizer(),
        ContentSynthesizer(llm_router=llm_router),
        ContentValidator(llm_router=llm_router),
        ContentAssembler(db_session=db),
    ]


def run_content_pipeline_for_all_repos(db: Session, user_id: int | None = None) -> None:
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

        try:
            owner = db.get(User, repo.user_id)
            gh_client = GitHubClient(token=decrypt_token(owner.access_token_encrypted))
        except Exception:
            # Same rationale as app.pipeline.jobs.run_pipeline_for_all_repos: owner
            # lookup / token decryption happens outside PipelineRunner's own
            # per-stage exception isolation, so it must be caught here explicitly.
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
```

In `backend/app/main.py`, add the second scheduled job. Replace the imports/scheduler block:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.rate_limit import limiter
from app.api.events import router as events_router
from app.api.repos import router as repos_router
from app.api.insights import router as insights_router
from app.api.recommendations import router as recommendations_router
from app.api.drafts import router as drafts_router
from app.api.runs import router as runs_router
from app.api.providers import router as providers_router
from app.api.users import router as users_router
from app.db import SessionLocal
from app.pipeline.jobs import run_pipeline_for_all_repos
from app.pipeline.content_jobs import run_content_pipeline_for_all_repos

settings = get_settings()

scheduler = BackgroundScheduler()


def _scheduled_pipeline_run() -> None:
    db = SessionLocal()
    try:
        run_pipeline_for_all_repos(db)
    finally:
        db.close()


def _scheduled_content_pipeline_run() -> None:
    db = SessionLocal()
    try:
        run_content_pipeline_for_all_repos(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler.add_job(_scheduled_pipeline_run, "interval", hours=24, id="daily_pipeline_run")
    # Offset 12h from the analytics job's default first-run time so the two
    # daily jobs don't both fire at once and contend for the same LLM
    # provider rate-limit windows.
    scheduler.add_job(
        _scheduled_content_pipeline_run,
        "interval",
        hours=24,
        id="daily_content_pipeline_run",
        next_run_time=datetime.now() + timedelta(hours=12),
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
```

(The rest of `main.py` — `app = FastAPI(...)`, middleware, router includes, `/api/health` — is unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_jobs.py -v`
Expected: PASS (2/2). Then run the full suite: `cd backend && .venv/bin/python -m pytest -v` — must stay 100% green (confirms `main.py`'s import/scheduler change didn't break app startup, exercised by every test that imports `app.main`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content_jobs.py backend/app/main.py backend/tests/test_content_jobs.py
git commit -m "feat(content-pipeline): wire content_jobs and staggered daily scheduler"
```

---

### Task 10: `POST /runs/content` endpoint

**Files:**
- Modify: `backend/app/api/runs.py`
- Test: `backend/tests/test_runs_api.py`

**Interfaces:**
- Consumes: `app.pipeline.content_jobs.run_content_pipeline_for_all_repos` (Task 9), existing `TriggerRunOut`, `limiter`, `require_user`.
- Produces: `POST /runs/content` — 202, rate-limited `"10/minute"`, `BackgroundTasks`-driven, mirrors `POST /runs` exactly.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_runs_api.py`:

```python
def test_trigger_content_run_returns_immediately_and_scopes_to_caller(client):
    client.post("/repos", json={"owner": "octocat", "name": "hello-world"})

    with patch("app.pipeline.content_jobs.run_content_pipeline_for_all_repos") as mock_run:
        resp = client.post("/runs/content")

    assert resp.status_code == 202
    assert resp.json() == {"status": "started"}
    assert mock_run.call_count == 1
    assert mock_run.call_args.kwargs["user_id"] == client.test_user_id


def test_trigger_content_run_requires_user_token(client_without_user_token):
    resp = client_without_user_token.post("/runs/content")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_runs_api.py -v`
Expected: FAIL — `404 Not Found` for `POST /runs/content` (route doesn't exist yet).

- [ ] **Step 3: Implement**

In `backend/app/api/runs.py`, add below the existing `trigger_run`/`_run_pipeline_background` pair:

```python
@router.post("/content", response_model=TriggerRunOut, status_code=202)
@limiter.limit("10/minute")
def trigger_content_run(
    request: Request, background_tasks: BackgroundTasks, current_user: User = Depends(require_user)
) -> TriggerRunOut:
    background_tasks.add_task(_run_content_pipeline_background, current_user.id)
    return TriggerRunOut(status="started")


def _run_content_pipeline_background(user_id: int) -> None:
    from app.pipeline.content_jobs import run_content_pipeline_for_all_repos

    db = SessionLocal()
    try:
        run_content_pipeline_for_all_repos(db, user_id=user_id)
    finally:
        db.close()
```

Place this directly after `trigger_run`/`_run_pipeline_background`, before `list_run_stages`, matching the file's existing top-to-bottom ordering (`GET /`, `POST /`, then path-parameterized routes). No route-collision risk here: `/runs/content` (one segment) and `/runs/{run_id}/stages` (two segments, second literal `stages`) never match the same request regardless of declaration order.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_runs_api.py -v`
Expected: PASS. Then run the full suite: `cd backend && .venv/bin/python -m pytest -v` — must stay 100% green. Also run `cd backend && .venv/bin/pip-audit` — must stay clean (no new dependency was added, so this is a regression check only).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/runs.py backend/tests/test_runs_api.py
git commit -m "feat(api): add POST /runs/content to trigger content generation"
```

---

### Task 11: Frontend types — OpenAPI regen, `types/drafts.ts`, `api.ts`, route handler

**Files:**
- Modify: `frontend/types/api.d.ts` (regenerated), `frontend/lib/api-types.ts`, `frontend/lib/api.ts`
- Create: `frontend/types/drafts.ts`, `frontend/app/api/runs/content/route.ts`

**Interfaces:**
- Consumes: the now-live `POST /runs/content` (Task 10) and `PipelineRunOut.pipeline_kind` (Task 2).
- Produces: `DraftKind` union + `ReadmeSuggestionContent`/`MissingDocSuggestionContent`/`TopicSuggestionContent`/`SeoSuggestionContent` interfaces (consumed by Task 13's `DraftContent`), `api.triggerContentRun(): Promise<{status: string}>` (consumed by Task 12's `useTriggerContentRun`).

- [ ] **Step 1: Regenerate OpenAPI types**

Start the backend dev server in one terminal (`cd backend && .venv/bin/uvicorn app.main:app --reload`), then in another:

```bash
cd frontend && npm run generate:types
```

Verify `frontend/types/api.d.ts`'s `PipelineRunOut` schema now includes `pipeline_kind: string` (`grep -A6 '"PipelineRunOut"' frontend/types/api.d.ts`). Stop the backend dev server.

- [ ] **Step 2: Create the hand-written per-kind content types**

Create `frontend/types/drafts.ts`:

```typescript
// Draft.content is stored as an untyped JSON column on the backend (app/models.py),
// so its per-kind shape can't be expressed in the generated OpenAPI schema — these
// mirror app/pipeline/content/assembler.py's ContentAssembler._content_for exactly.

export interface ReadmeSuggestionContent {
  current: string | null;
  suggested: string;
  reason: string | null;
}

export interface MissingDocSuggestionContent {
  suggested: string;
  reason: string | null;
}

export interface TopicSuggestionContent {
  current: string[];
  suggested: string[];
  reason: string | null;
}

export interface SeoSuggestionContent {
  current: string | null;
  suggested_description: string;
  keywords: string[];
  reason: string | null;
}

export type DraftKind =
  | "readme_suggestion"
  | "missing_doc_suggestion"
  | "topic_suggestion"
  | "seo_suggestion";
```

- [ ] **Step 3: Add the frontend API client method and Route Handler**

In `frontend/lib/api.ts`, add below `listRunStages`:

```typescript
  triggerContentRun: () => backendFetch<{ status: string }>("/runs/content", { method: "POST" }),
```

Create `frontend/app/api/runs/content/route.ts`:

```typescript
import { api } from "@/lib/api";
import { proxyRoute } from "@/lib/route-handler";

export async function POST() {
  return proxyRoute(() => api.triggerContentRun(), 202);
}
```

- [ ] **Step 4: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/types/api.d.ts frontend/types/drafts.ts frontend/lib/api.ts frontend/app/api/runs/content/route.ts
git commit -m "feat(frontend): regenerate OpenAPI types, add per-kind Draft content types and triggerContentRun"
```

---

### Task 12: `useTriggerContentRun` + `drafts_generated` SSE mapping

**Files:**
- Modify: `frontend/hooks/use-drafts.ts`, `frontend/hooks/use-live-events.ts`
- Test: `frontend/tests/use-live-events.test.tsx`

**Interfaces:**
- Consumes: `api.triggerContentRun` (Task 11), `queryKeys.runs.all`/`queryKeys.drafts.all` (existing).
- Produces: `useTriggerContentRun()` mutation hook (consumed by Task 14's `drafts-client.tsx`). `EVENT_QUERY_MAP["drafts_generated"] = [queryKeys.drafts.all]`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/use-live-events.test.tsx` (inside the existing `describe("useLiveEvents")` block, after the `draft_updated` test):

```tsx
  it("invalidates the drafts query when a drafts_generated event arrives", () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    render(
      <QueryClientProvider client={queryClient}>
        <Harness />
      </QueryClientProvider>,
    );

    const source = FakeEventSource.instances[0];
    source.emit("drafts_generated", {});

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.drafts.all });
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/use-live-events.test.tsx`
Expected: FAIL — `invalidateSpy` never called (no `drafts_generated` handler registered, event type not in `EVENT_QUERY_MAP`).

- [ ] **Step 3: Implement**

In `frontend/hooks/use-live-events.ts`, add to `EVENT_QUERY_MAP`:

```typescript
const EVENT_QUERY_MAP: Record<string, QueryKey[]> = {
  repo_added: [queryKeys.repos.all],
  repo_removed: [queryKeys.repos.all],
  recommendation_updated: [queryKeys.recommendations.all],
  run_completed: [queryKeys.runs.all, queryKeys.repos.all, queryKeys.recommendations.all],
  draft_updated: [queryKeys.drafts.all],
  drafts_generated: [queryKeys.drafts.all, queryKeys.runs.all],
};
```

In `frontend/hooks/use-drafts.ts`, add below `useReviewDraft`:

```typescript
export function useTriggerContentRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => fetchJson<{ status: string }>("/api/runs/content", { method: "POST" }),
    onSuccess: () => {
      // The triggered run itself (not its eventual drafts) is visible immediately;
      // the drafts_generated SSE event above invalidates queryKeys.drafts.all once
      // the background pipeline actually finishes and writes rows.
      queryClient.invalidateQueries({ queryKey: queryKeys.runs.all });
    },
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/use-live-events.test.tsx`
Expected: PASS (5/5). Then `cd frontend && npx vitest run` (full suite) and `npx tsc --noEmit` — both clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/hooks/use-drafts.ts frontend/hooks/use-live-events.ts frontend/tests/use-live-events.test.tsx
git commit -m "feat(frontend): add useTriggerContentRun and drafts_generated SSE invalidation"
```

---

### Task 13: `Chip` UI primitive + `DraftContent` component

**Files:**
- Create: `frontend/components/ui/chip.tsx`, `frontend/components/drafts/draft-content.tsx`
- Test: `frontend/tests/draft-content.test.tsx`

**Interfaces:**
- Consumes: `frontend/types/drafts.ts` (Task 11).
- Produces: `Chip({children}): JSX.Element` (reusable rounded-pill label, for any future tag/keyword list — not draft-specific). `DraftContent({kind, content}: {kind: string; content: unknown}): JSX.Element` (consumed by Task 14's `drafts-client.tsx`).

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/draft-content.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DraftContent } from "@/components/drafts/draft-content";

describe("DraftContent", () => {
  it("renders current/suggested panels for readme_suggestion", () => {
    render(<DraftContent kind="readme_suggestion" content={{ current: "# Old", suggested: "# New", reason: "clearer" }} />);
    expect(screen.getByText("# Old")).toBeInTheDocument();
    expect(screen.getByText("# New")).toBeInTheDocument();
  });

  it("renders a chip per suggested topic for topic_suggestion", () => {
    render(<DraftContent kind="topic_suggestion" content={{ current: ["cli"], suggested: ["cli", "automation"], reason: "broader" }} />);
    expect(screen.getByText("cli")).toBeInTheDocument();
    expect(screen.getByText("automation")).toBeInTheDocument();
  });

  it("renders description and keyword chips for seo_suggestion", () => {
    render(<DraftContent kind="seo_suggestion" content={{ current: null, suggested_description: "A great tool.", keywords: ["cli", "automation"], reason: "sharper" }} />);
    expect(screen.getByText("A great tool.")).toBeInTheDocument();
    expect(screen.getByText("cli")).toBeInTheDocument();
  });

  it("renders suggested text for missing_doc_suggestion", () => {
    render(<DraftContent kind="missing_doc_suggestion" content={{ suggested: "# Security Policy", reason: "standard template" }} />);
    expect(screen.getByText("# Security Policy")).toBeInTheDocument();
  });

  it("falls back to JSON.stringify for an unrecognized kind", () => {
    render(<DraftContent kind="future_kind" content={{ anything: 1 }} />);
    expect(screen.getByText('{"anything":1}')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/draft-content.test.tsx`
Expected: FAIL — `Cannot find module '@/components/drafts/draft-content'`.

- [ ] **Step 3: Implement**

Create `frontend/components/ui/chip.tsx`:

```tsx
import type { ReactNode } from "react";

export function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground ring-1 ring-foreground/10">
      {children}
    </span>
  );
}
```

Create `frontend/components/drafts/draft-content.tsx`:

```tsx
import type {
  MissingDocSuggestionContent,
  ReadmeSuggestionContent,
  SeoSuggestionContent,
  TopicSuggestionContent,
} from "@/types/drafts";
import { Chip } from "@/components/ui/chip";

function isReadmeSuggestion(c: unknown): c is ReadmeSuggestionContent {
  return typeof c === "object" && c !== null && typeof (c as ReadmeSuggestionContent).suggested === "string" && "current" in c;
}

function isMissingDocSuggestion(c: unknown): c is MissingDocSuggestionContent {
  return typeof c === "object" && c !== null && typeof (c as MissingDocSuggestionContent).suggested === "string" && !("current" in c);
}

function isTopicSuggestion(c: unknown): c is TopicSuggestionContent {
  return typeof c === "object" && c !== null && Array.isArray((c as TopicSuggestionContent).suggested) && Array.isArray((c as TopicSuggestionContent).current);
}

function isSeoSuggestion(c: unknown): c is SeoSuggestionContent {
  return typeof c === "object" && c !== null && typeof (c as SeoSuggestionContent).suggested_description === "string";
}

export function DraftContent({ kind, content }: { kind: string; content: unknown }) {
  if (kind === "readme_suggestion" && isReadmeSuggestion(content)) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Current</p>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-xs">
            {content.current ?? "(no README yet)"}
          </pre>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Suggested</p>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-xs">{content.suggested}</pre>
        </div>
      </div>
    );
  }

  if (kind === "missing_doc_suggestion" && isMissingDocSuggestion(content)) {
    return (
      <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-xs">{content.suggested}</pre>
    );
  }

  if (kind === "topic_suggestion" && isTopicSuggestion(content)) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {content.suggested.map((topic) => (
          <Chip key={topic}>{topic}</Chip>
        ))}
      </div>
    );
  }

  if (kind === "seo_suggestion" && isSeoSuggestion(content)) {
    return (
      <div className="space-y-1.5 text-sm">
        <p>{content.suggested_description}</p>
        <div className="flex flex-wrap gap-1.5">
          {content.keywords.map((keyword) => (
            <Chip key={keyword}>{keyword}</Chip>
          ))}
        </div>
      </div>
    );
  }

  return <p className="text-sm text-muted-foreground">{JSON.stringify(content)}</p>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/draft-content.test.tsx`
Expected: PASS (5/5). Then `npx tsc --noEmit` and `npx eslint .` — both clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/chip.tsx frontend/components/drafts/draft-content.tsx frontend/tests/draft-content.test.tsx
git commit -m "feat(frontend): add Chip primitive and per-kind DraftContent renderer"
```

---

### Task 14: Wire `DraftContent` + "Generate drafts" button + Pipeline Runs `pipeline_kind` badge

**Files:**
- Modify: `frontend/components/drafts/drafts-client.tsx`, `frontend/components/runs/run-row.tsx`

**Interfaces:**
- Consumes: `DraftContent` (Task 13), `useTriggerContentRun` (Task 12), `PipelineRun.pipeline_kind` (Task 11).
- Produces: final user-visible seam — the Drafts inbox renders real content and can trigger generation; the Pipeline Runs page distinguishes analytics vs. content runs.

- [ ] **Step 1: Update `drafts-client.tsx`**

In `frontend/components/drafts/drafts-client.tsx`, replace the imports and the header/content rendering:

```tsx
"use client";

import { CheckCircle2, Inbox, Sparkles, X } from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeading } from "@/components/ui/section-heading";
import { DraftContent } from "@/components/drafts/draft-content";
import { useDrafts, useReviewDraft, useTriggerContentRun } from "@/hooks/use-drafts";
import { useRepos } from "@/hooks/use-repos";

export function DraftsClient() {
  const { data: drafts } = useDrafts();
  const { data: repos } = useRepos();
  const review = useReviewDraft();
  const triggerContentRun = useTriggerContentRun();

  const repoNameById = useMemo(() => {
    const map = new Map<number, string>();
    repos?.forEach((r) => map.set(r.id, `${r.owner}/${r.name}`));
    return map;
  }, [repos]);

  const pending = drafts?.filter((d) => d.status === "pending");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SectionHeading icon={Inbox} title="Drafts" subtitle="Review before anything goes out" iconColor="text-emerald-500" />
        <Button
          onClick={() =>
            triggerContentRun.mutate(undefined, {
              onSuccess: () => toast.success("Content generation started"),
              onError: () => toast.error("Could not start content generation"),
            })
          }
          disabled={triggerContentRun.isPending}
        >
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          {triggerContentRun.isPending ? "Generating..." : "Generate drafts"}
        </Button>
      </div>

      {pending && pending.length === 0 ? (
        <EmptyState icon={Inbox} title="No drafts yet" description="Click 'Generate drafts' or wait for the daily schedule." />
      ) : (
        <div className="space-y-2">
          {pending?.map((draft) => (
            <Card key={draft.id}>
              <CardContent className="flex items-start justify-between gap-4 py-4">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-muted-foreground">
                    {draft.repo_id !== null ? repoNameById.get(draft.repo_id) ?? `repo #${draft.repo_id}` : "Account-level"}
                    {" · "}
                    {draft.kind}
                  </p>
                  <div className="mt-1">
                    <DraftContent kind={draft.kind} content={draft.content} />
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Approve draft"
                    onClick={() =>
                      review.mutate(
                        { id: draft.id, status: "approved" },
                        { onError: () => toast.error("Could not approve — try again.") },
                      )
                    }
                    disabled={review.isPending}
                  >
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Reject draft"
                    onClick={() =>
                      review.mutate(
                        { id: draft.id, status: "rejected" },
                        { onError: () => toast.error("Could not reject — try again.") },
                      )
                    }
                    disabled={review.isPending}
                  >
                    <X className="h-4 w-4 text-red-500" aria-hidden="true" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Update `run-row.tsx`**

In `frontend/components/runs/run-row.tsx`, add the `pipeline_kind` badge next to the run title:

```tsx
"use client";

import { AlertTriangle, BarChart3, CheckCircle2, ChevronDown, ChevronRight, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunStages } from "@/hooks/use-run-stages";
import type { PipelineRun } from "@/lib/api-types";

const STATUS_META = {
  ok: { icon: CheckCircle2, color: "text-emerald-500", label: "OK" },
  degraded: { icon: AlertTriangle, color: "text-amber-500", label: "Degraded" },
  running: { icon: Loader2, color: "text-sky-500", label: "Running" },
} as const;

const KIND_META = {
  analytics: { icon: BarChart3, color: "text-sky-500", label: "Analytics" },
  content: { icon: Sparkles, color: "text-fuchsia-500", label: "Content" },
} as const;

export function RunRow({ run }: { run: PipelineRun }) {
  const [expanded, setExpanded] = useState(false);
  const { data: stages, isPending } = useRunStages(run.id, expanded);
  const meta = STATUS_META[run.status as keyof typeof STATUS_META] ?? STATUS_META.running;
  const StatusIcon = meta.icon;
  const kindMeta = KIND_META[run.pipeline_kind as keyof typeof KIND_META] ?? KIND_META.analytics;
  const KindIcon = kindMeta.icon;

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
            <span className={`flex items-center gap-1 text-xs ${kindMeta.color}`}>
              <KindIcon className="h-3.5 w-3.5" aria-hidden="true" />
              {kindMeta.label}
            </span>
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

- [ ] **Step 3: Verify no regressions**

Run: `cd frontend && npx tsc --noEmit && npx eslint . && npx vitest run && npm run build`
Expected: all four clean/pass.

- [ ] **Step 4: Manual smoke test**

Start both dev servers (`cd backend && .venv/bin/uvicorn app.main:app --reload`, `cd frontend && npm run dev`), sign in, navigate to `/drafts`, click "Generate drafts", confirm the button shows "Generating...", then (once the background job finishes — check `/runs` for a "Content" badge) confirm new draft cards appear in `/drafts` **without a page refresh** (SSE-driven), with README panels/topic chips/description rendering correctly per kind, and confirm the same tab and any second open tab both update.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/drafts/drafts-client.tsx frontend/components/runs/run-row.tsx
git commit -m "feat(frontend): wire DraftContent, Generate drafts button, and run pipeline_kind badge"
```

---

## Final Verification

After all 14 tasks:

- Backend: `cd backend && .venv/bin/python -m pytest -v` (full suite, expect 100+ tests, 100% pass, no warnings), `.venv/bin/pip-audit` (clean).
- Frontend: `cd frontend && npx tsc --noEmit && npx eslint . && npx vitest run && npm run build` (all clean).
- Manual: the Task 14 Step 4 smoke test, plus confirm the existing analytics pipeline (`/runs`, "Run now" button) still works unaffected.
- Dead code: confirm no leftover debug `print`/`console.log` statements were introduced across the 14 tasks.
