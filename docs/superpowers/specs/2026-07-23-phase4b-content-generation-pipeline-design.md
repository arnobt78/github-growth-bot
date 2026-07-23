# Phase 4B: Content Generation Pipeline — Design Spec

**Status:** Approved by Product Owner (Arnob Mahmud), 2026-07-23. Governing decisions confirmed via `AskUserQuestion`: all 4 content kinds in this sub-project, N=3 best-of-N sequential across providers, `pipeline_kind` column added to `PipelineRun`, LLM-as-judge Validator, plain before/after text panels for README (no diff library) — plus a Product Owner follow-up requesting the daily-automatic scheduling option in addition to manual trigger ("add as much as dynamic automatic... daily basis features... as much as u can implement").

## Goal

Turn the Phase 4A `Draft` inbox from an empty pipe into a real producer: a second `Stage`/`PipelineRunner` pipeline template that generates README improvement suggestions, missing-standard-doc suggestions, topic/tag recommendations, and SEO-description suggestions — landing every one as a `Draft` row, reviewed by the existing approve/reject inbox, nothing ever posted externally without human approval (unchanged from 4A).

## Architecture

### New pipeline context (`backend/app/pipeline/content_base.py`)

The existing `PipelineContext` (`backend/app/pipeline/base.py`) is analytics-flavored — `recommendations`, `narrative`, `ranked_findings` don't fit content generation. A second, parallel dataclass, same `Stage` contract (`Stage.run(ctx) -> ctx` is already generic, reused as-is):

```python
@dataclass
class ContentTask:
    kind: str            # "readme_suggestion" | "missing_doc_suggestion" | "topic_suggestion" | "seo_suggestion"
    target: str          # "readme" | "<filename>" | "topics" | "description"
    structured: bool      # False = free-text candidate (readme/missing_doc); True = JSON candidate (topic/seo)
    current: Any          # the existing value being improved on (readme text, topics list, description str, or None for a missing file)
    source_material: dict[str, Any]   # whatever this task's Synthesizer prompt needs
    candidates: list[Any] = field(default_factory=list)   # list[str] if not structured, list[dict|list] if structured
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

(No `normalized` field — unlike the analytics pipeline, nothing in this pipeline needs a separate normalized-metrics view; every stage reads/writes `ctx.raw` and `ctx.tasks` directly. Adding an unused field here would be exactly the kind of dead code this project's standing instructions ask to avoid.)

### Stages (`backend/app/pipeline/content/*.py`), same 7-stage order as Phase 1

| Stage | File | Responsibility |
| --- | --- | --- |
| `ContentExtractor` | `content/extractor.py` | `GitHubClient.get_repo` (description, topics), `get_readme`, `has_file` for `CONTRIBUTING.md`/`CODE_OF_CONDUCT.md`/`SECURITY.md` (independent of the analytics pipeline's own extraction — no coupling to `Snapshot` freshness). Populates `ctx.raw`. |
| `ContentAnalyzer` | `content/analyzer.py` | Decides which of the 4 kinds need a task this run: always `readme_suggestion` + `seo_suggestion`; one `missing_doc_suggestion` task per missing standard file; `topic_suggestion` only if `len(topics) < 5`. Builds `ctx.tasks`, setting each task's `structured` flag and `current` value (README text / topics list / description str / `None` for a missing file). |
| `ContentPreprocessor` | `content/preprocessor.py` | Cleans/truncates each task's `source_material` text (strip markdown noise from README, cap length). |
| `ContentOptimizer` | `content/optimizer.py` | Trims each task's `source_material` to a token budget (character-count heuristic, matching `Optimizer`'s simplicity). |
| `ContentSynthesizer` | `content/synthesizer.py` | Per task: 3 `LLMRouter.chat_completion` calls, each forced onto a different provider via new `skip_providers` param (see below) — candidate 1 no skip, candidate 2 skips the provider candidate 1 used, candidate 3 skips both prior providers. Non-`structured` tasks (readme/missing_doc) keep the raw text response as a candidate. `structured` tasks (topic/seo) `json.loads` the response — a candidate that fails to parse as the expected shape (list for topics, dict for seo) is simply omitted, same graceful-degrade pattern as the existing `Synthesizer`. Any candidate call that raises is likewise omitted; if zero candidates survive, the task is dropped. |
| `ContentValidator` | `content/validator.py` | Per task with ≥1 candidate: one extra `chat_completion` call — judge prompt embeds all candidates, asks for the best index + one-line reason (or "REJECT" if all are poor). The winner then passes a kind-appropriate check before `task.valid = True`: non-`structured` winners go through the existing deterministic number-cross-check pattern from `validator.py` (stated numbers must exist in `ctx.raw`/`ctx.normalized`); `structured` winners are checked for shape only (topic list is non-empty strings; seo dict has a non-empty `description` and non-empty `keywords` list) — there's no free-text number-hallucination risk in a topic/keyword list. |
| `ContentAssembler` | `content/assembler.py` | For each valid task, inserts one `Draft` row (`user_id`, `repo_id`, `kind=task.kind`, `target=task.target`, `status="pending"`) with a **kind-specific `content` shape** (see "Draft kinds & content shapes" below — never a uniform `{suggestion, reason}` blob, since the frontend renders each kind differently). Publishes SSE `drafts_generated` per repo processed (not per draft — avoids an SSE flood when several tasks land at once). |

### Draft kinds & content shapes

| Kind | `target` | `content` shape |
| --- | --- | --- |
| `readme_suggestion` | `"readme"` | `{"current": str, "suggested": str, "reason": str}` |
| `missing_doc_suggestion` | `"<filename>"` (e.g. `"SECURITY.md"`) | `{"suggested": str, "reason": str}` (no `current` — the file doesn't exist) |
| `topic_suggestion` | `"topics"` | `{"current": list[str], "suggested": list[str], "reason": str}` |
| `seo_suggestion` | `"description"` | `{"current": str \| None, "suggested_description": str, "keywords": list[str], "reason": str}` |

### LLMRouter change (`backend/app/llm_router.py`)

```python
def chat_completion(self, messages: list[dict[str, str]], skip_providers: set[str] | None = None) -> str:
```

`skip_providers` (default `None`, fully backward-compatible with every existing call site) filters `self._providers()` before the fallback loop runs — same iteration logic otherwise. This is the only change to existing pipeline code; Phase 1's `Synthesizer` keeps calling `chat_completion(messages)` unchanged.

### `PipelineRun.pipeline_kind` column

New migration adds `pipeline_kind: Mapped[str] = mapped_column(String(50), default="analytics")` to `PipelineRun` (`backend/app/models.py`). Existing rows backfill to `"analytics"` (matches current behavior — nothing else has ever written this table). `PipelineRunOut` (`backend/app/api/runs.py`) gains `pipeline_kind: str` so the frontend Pipeline Runs page can label each run.

### New backend job wiring (`backend/app/pipeline/content_jobs.py`, mirrors `jobs.py`)

```python
def build_content_stages(db: Session, gh_client: GitHubClient, llm_router: LLMRouter) -> list[Stage]: ...
def run_content_pipeline_for_all_repos(db: Session, user_id: int | None = None) -> None: ...
```

Same per-user circuit breaker pattern as `run_pipeline_for_all_repos` (skip `user_id`s with `needs_reauth`/decrypt failures), same `PipelineRunner` reuse via its new `context_factory`/`pipeline_kind` params (constructs `PipelineRun` with `pipeline_kind="content"`), same SSE publish-per-user-processed pattern at the end (event `drafts_generated`, empty payload `{}` — matches `run_completed`'s existing per-user-not-per-repo shape, since a user's drafts across all their repos are invalidated by one query-key refetch either way).

### New API endpoint (`backend/app/api/runs.py`, or a small addition — reuses the router)

```python
@router.post("/content", response_model=TriggerRunOut, status_code=202)
@limiter.limit("10/minute")
def trigger_content_run(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(require_user)) -> TriggerRunOut:
```

Mirrors `POST /runs` exactly (same rate limit, same `BackgroundTasks` pattern, same response shape) — path `POST /runs/content` keeps ad-blocker-safe naming (no `analytics`/`metrics`/etc.) and groups with the existing runs router rather than inventing a new top-level path.

### Scheduler (`backend/app/main.py`)

Both a manual trigger (above) **and** a second daily APScheduler job, per the Product Owner's explicit request for daily-automatic operation:

```python
def _scheduled_content_pipeline_run() -> None:
    db = SessionLocal()
    try:
        run_content_pipeline_for_all_repos(db)
    finally:
        db.close()
```

Added inside `lifespan` with an explicit `next_run_time` offset by 12 hours from the analytics job's first run (both jobs otherwise default to firing at the same moment 24h after process start — a real provider-rate-limit contention risk flagged in the audit) — staggers the two daily jobs half a day apart.

## Frontend

- **`frontend/components/drafts/draft-content.tsx`** (new) — dispatches rendering by `draft.kind`: `readme_suggestion` → two stacked read-only text panels ("Current" / "Suggested", plain text, existing `Card`/`ScrollArea` primitives, no new dependency); `topic_suggestion` → `Badge` chip list; `missing_doc_suggestion`/`seo_suggestion` → simple label/value rows. Unrecognized `kind` falls back to today's `JSON.stringify`. `content` is typed per-kind via a hand-written discriminated union in `frontend/types/drafts.ts` (new file) since the backend's `content: dict` can't express this at the OpenAPI level — runtime-narrowed by `draft.kind`, never assumed.
- **`drafts-client.tsx`** — swaps the raw `JSON.stringify(draft.content)` line for `<DraftContent kind={draft.kind} content={draft.content} />`. Everything else in this file (approve/reject mutations, repo-name lookup) is unchanged.
- **"Generate drafts" button** — added to the Drafts page (`frontend/components/drafts/drafts-client.tsx` header region), calls a new `POST /api/runs/content` Route Handler (thin proxy, mirrors `frontend/app/api/runs/route.ts`'s existing pattern) via a new `useTriggerContentRun()` mutation hook in `use-drafts.ts`. On success, no manual cache poke needed — the eventual `drafts_generated` SSE event drives the real refresh (matches the existing "trigger returns 202 immediately, SSE delivers the actual update" pattern from `POST /runs`).
- **SSE mapping** — `frontend/hooks/use-live-events.ts`'s `EVENT_QUERY_MAP` gains `drafts_generated: [queryKeys.drafts.all]` (new pending drafts appear instantly in every open tab, no refresh — same mechanism as every other CRUD invalidation in this codebase).
- **Pipeline Runs page** — `PipelineRunOut.pipeline_kind` rendered as a small badge (`"Analytics"` / `"Content"`) next to each run row, using the existing icon+color convention (no new component needed, extend the existing run-row renderer).

## Testing

- Backend: TDD per stage (`backend/tests/test_content_pipeline_stages.py` — one test class per stage, mocking `GitHubClient`/`LLMRouter` at the same boundaries the existing `test_analyzer_optimizer.py`/`test_synthesizer_validator.py` do), `test_content_jobs.py` (circuit breaker + SSE publish, mirroring `test_runner.py`/existing `jobs.py` test conventions), `test_runs_api.py` extended for the new `POST /runs/content` endpoint and `pipeline_kind` field. `test_llm_router.py` extended for `skip_providers`.
- Frontend: `use-drafts.test.tsx` extended for `useTriggerContentRun`, `use-live-events.test.tsx` extended for `drafts_generated`, a new `draft-content.test.tsx` for the per-kind render dispatch (including the unrecognized-kind fallback).
- Full regression: backend `pytest -v` (currently 76/76), frontend `tsc`/`eslint`/`vitest`/`next build` all clean, per this project's standing regression baseline (`TEST_SPEC.md`).

## Global Constraints (carried into every implementation task)

- Every new endpoint requires `dependencies=[Depends(require_api_key)]` + `require_user` scoping, per-user filtering at the query layer (404 not 403 on cross-user access).
- No endpoint path contains `analytics`/`analysis`/`tracking`/`performance`/`metrics`.
- Every CRUD/generation action invalidates the relevant TanStack Query key everywhere via SSE — no page refresh, current tab and all other open tabs.
- SSR data-fetching stays in `page.tsx`; only genuinely interactive code in `"use client"` components.
- Every new frontend type comes from the generated OpenAPI schema where the shape is expressible there; hand-written types only for the per-kind `content` discriminated union that the backend's `dict` column can't express.
- No artificial engagement, ever (REQ-0000/POL-0001) — unaffected by this sub-project, noted for completeness since Assembler writes are the closest thing to "posting" in this codebase and must stay draft-only.
- Comments explain WHY, never WHAT. No unrequested summary `.md` files.
