<!-- Revision: C1 -->
# Requirements — GitHub Growth Bot (Phase 1: Repo Health & Analytics)

Source of truth: `docs/superpowers/specs/2026-07-20-github-growth-bot-design.md` (approved by Product Owner during brainstorming, 2026-07-20). This document retroactively assigns REQ-IDs to that approved spec so the work already completed (backend, C1) and the work remaining (frontend, C1 continuation) are both traceable.

Status tags per `agile-v-lifecycle`: `approved [C1]` (accepted, not yet built), `implemented [C1]` (built + unit/task-reviewed), `verified [C1]` (passed final whole-branch review + tests).

---

## Non-Goal (binding constraint, all REQs)

**REQ-0000 — No artificial engagement.** The system MUST NEVER auto-star, auto-fork, auto-follow, or otherwise artificially inflate any GitHub metric, on this account or any other, via automation, bot accounts, or paid services. This is a hard boundary, not a feature to trade off. Violates GitHub Acceptable Use Policies.
**Status:** verified [C1] — `GitHubClient` (`backend/app/github_client.py`) exposes read-only methods only (`get_*`, `has_file`, `search_similar_repos`); no write/star/fork/follow method exists anywhere in the codebase. Confirmed by final whole-branch review (2026-07-20).

---

## Backend Requirements (C1 — Implemented & Verified)

**REQ-0001 — Multi-agent analytics pipeline.** A 7-stage pipeline (Extractor → Preprocessor → Analyzer → Optimizer → Synthesizer → Validator → Assembler) processes each tracked repo daily, with each stage isolated so one stage's failure never crashes the run or loses data already gathered by earlier stages.
**Status:** verified [C1]. Artifacts: `backend/app/pipeline/{base,extractor,preprocessor,analyzer,optimizer,synthesizer,validator,assembler,runner}.py`. Tests: `test_extractor_preprocessor.py`, `test_analyzer_optimizer.py`, `test_synthesizer_validator.py`, `test_runner.py`, `test_pipeline_integration.py`.

**REQ-0002 — GitHub data extraction.** Pull repo metadata, stars/forks/watchers/open-issues, 14-day traffic (views/clones + uniques), referrers, popular content paths, README content, presence of LICENSE/CONTRIBUTING, and benchmark repos (similar by language+topic) via the GitHub REST API.
**Status:** verified [C1]. Artifacts: `backend/app/github_client.py`, `backend/app/pipeline/extractor.py`. Test: `test_github_client.py` (6 tests).

**REQ-0003 — Historical snapshot tracking.** Each daily run diffs against the prior day's snapshot (stars/forks delta) and persists a permanent record, since GitHub's traffic API is a rolling 14-day window.
**Status:** verified [C1]. Artifacts: `backend/app/pipeline/preprocessor.py`, `backend/app/models.py::Snapshot`.

**REQ-0004 — Multi-provider LLM fallback router.** Application-internal router calling Groq → Gemini → OpenRouter (`:free`) → Hugging Face → Cloudflare Workers AI → Vercel AI Gateway in order, retrying sibling models within a provider before moving to the next provider, tracking daily per-provider usage to proactively avoid rate limits. Groq model allowlist restricted to `openai/gpt-oss-120b` / `qwen/qwen3.6-27b` / `openai/gpt-oss-20b` (deprecated `llama-3.1-8b-instant` / `llama-3.3-70b-versatile` forbidden, per Product Owner's existing `docs/LLM_MODEL_SELECTION.md` convention).
**Status:** verified [C1]. Artifact: `backend/app/llm_router.py`. Test: `test_llm_router.py` (4 tests). **Note:** original implementation only retried sibling models on 429/5xx; task review (2026-07-20) found this defeated the purpose of the 3-model Groq list on non-HTTP failures (timeouts, 400-class "model unavailable") — fixed to retry on any exception. See DECISION_LOG.

**REQ-0005 — Hallucination-guarding Validator stage.** Every LLM-synthesized recommendation must have its cited numbers cross-checked against real source data before being persisted; unverified claims are dropped, not shown to the user.
**Status:** verified [C1]. Artifacts: `backend/app/pipeline/synthesizer.py`, `backend/app/pipeline/validator.py`. Test: `test_synthesizer_validator.py` (5 tests).

**REQ-0006 — REST + SSE API, ad-blocker-safe naming.** Endpoint paths must never contain `analytics`/`analysis`/`tracking`/`performance`/`metrics` (common ad-blocker/extension URL filter triggers) — use `insights`/`snapshots`/`benchmarks`/`runs` instead.
**Status:** verified [C1]. Artifacts: `backend/app/api/{repos,insights,recommendations,runs,providers,events}.py`. Confirmed keyword-free by task review and final review.

**REQ-0007 — API-key authentication.** Every endpoint except `GET /api/health` requires `Authorization: Bearer <API_KEY>`.
**Status:** verified [C1]. Artifact: `backend/app/deps.py::require_api_key`. Confirmed applied to every router by final whole-branch review.

**REQ-0008 — Daily automated pipeline trigger + real-time UI push.** An in-process scheduler runs the full pipeline for all tracked repos every 24 hours; an SSE event stream (`GET /events`) pushes CRUD-triggered updates (recommendation dismissed, repo added/removed, run completed) to connected clients for instant UI invalidation without polling or page refresh.
**Status:** verified [C1]. Artifacts: `backend/app/events.py`, `backend/app/api/events.py`, `backend/app/main.py` (APScheduler wiring). Test: `test_events.py`.

**REQ-0009 — Deployment: Coolify/Docker on existing Hetzner VPS.** Single non-root Docker container (`python:3.12-slim`), Postgres as a separate Coolify-managed service (not bundled), subdomain of `arnobmahmud.com` via existing Traefik/Caddy pattern, secrets only in Coolify env.
**Status:** approved [C1], **not yet deployed** — Dockerfile/`.dockerignore` built and reviewed (`backend/Dockerfile`); actual VPS deployment (DNS record, Coolify app creation, Traefik labels, Postgres provisioning, `alembic upgrade head`) is a manual operational step not yet executed. Tracked as open item.

---

## Frontend Requirements (C1 — Implemented)

**REQ-0010 — Next.js App Router dashboard.** Overview page (tracked repos, sparklines, delta badges), repo detail page (trend charts, benchmark comparison, referrers, recommendations), recommendations inbox, pipeline runs history, settings. SSR data-fetching directly in `page.tsx`; only genuinely interactive code in `use client` components.
**Status:** verified [C1] — final whole-branch review clean, `tsc`/`eslint`/`next build` clean, no `loading.tsx` anywhere. Primary artifacts: `frontend/app/page.tsx`, `frontend/app/repos/[id]/page.tsx`, `frontend/app/recommendations/page.tsx`, `frontend/app/runs/page.tsx`, `frontend/app/settings/page.tsx`, `frontend/components/overview/`, `frontend/components/repo-detail/`, `frontend/components/recommendations/`, `frontend/components/runs/`, `frontend/components/settings/`.

**REQ-0011 — Instant UI updates, no refresh, on any CRUD action.** TanStack Query mutations + SSE-driven cache invalidation update the current tab and all other open tabs immediately (dismiss recommendation, add/remove repo, manual run trigger) — consuming REQ-0008's `/events` stream. Shell (headers/labels/icons/buttons/cards) renders instantly; only data-bearing regions show inline pulse-skeletons, no `loading.tsx`. Independent server prefetches run in parallel (`Promise.all`), not sequential.
**Status:** verified [C1] — post-plan audit (2026-07-21) confirmed every mutation (`useAddRepo`/`useDeleteRepo`/`useDismissRecommendation`/`useTriggerRun`) pairs `onError` + `disabled={…isPending}` at every call site, all 5 `page.tsx` use `force-dynamic` + parallel prefetch/`setQueryData` (no silent-failing `prefetchQuery` left on primary data), and the SSE map invalidates all 3 affected query families (`repos`, `runs`, `recommendations`) on `run_completed`. Primary artifacts: `frontend/hooks/use-repos.ts`, `frontend/hooks/use-recommendations.ts`, `frontend/hooks/use-runs.ts`, `frontend/hooks/use-live-events.ts`, `frontend/providers/live-events-provider.tsx`, `frontend/providers/query-provider.tsx`, `frontend/app/api/events/route.ts`. Verified end-to-end in Task 20's manual pass: dismissing a recommendation in one browser tab instantly cleared it from a second tab's repo-detail view via SSE-driven cache invalidation, with no reload.

**REQ-0012 — Shared, reusable, strictly-typed UI layer.** `lib/`/`hooks/`/`providers/`/`types/`/`components/ui/` structure; types generated from the backend's OpenAPI schema (no hand-duplicated interfaces); shadcn/ui + Tailwind consistent theme (light/dark); every title/label/button carries a meaningful `lucide-react` icon with semantic color tied to the data it represents. `SafeImage` pattern (`docs/SAFE_IMAGE_REUSABLE_COMPONENT.md`) reused for GitHub avatars.
**Status:** verified [C1] — post-plan audit (2026-07-21) confirmed zero orphaned files across `components/`, `hooks/`, `lib/`, `providers/`; `benchmark-table.tsx`/`referrers-table.tsx`/`popular-paths-table.tsx` reviewed for redundancy and found to be appropriately-scoped domain components already built on shared primitives, not duplication. Primary artifacts: `frontend/lib/` (`api.ts`, `api-types.ts`, `backend-client.ts`, `fetch-json.ts`, `query-keys.ts`, `route-handler.ts`, `utils.ts`), `frontend/hooks/`, `frontend/providers/`, `frontend/types/api.d.ts` (generated from backend OpenAPI schema), `frontend/components/ui/`, `frontend/components/safe-image.tsx`. Dark/light legibility spot-checked across all 5 pages in Task 20's manual pass.

**REQ-0013 — API-key isolation from the browser.** Browser never holds the backend's static API key; Next.js Route Handlers attach it server-side and proxy all backend calls.
**Status:** verified [C1]. Primary artifacts: `frontend/lib/backend-client.ts` (server-only, attaches `BACKEND_API_KEY`), `frontend/lib/route-handler.ts` (`proxyRoute` wrapper), `frontend/app/api/**/route.ts`. **Open item resolved:** the "revisit if the dashboard's threat model changes" note is now acted on — REQ-0015–REQ-0019 (below) add real per-user GitHub OAuth on top of this static-key layer, since the threat model changed from "single personal dashboard" to "multi-tenant SaaS." The static API key remains one layer of the resulting defense-in-depth chain, not replaced by it.

**REQ-0014 — Vercel deployment with production guardrails.** Bot protection + AI-bot blocking ON, security headers in `next.config.ts` mirrored in `vercel.json`, `/_next/static/` immutable cache, single-source `robots.ts` disallowing all crawling (`disallow: "/"` — personal tool, no SEO value), per `docs/VERCEL_PRODUCTION_GUARDRAILS.md`.
**Status:** implemented [C1] (guardrail configuration only — actual Vercel deployment/production Gate 2 still pending, see STATE.md and the Task 20 post-plan note below). Primary artifacts: `frontend/next.config.ts`, `frontend/vercel.json`, `frontend/app/robots.ts`.

---

## Multi-Tenant SaaS Foundation Requirements (C1, Phase 2 — Implemented)

Source of truth: `docs/superpowers/specs/2026-07-21-multi-tenant-saas-design.md`. This turns the app from single-tenant (one shared static API key, one global repo list) into a real multi-tenant SaaS — anyone signs in with their own GitHub account and tracks their own repos, fully isolated from every other user's data.

**REQ-0015 — GitHub OAuth authentication, public-repo scope only.** Auth.js (NextAuth) v5, GitHub provider, `read:user public_repo` scope (no `repo` — no private-repo access in this phase), JWT session strategy (no database adapter — Next.js still never touches Postgres directly). `proxy.ts` (this Next.js version's renamed `middleware.ts`) protects every page, redirecting unauthenticated visitors to a dedicated `/sign-in` page.
**Status:** verified [C1]. Primary artifacts: `frontend/auth.ts`, `frontend/proxy.ts`, `frontend/app/api/auth/[...nextauth]/route.ts`, `frontend/app/sign-in/page.tsx`, `frontend/types/next-auth.d.ts`. Live end-to-end sign-in verification (real GitHub OAuth App) is a separate open item — see STATE.md.

**REQ-0016 — Per-user data isolation on every table.** New `User` table (`github_id`, encrypted OAuth token, `plan`/`max_tracked_repos` for future billing readiness); every existing table (`Repo`, `Snapshot`, `BenchmarkRepo`, `Referrer`, `PopularPath`, `Recommendation`, `PipelineRun`, `StageRun`) gains a `user_id` FK. Fetching another user's resource by id returns 404, never 403 (no existence leak). `LLMUsage` (shared app-wide LLM budget) and `StageRun.pipeline_run_id`'s FK (no cascade, a prior deliberate decision) are the two intentional exceptions to "every table gets scoped."
**Status:** verified [C1]. Primary artifacts: `backend/app/models.py`, `backend/alembic/versions/9bb84cb18218_*.py` + `2d5539f16118_*.py` (two-phase nullable→backfill→not-null migration), `backend/scripts/backfill_owner_user.py`.

**REQ-0017 — Defense-in-depth request authorization.** Every authenticated request: Auth.js session (frontend) → short-lived (60s) HMAC-signed internal token (`X-Internal-User-Token`, minted server-side from the verified session, never by the browser) → existing `require_api_key` (unchanged) → new `require_user` (verifies the token, loads the `User`) → every query filtered by that `user_id`. GitHub OAuth tokens encrypted at rest (Fernet), never logged, never returned by any API response.
**Status:** verified [C1]. Primary artifacts: `backend/app/internal_auth.py`, `backend/app/token_crypto.py`, `backend/app/deps.py::require_user`, `backend/app/api/users.py`, `frontend/lib/internal-auth.ts`, `frontend/lib/backend-client.ts` (auto-attaches the token to every existing `api.ts` call — zero changes needed to any of the 13 pre-existing Route Handlers or SSR `page.tsx` call sites).

**REQ-0018 — Per-user pipeline execution.** Each pipeline run authenticates to GitHub as the repo's owning user (own OAuth token, own 5,000/hr rate-limit budget instead of one shared budget). A user's expired/revoked token stops only that user's remaining repos for the rest of the run (circuit breaker via `GitHubAuthError`/`ctx.errors`, without touching the protected `PipelineRunner`/`Stage` exception-isolation contract). Manual run triggers (`POST /runs`) return immediately (202) via FastAPI `BackgroundTasks` instead of blocking the request on the actual run. SSE (`/events`) delivery is scoped per-user — a user's live-update stream only ever receives their own events.
**Status:** verified [C1]. Primary artifacts: `backend/app/pipeline/jobs.py`, `backend/app/github_client.py` (`GitHubAuthError`, benchmark-search TTL cache), `backend/app/api/runs.py`, `backend/app/events.py`, `backend/app/api/events.py`, `frontend/app/api/events/route.ts`, `frontend/hooks/use-live-events.ts`.

**REQ-0019 — Rate limiting on state-mutating endpoints.** `slowapi`, keyed by the verified `github_id` when available (falls back to remote IP) — never by the internal token itself, which rotates every request. Applied to `POST /repos`, `DELETE /repos/{id}`, `POST /runs`.
**Status:** verified [C1]. Primary artifacts: `backend/app/rate_limit.py`, `backend/app/api/repos.py`, `backend/app/api/runs.py`.

---

## Phase 4A: Automation Engine Core Requirements (C1, Phase 4A — Implemented)

Source of truth: `docs/superpowers/specs/2026-07-22-phase4a-automation-engine-core-design.md`. First sub-project of the Phase 4 roadmap (`docs/PROJECT_PLAN.md`) — ships the draft-and-approve infrastructure every later Phase 4 sub-project (4B–4G) writes into. Deliberately plumbing-only: no content producer exists yet, so the dashboard inbox legitimately shows its empty state until 4B lands.

**REQ-0020 — `Draft` model, per-user REST API, and real-time inbox.** New `Draft` table (`user_id`, nullable `repo_id`, `kind`/`target`/`status` as plain strings, `content` as JSON, `reviewed_at`), scoped and isolated exactly like every other per-user resource (404 not 403 on cross-user access). `GET /drafts` + `PATCH /drafts/{id}` (`status: "approved" | "rejected"`, one-way transition — 409 on an already-reviewed draft, 422 on an invalid status value). New SSE event `draft_updated` reuses the existing `EventBroadcaster` unchanged. Frontend mirrors the Recommendations page/hook/component trio byte-for-byte, including a new `Drafts` nav entry (`Inbox` icon, `text-emerald-500`).
**Status:** verified [C1]. Primary artifacts: `backend/app/models.py::Draft`, `backend/alembic/versions/a2eaa148e044_*.py`, `backend/app/api/drafts.py`, `backend/tests/test_drafts_api.py`, `frontend/lib/api-types.ts`/`api.ts`/`query-keys.ts`, `frontend/hooks/use-drafts.ts`, `frontend/hooks/use-live-events.ts`, `frontend/app/api/drafts/**`, `frontend/app/drafts/page.tsx`, `frontend/components/drafts/drafts-client.tsx`, `frontend/components/nav-sidebar.tsx`. Built via a 3-task subagent-driven plan (`docs/superpowers/plans/2026-07-22-phase4a-automation-engine-core.md`), each task independently reviewed (one fix round on Task 1 — brief's own test/reference-code contradiction on the 409 response shape, resolved by keeping the codebase-wide `{detail}` error convention), final whole-branch review clean (opus, 0 Critical/Important, 3 Minor forward-looking notes for 4B). Backend 76/76 tests, `pip-audit` clean. Frontend `tsc`/`eslint`/`vitest` (9/9)/`next build` all clean.

---

## Phase 4B: Content Generation Pipeline Requirements (C1, Phase 4B — Implemented)

Source of truth: `docs/superpowers/specs/2026-07-23-phase4b-content-generation-pipeline-design.md`. Second sub-project of the Phase 4 roadmap — the first real producer writing into the `Draft` inbox REQ-0020 built.

**REQ-0021 — Content generation pipeline (README/missing-doc/topic/SEO suggestions).** A second `Stage`/`PipelineRunner` pipeline (`backend/app/pipeline/content/*.py`: `ContentExtractor` → `ContentAnalyzer` → `ContentPreprocessor` → `ContentOptimizer` → `ContentSynthesizer` → `ContentValidator` → `ContentAssembler`), sharing the analytics pipeline's `Stage` contract via a new `ContentPipelineContext`/`ContentTask` pair (`backend/app/pipeline/content_base.py`). Best-of-3 candidate generation per task (`LLMRouter.chat_completion`'s new `skip_providers` param forces each candidate onto a different provider), an LLM-as-judge `ContentValidator` picking the winner, a kind-appropriate validity check (deterministic metric-claim number-check for free-text kinds, shape-check already done upstream for structured kinds). Writes one `Draft` row per valid task with a kind-specific `content` shape (`readme_suggestion`/`topic_suggestion`: `{current, suggested, reason}`; `missing_doc_suggestion`: `{suggested, reason}`; `seo_suggestion`: `{current, suggested_description, keywords, reason}`). New `PipelineRun.pipeline_kind` column (default `"analytics"`) distinguishes the two pipelines in the API/UI. Triggered both manually (`POST /runs/content`, mirrors `POST /runs`) and via a second daily APScheduler job staggered 12h from the analytics job. Frontend: `DraftContent` renders each kind's real content (before/after README panels, topic/keyword chips) in place of the 4A placeholder `JSON.stringify`; a "Generate drafts" button on the Drafts page; `drafts_generated` SSE event drives instant cross-tab inbox refresh; Pipeline Runs page shows an Analytics/Content badge per run.
**Status:** verified [C1]. Primary artifacts: `backend/app/pipeline/content_base.py`, `backend/app/pipeline/content/{extractor,analyzer,preprocessor,optimizer,synthesizer,validator,assembler}.py`, `backend/app/pipeline/content_jobs.py`, `backend/app/llm_router.py` (`skip_providers`/`available_provider_names`), `backend/app/pipeline/runner.py` (`context_factory`/`pipeline_kind`), `backend/app/models.py::PipelineRun.pipeline_kind`, `backend/alembic/versions/*_add_pipeline_kind_to_pipeline_runs.py`, `backend/app/api/runs.py` (`POST /runs/content`), `frontend/types/drafts.ts`, `frontend/components/drafts/{draft-content,drafts-client}.tsx`, `frontend/components/ui/chip.tsx`, `frontend/components/runs/run-row.tsx`, `frontend/hooks/{use-drafts,use-live-events}.ts`. Built via a 14-task subagent-driven plan (`docs/superpowers/plans/2026-07-23-phase4b-content-generation-pipeline.md`), 4 tasks required a fix round each (a vacuous test, an unguarded KeyError path + missing judge-failure test coverage, an incomplete SSE-invalidation assertion — all task-scoped and closed), final whole-branch review (opus) found one real Important production bug — the Validator's number cross-check checked every digit in a generated document against the single known integer (`stars`), which would have silently rejected nearly all `readme_suggestion`/`missing_doc_suggestion` drafts — fixed by scoping the check to metric-claim numbers only (`"N stars"`-shaped patterns), plus 3 Minor polish fixes, all independently re-reviewed clean. Backend 111/111 tests, `pip-audit` clean. Frontend `tsc`/`eslint`/`vitest` (15/15)/`next build` all clean. A post-build independent deep audit (2 fresh subagents, backend + frontend, no shared context) then found and closed 4 more gaps before Gate 2: `ContentValidator._known_numbers` only scanned top-level `ctx.raw` ints, missing `forks_count`/`watchers_count`/`open_issues_count` nested under `ctx.raw["repo"]`, wrongly rejecting candidates citing real repo stats; `DraftContent` declared but never rendered each kind's `reason` field; `topic_suggestion`/`seo_suggestion`'s `current` value (populated by the backend) was never shown, unlike `readme_suggestion`'s before/after panels; `DraftKind` was declared but unused, giving `DRAFT_KIND_LABELS` no compile-time exhaustiveness check. All 4 fixed with new regression tests, independently re-verified clean by a fresh subagent. Backend 112/112 tests, frontend `tsc`/`eslint`/`vitest`(16/16)/`build` all clean.

**Remaining:** a live manual browser smoke test (sign in, click "Generate drafts", confirm real drafts render and instantly propagate via SSE) requires the Product Owner's participation — deliberately not attempted by any automated agent.

---

## Deferred to Later Cycles (explicitly out of C1 scope)

Per the approved design spec, the remaining feature groups from the user's original request are deferred and will be opened as new cycles (C2+) with their own REQ sets when picked up: issue/discussion auto-response (4F); release-notes automation + demo GIF/video generation (4C/4G); community & trend discovery (4D — similar-repo contribution opportunities, forum recommendations); notifications & alerting (4E).

## Traceability Index

| REQ | Sub-scope | Status | Primary Artifacts |
|---|---|---|---|
| REQ-0000 | Constraint | verified [C1] | github_client.py |
| REQ-0001 | Backend | verified [C1] | pipeline/*.py |
| REQ-0002 | Backend | verified [C1] | github_client.py, extractor.py |
| REQ-0003 | Backend | verified [C1] | preprocessor.py, models.py |
| REQ-0004 | Backend | verified [C1] | llm_router.py |
| REQ-0005 | Backend | verified [C1] | synthesizer.py, validator.py |
| REQ-0006 | Backend | verified [C1] | api/*.py |
| REQ-0007 | Backend | verified [C1] | deps.py |
| REQ-0008 | Backend | verified [C1] | events.py, main.py |
| REQ-0009 | Backend | approved [C1] | Dockerfile (deploy pending) |
| REQ-0010 | Frontend | verified [C1] | frontend/app/*, frontend/components/{overview,repo-detail,recommendations,runs,settings}/ |
| REQ-0011 | Frontend | verified [C1] | frontend/hooks/*, frontend/providers/*, frontend/app/api/events/route.ts |
| REQ-0012 | Frontend | verified [C1] | frontend/lib/*, frontend/hooks/*, frontend/providers/*, frontend/types/api.d.ts, frontend/components/ui/* |
| REQ-0013 | Frontend | verified [C1] | frontend/lib/backend-client.ts, frontend/lib/route-handler.ts, frontend/app/api/**/route.ts |
| REQ-0014 | Frontend | implemented [C1] | frontend/next.config.ts, frontend/vercel.json, frontend/app/robots.ts (Vercel deploy pending) |
| REQ-0015 | Multi-tenant | verified [C1] | frontend/auth.ts, frontend/proxy.ts, frontend/app/sign-in/* (live OAuth E2E confirmed 2026-07-22) |
| REQ-0016 | Multi-tenant | verified [C1] | backend/app/models.py, alembic/versions/{9bb84cb18218,2d5539f16118}, scripts/backfill_owner_user.py |
| REQ-0017 | Multi-tenant | verified [C1] | backend/app/{internal_auth,token_crypto,deps}.py, frontend/lib/{internal-auth,backend-client}.ts |
| REQ-0018 | Multi-tenant | verified [C1] | backend/app/pipeline/jobs.py, backend/app/{github_client,events}.py, backend/app/api/{runs,events}.py |
| REQ-0019 | Multi-tenant | verified [C1] | backend/app/rate_limit.py, backend/app/api/{repos,runs}.py |
| REQ-0020 | Phase 4A | verified [C1] | backend/app/models.py::Draft, backend/app/api/drafts.py, frontend/hooks/use-drafts.ts, frontend/components/drafts/* |
| REQ-0021 | Phase 4B | verified [C1] | backend/app/pipeline/content/*.py, backend/app/pipeline/content_jobs.py, backend/app/llm_router.py, frontend/types/drafts.ts, frontend/components/drafts/draft-content.tsx |

**Frontend sub-scope Gate 2:** Approved (`GATE-0002`, 2026-07-21) — REQ-0010–REQ-0013 verified; REQ-0014's guardrail *code* is verified but actual Vercel deployment remains a separate, still-open action gated by POL-0006.
