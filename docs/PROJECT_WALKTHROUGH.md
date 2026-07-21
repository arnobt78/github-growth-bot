# Project Walkthrough — GitHub Growth Bot

How the system actually works, end to end. For status/roadmap see `PROJECT_PLAN.md`; for requirement-level traceability see `../.agile-v/REQUIREMENTS.md`; for the original design rationale see `superpowers/specs/2026-07-20-github-growth-bot-design.md`.

## The problem this solves

Growing a GitHub repo organically takes noticing things: "your stars grew 20% this week, probably from that Hacker News post" or "similar repos average 3x your stars and they all have a LICENSE file, you don't." Nobody checks this daily. This bot does, safely — it never touches anyone else's repo, never stars/forks/follows anything, and every AI-written claim it shows you is fact-checked against real numbers before you see it.

## How a daily run works

```
1. APScheduler fires (every 24h) or you hit POST /runs manually
2. run_pipeline_for_all_repos() loads every tracked repo, runs the pipeline for each:

   Extractor        → pulls fresh data from the GitHub API (stars, forks, traffic,
                       referrers, popular paths, README, LICENSE/CONTRIBUTING presence,
                       benchmark repos with similar language+topic)
   Preprocessor      → diffs against yesterday's snapshot (stars_delta, forks_delta),
                       normalizes everything into one shape
   Analyzer          → turns raw numbers into findings ("missing LICENSE", "referrer
                       spike from news.ycombinator.com", "similar repos average 3x
                       your stars") — pure computation, no AI yet
   Optimizer         → ranks findings by impact-vs-effort, keeps the top 10, drops noise
   Synthesizer       → hands the ranked findings to the LLM router, asks for a JSON list
                       of {title, body, category} recommendations written in plain English
   Validator         → the hallucination guard: extracts every number the AI wrote and
                       checks it actually appears somewhere in the real data. Fabricated
                       numbers get the recommendation marked unvalidated
   Assembler         → writes the day's Snapshot, BenchmarkRepo, Referrer, and
                       PopularPath rows, and persists only the *validated*
                       recommendations

3. Every stage is wrapped in its own try/except by PipelineRunner. If Extractor's
   network call fails for one repo, that repo's run is marked "degraded" and the
   rest of your tracked repos still get processed — one bad API call never takes
   down the whole batch.
```

## The LLM router (why it never just breaks)

The Synthesizer needs *an* LLM to write recommendations, but free-tier LLM APIs get rate-limited constantly. `app/llm_router.py` tries providers in a fixed order — **Groq → Gemini → OpenRouter → Hugging Face → Cloudflare Workers AI → Vercel AI Gateway** — and within each provider, tries multiple models before giving up on that provider entirely. If literally everything fails, the Synthesizer just produces zero recommendations for that run instead of crashing — you still get your raw metrics, just no AI commentary that day.

This exact fallback pattern is ported from the user's own proven TypeScript chatbot implementation (see `LLM_MODEL_IMPLEMENTATION_GUIDE.md` / `LLM_MODEL_SELECTION.md` in this `docs/` folder) — not invented from scratch.

## The API surface

Everything requires `Authorization: Bearer <API_KEY>` except the health check. Endpoint names deliberately avoid words like "analytics" or "tracking" that ad-blockers commonly filter out of URLs — so `/repos/{id}/insights` instead of `/repos/{id}/analytics`, `/repos/{id}/snapshots` instead of `/repos/{id}/tracking`, etc.

| Endpoint | What it does |
|---|---|
| `GET/POST/DELETE /repos` | Manage which repos you're tracking |
| `GET /repos/{id}/snapshots` | Time-series history for one repo |
| `GET /repos/{id}/insights` | Latest stars/forks + open recommendation count |
| `GET /repos/{id}/benchmarks` | How you compare to similar repos |
| `GET /recommendations` / `PATCH /recommendations/{id}` | Cross-repo recommendation feed, dismiss individual ones |
| `GET/POST /runs` | Pipeline run history, manually trigger a run |
| `GET /providers/status` | Which LLM providers are near their daily rate limit |
| `GET /events` | Server-Sent Events stream — pushes live updates when anything changes (a recommendation gets dismissed, a repo gets added, a run completes) |

## Why the frontend feels instant

The dashboard's page *shell* — headers, card outlines, buttons, icons — renders immediately on every navigation; only the actual data numbers show a brief loading pulse (no `loading.tsx` anywhere). Each of the 5 pages (Overview, repo detail, recommendations inbox, pipeline runs, settings) is a Next.js Server Component (`page.tsx`, `export const dynamic = "force-dynamic"`) that fetches its data server-side, in parallel via `Promise.all` — never one slow query blocking the whole page — then hands it to a `use client` component through TanStack Query's `HydrationBoundary`.

Every open browser tab also subscribes to the backend's `/events` SSE stream (`hooks/use-live-events.ts`). Any change anywhere — dismissing a recommendation, adding/removing a repo, triggering a run, or the daily scheduled run finishing — invalidates the relevant TanStack Query cache keys and shows up everywhere instantly, current tab and every other open tab, without a page refresh.

The browser never holds the backend's API key: Next.js Route Handlers under `frontend/app/api/**` proxy every backend call server-side, using the same typed `lib/api.ts` client the Server Components use for SSR.

## Safety rails baked into the design

- **No write access to GitHub, anywhere.** `GitHubClient` only has `get_*`/`has_file`/`search_similar_repos` methods — there is no method that could star, fork, follow, or otherwise touch another account's repo, even by accident.
- **Every AI claim is checked against real data** before it's ever shown to you (the Validator stage).
- **A single tracked repo's failure never affects the others** — per-stage, per-repo error isolation all the way through the pipeline.
- **The backend's API key never reaches the browser** — the Next.js frontend proxies every call server-side.

## Where to go deeper

- Full requirement list + verification status: `../.agile-v/REQUIREMENTS.md`
- Every architectural decision and why it was made: `../.agile-v/DECISION_LOG.md`
- What went wrong during build and how it got caught: `../.agile-v/CAPA_LOG.md`
- Known accepted risks: `../.agile-v/RISK_REGISTER.md`
- Original design conversation: `superpowers/specs/2026-07-20-github-growth-bot-design.md`
- Task-by-task implementation plans: `superpowers/plans/2026-07-20-github-growth-bot-backend.md`, `superpowers/plans/2026-07-20-github-growth-bot-frontend.md`
