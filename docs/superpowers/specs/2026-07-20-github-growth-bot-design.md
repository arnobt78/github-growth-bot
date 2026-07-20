# GitHub Growth Bot — Phase 1 Design (Repo Health & Analytics)

Status: Approved for implementation
Date: 2026-07-20

## 1. Overview

A personal, account-wide "command center" that watches all of the user's GitHub repos, tracks
stars/forks/watchers/traffic over time, benchmarks them against similar public repos, and
surfaces prioritized, LLM-synthesized recommendations — all in a fast, self-hosted web dashboard.

Built as a real multi-agent pipeline (Extractor → Preprocessor → Analyzer → Optimizer →
Synthesizer → Validator → Assembler), run daily, with a multi-provider free-tier LLM fallback
router so no single provider's rate limits ever block a run.

### 1.1 Explicit non-goal

This system **never** artificially inflates stars, forks, watchers, or traffic (no auto-starring
from other accounts, no bot networks, no paid engagement services). That violates GitHub's
Acceptable Use Policies and is out of scope by design. All growth here is organic: better docs,
better discoverability, better community engagement.

### 1.2 Phase 1 scope

In scope: repo health & analytics only — data extraction, historical tracking, benchmarking
against similar repos, LLM-synthesized insights/recommendations, and a rich dashboard.

Deferred to later phases (each gets its own spec when picked up):

- README/docs/topics improvement suggestions, SEO-friendly docs generation
- Issue/discussion auto-response
- Release notes automation, demo GIF/video generation on release
- Community & trend discovery (similar-repo contribution opportunities, forum recommendations)

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Daily trigger (APScheduler, in-process) + manual "run now"     │
└───────────────────────────┬─────────────────────────────────────┘
                             ▼
                  ┌────────────────────┐
                  │   Pipeline Runner   │  (Python, orchestrates stages)
                  └──────────┬─────────┘
     ┌────────────┬──────────┼──────────┬────────────┬────────────┐
     ▼            ▼          ▼          ▼            ▼            ▼
 Extractor → Preprocessor → Analyzer → Optimizer → Synthesizer → Validator → Assembler
 (GitHub     (normalize,    (trend/    (rank what   (LLM: write   (LLM/rule  (build final
  API pull)   diff vs       compare    matters,     human-        sanity-     snapshot +
              last run)     stages)    drop noise)  readable       check      recommendations)
                                                     insights)      output)
                             │            │             │             │
                             └────────────┴─────────────┴─────────────┘
                                    LLM Router (multi-provider,
                                  free-tier, fallback on 429/5xx)
                                          │
                         Groq → Gemini → OpenRouter(:free) → HuggingFace →
                              Cloudflare Workers AI → Vercel AI Gateway
                             ▼
                        Postgres (time-series snapshots,
                          pipeline run logs, recommendations)
                             ▼
              FastAPI (REST + SSE) — Coolify container, Hetzner VPS
                             ▼
        Next.js Route Handlers (attach API key server-side; proxy)
                             ▼
              Next.js App Router dashboard — Vercel
                             ▼
                     Your browser
```

Each pipeline stage is a small class: `class Stage: def run(self, ctx: PipelineContext) ->
PipelineContext`. The runner executes them in order, catches/logs exceptions per stage (a
failure in Synthesizer must not lose the raw data Extractor already pulled), and writes a
`pipeline_run` row with per-stage status/duration/error to Postgres. A stage failure degrades
the run (raw metrics still land in the dashboard) rather than failing it outright.

## 3. Backend (Python / FastAPI)

### 3.1 Pipeline stages

| Stage | What it does | Uses LLM? |
|---|---|---|
| **Extractor** | Pulls via GitHub REST/GraphQL: repo metadata, stars/forks/watchers/open-issues, 14-day traffic (views/clones + uniques), referrers & popular content paths, stargazer timestamps, README + presence of CONTRIBUTING/LICENSE/docs, releases. Also searches GitHub for similar repos (topic+language match) as benchmarks. | No |
| **Preprocessor** | Normalizes raw API responses into the internal schema; diffs against yesterday's snapshot to compute deltas; accumulates GitHub's rolling 14-day traffic window into permanent history so nothing is lost between runs. | No |
| **Analyzer** | Computes star/fork velocity, growth trends, percentile vs. benchmark repos, flags traffic anomalies (e.g. a referrer spike from Hacker News). | No (pandas/plain Python) |
| **Optimizer** | Scores and ranks Analyzer's findings by impact/effort (e.g. "missing topics" = high-impact/low-effort), drops redundant noise. | Mostly rule-based |
| **Synthesizer** | Turns ranked findings into a readable narrative + concrete recommendations. | **Yes**, via LLM Router |
| **Validator** | Cross-checks every number the Synthesizer's text cites against the actual source data; rejects/flags recommendations with unsupported claims (hallucination guard). | Rule-based checks + optional second-opinion call on a *different* provider than Synthesizer used |
| **Assembler** | Combines validated synthesis + raw metrics into the day's final snapshot record. | No |

### 3.2 LLM Router

Ported from the user's existing TypeScript multi-provider chatbot pattern
(`docs/LLM_MODEL_IMPLEMENTATION_GUIDE.md`, `docs/LLM_MODEL_SELECTION.md`) to Python, calling each
provider's OpenAI-compatible chat-completions endpoint via `httpx` wherever available, so the
router logic stays uniform:

**Fallback order:** Groq → Gemini (OpenAI-compatible endpoint) → OpenRouter (`:free` models) →
Hugging Face (router.huggingface.co) → Cloudflare Workers AI → Vercel AI Gateway.

**Per-provider model chains** (mirroring the user's established preference list, adjusted for
prose/analysis rather than coding):

- Groq: `openai/gpt-oss-120b` → `qwen/qwen3.6-27b` → `openai/gpt-oss-20b` (never
  `llama-3.1-8b-instant` / `llama-3.3-70b-versatile` — deprecated, shutdown 2026-08-16)
- OpenRouter: rotating `:free` tier models (e.g. `meta-llama/llama-3.3-70b-instruct:free`,
  `deepseek/deepseek-chat-v3-0324:free`)
- Others: single best free-tier model per provider

**Failover rules** (silent, automatic — mirrors the existing pattern's "fast skip on 429"):
switch to the next model/provider on timeout, 429, 500/502/503/504, model unavailable/deprecated,
context overflow, or empty response. Never stop after one failure; if every provider fails, the
stage degrades gracefully (raw data still ships) instead of failing the whole run.

**Usage tracking:** daily call counts per provider stored in Postgres so the router can
proactively skip a provider nearing its free-tier ceiling instead of waiting for a 429.

### 3.3 Data model (Postgres)

- `repos` — tracked repos (owner, name, tracked_since)
- `snapshots` — daily metrics per repo (stars, forks, watchers, open_issues, views_14d,
  unique_views_14d, clones_14d, unique_clones_14d, accumulated historical totals)
- `benchmark_repos` — comparison data (similar repos' stars/forks/topics, captured_at)
- `referrers` / `popular_paths` — traffic detail per repo per day
- `pipeline_runs` / `stage_runs` — observability (status, duration, error per stage)
- `recommendations` — Synthesizer output (category, title, body, validated flag, dismissed flag)
- `llm_usage` — per-provider daily call counts for proactive rate-limit avoidance

### 3.4 API design

REST + one SSE stream. Endpoint names deliberately avoid words that trigger ad-blocker /
browser-extension URL filters (`analytics`, `analysis`, `tracking`, `performance`, `metrics`):

- `GET /repos`, `POST /repos`, `DELETE /repos/{id}` — tracked repo management
- `GET /repos/{id}` — repo detail
- `GET /repos/{id}/snapshots` — time-series history
- `GET /repos/{id}/insights` — Analyzer + Synthesizer output
- `GET /repos/{id}/benchmarks` — comparison vs. similar repos
- `GET /recommendations`, `PATCH /recommendations/{id}` — cross-repo feed, dismiss/mark-done
- `GET /runs`, `POST /runs` — pipeline run history, manual trigger
- `GET /providers/status` — LLM provider health/usage
- `GET /events` — SSE stream (pipeline-run-complete, recommendation-dismissed, repo-added/removed)
- `GET /api/health` — Coolify healthcheck target

All endpoints require a static `Authorization: Bearer <API_KEY>` header (env-configured), called
only from the Next.js server (Route Handlers), never from the browser directly.

### 3.5 Deployment (matches user's existing Coolify/Hetzner pattern)

- Single Docker image: `python:3.12-slim`, non-root user, `.dockerignore`, `requirements.txt`
  layer cached before app code, `HEALTHCHECK` against `/api/health` — per
  `docs/DOCKER_VPS_BACKEND_PLAYBOOK.md`.
- Daily pipeline run triggered in-process via APScheduler inside the same FastAPI app (no
  separate cron service) — matches the user's one-container-per-app Coolify convention.
- Deployed as a Coolify app on the existing Hetzner VPS (77.42.71.87), subdomain
  `github-bot-backend.arnobmahmud.com` (IONOS A record + Coolify Traefik/Caddy labels per
  `docs/SUBDOMAIN_ARNOBMAHMUD_SETUP.md` — rename the subdomain freely, it's just DNS).
- Postgres runs as a separate Coolify-managed service, not bundled in the app container (per the
  playbook's own guidance).
- `CORS_ORIGINS` restricted to the production Vercel frontend URL.
- Secrets (GitHub PAT, LLM provider keys, `API_KEY`) set only in Coolify env — never committed.

## 4. Frontend (Next.js App Router, TypeScript)

### 4.1 Rendering & data-fetching pattern

- SSR data-fetching code lives directly in `page.tsx` (Server Components); only genuinely
  client-only code (`use client`) lives in `components/`.
- No `loading.tsx` files — the page shell (headers, labels, icons, buttons, card frames, table
  structure) renders instantly; only the data-bearing regions show an inline pulse-skeleton
  the same width/height as the real content, and only while that specific query is pending.
- Independent server-side prefetches run in parallel via `Promise.all(...)`, not sequential
  `await`s, so the page waits for the slowest query, not the sum of all of them.
- Prefetched queries are dehydrated (`dehydrate(queryClient)` + `<HydrationBoundary>`) so
  TanStack Query on the client picks up the SSR data without an extra round-trip. Below-the-fold,
  non-critical data may be fetched client-side only (not dehydrated) if it would otherwise block
  first paint.
- All server-to-backend calls go through Next.js Route Handlers that attach the API key —
  the browser only ever talks to the Next.js app's own `/api/*` routes.

### 4.2 Instant-update flow (CRUD actions)

Dismissing a recommendation, adding/removing a tracked repo, or manually triggering a pipeline
run: a TanStack Query mutation fires (optimistic update in the current view) → the Route Handler
persists the change against FastAPI → FastAPI emits an event on an in-process async broadcaster
→ the `/events` SSE stream pushes it to all connected browser tabs → each tab's SSE-subscribing
provider invalidates the relevant TanStack Query keys → every open page (current tab and any
other open tab) re-renders with fresh data, no reload, no polling. No Redis needed for this scale
(single backend process); can be added later if the backend ever scales beyond one instance.

### 4.3 Shared structure

- `lib/` — API client, formatting helpers
- `hooks/` — e.g. `useRepoSnapshots`, `useRecommendations`, `useLiveEvents` (SSE subscription)
- `providers/` — TanStack Query provider + SSE-subscription provider, mounted once in the root layout
- `types/` — generated from the FastAPI OpenAPI schema so frontend/backend types never drift
- `components/ui/` — shared, reusable primitives (buttons, cards, charts, skeletons, badges),
  shadcn/ui + Tailwind, consistent theme tokens (light/dark)
- `components/safe-image.tsx` — reused from `docs/SAFE_IMAGE_REUSABLE_COMPONENT.md` for GitHub
  owner/repo avatars (falls back to plain `<img>` if Next.js image optimization fails)

### 4.4 UI conventions

- Every title, subtitle, label, and button carries a meaningful `lucide-react` icon alongside
  its text, with semantic color (e.g. green up-trend, red down-trend, amber warning) — not
  decorative-only, tied to the data it represents.
- Pages (Phase 1): Overview (card grid of tracked repos, sparklines, delta badges), Repo detail
  (trend charts, benchmark comparison, referrers, recommendations for that repo), Recommendations
  inbox (cross-repo feed, filter/sort, dismiss), Pipeline runs (execution history, per-stage
  status — debugging aid), Settings (manage tracked repos, view LLM provider health/usage).

### 4.5 Vercel production guardrails

Per `docs/VERCEL_PRODUCTION_GUARDRAILS.md`: bot protection + AI bot blocking on in the Vercel
dashboard, security headers in `next.config.ts` (mirrored in `vercel.json`), `/_next/static/`
cached immutable, single-source `robots.ts` disallowing all crawling (`disallow: "/"`) since this
is a personal, non-public tool with no SEO value.

## 5. Engineering conventions

- Strict TypeScript throughout the frontend; exhaustive handling of loading/error/empty states.
- No dead code, no leftover debug log files, no unused dependencies.
- Comments explain non-obvious *why*, not *what* — plus a light code-walkthrough pass after
  initial implementation (functions/pages/components/API routes get a short explanatory comment
  for future-reference understanding), without altering any existing logic.
- No duplicate/redundant API calls across components — shared TanStack Query keys and hooks
  prevent the same data being fetched twice on one page.
- Dependencies kept current and vulnerability-free: `npm audit` / `pip-audit` run clean, lint and
  build run clean, before considering any milestone done.
- No summary/changelog `.md` files created during implementation — documentation lives as
  in-code comments plus this spec.

## 6. Testing approach

- Backend: unit tests per pipeline stage (mocked GitHub/LLM responses), integration test for the
  full pipeline run against a fixture repo, LLM router tested for correct fallback ordering and
  429-skip behavior.
- Frontend: component tests for shared UI primitives; a smoke test that SSE-driven invalidation
  actually updates a mounted query (mutation → event → refetch).
- Manual verification pass in a browser (per project convention) before declaring the dashboard
  done: golden path (view repos, drill into one, dismiss a recommendation, trigger a manual run)
  and edge cases (no repos tracked yet, all LLM providers down, a repo with zero traffic history).

## 7. Open items for the user to confirm before/at deploy time (not blockers for building)

- GitHub Personal Access Token scope: read-only on the repos to be tracked (needs `repo` scope
  for private repos' traffic API; public repos only need no auth or minimal scope).
- Final subdomain name for the backend (default proposed: `github-bot-backend.arnobmahmud.com`).
- Whether the static API-key proxy approach (Section 4.1) is sufficient, or real auth is wanted later.
