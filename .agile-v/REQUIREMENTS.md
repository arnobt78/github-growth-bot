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

## Frontend Requirements (C1 — Approved, Not Yet Implemented)

**REQ-0010 — Next.js App Router dashboard.** Overview page (tracked repos, sparklines, delta badges), repo detail page (trend charts, benchmark comparison, referrers, recommendations), recommendations inbox, pipeline runs history, settings. SSR data-fetching directly in `page.tsx`; only genuinely interactive code in `use client` components.
**Status:** approved [C1], not started.

**REQ-0011 — Instant UI updates, no refresh, on any CRUD action.** TanStack Query mutations + SSE-driven cache invalidation update the current tab and all other open tabs immediately (dismiss recommendation, add/remove repo, manual run trigger) — consuming REQ-0008's `/events` stream. Shell (headers/labels/icons/buttons/cards) renders instantly; only data-bearing regions show inline pulse-skeletons, no `loading.tsx`. Independent server prefetches run in parallel (`Promise.all`), not sequential.
**Status:** approved [C1], not started.

**REQ-0012 — Shared, reusable, strictly-typed UI layer.** `lib/`/`hooks/`/`providers/`/`types/`/`components/ui/` structure; types generated from the backend's OpenAPI schema (no hand-duplicated interfaces); shadcn/ui + Tailwind consistent theme (light/dark); every title/label/button carries a meaningful `lucide-react` icon with semantic color tied to the data it represents. `SafeImage` pattern (`docs/SAFE_IMAGE_REUSABLE_COMPONENT.md`) reused for GitHub avatars.
**Status:** approved [C1], not started.

**REQ-0013 — API-key isolation from the browser.** Browser never holds the backend's static API key; Next.js Route Handlers attach it server-side and proxy all backend calls.
**Status:** approved [C1], not started. **Open item:** Product Owner flagged this as the chosen default over full auth (Clerk/NextAuth) or Vercel password protection — revisit if the dashboard's threat model changes (see RISK_REGISTER RISK-0004).

**REQ-0014 — Vercel deployment with production guardrails.** Bot protection + AI-bot blocking ON, security headers in `next.config.ts` mirrored in `vercel.json`, `/_next/static/` immutable cache, single-source `robots.ts` disallowing all crawling (`disallow: "/"` — personal tool, no SEO value), per `docs/VERCEL_PRODUCTION_GUARDRAILS.md`.
**Status:** approved [C1], not started.

---

## Deferred to Later Cycles (explicitly out of C1 scope)

Per the approved design spec, these feature groups from the user's original request are deferred and will be opened as new cycles (C2+) with their own REQ sets when picked up: README/docs/topics improvement suggestions + SEO doc generation; issue/discussion auto-response; release-notes automation + demo GIF/video generation; community & trend discovery (similar-repo contribution opportunities, forum recommendations).

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
| REQ-0010 | Frontend | approved [C1] | not started |
| REQ-0011 | Frontend | approved [C1] | not started |
| REQ-0012 | Frontend | approved [C1] | not started |
| REQ-0013 | Frontend | approved [C1] | not started |
| REQ-0014 | Frontend | approved [C1] | not started |
