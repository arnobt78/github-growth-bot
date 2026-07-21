# Project Plan — GitHub Growth Bot

Living roadmap. Requirement-level detail and status: `.agile-v/REQUIREMENTS.md`. This file is the human-readable narrative version.

## Phase 1: Repo Health & Analytics

The foundation everything else builds on — track repo metrics over time, benchmark against similar projects, surface AI-synthesized (and fact-checked) recommendations, in a fast personal dashboard.

### Backend — ✅ Done (2026-07-20)

- 7-stage analytics pipeline (Extractor → Preprocessor → Analyzer → Optimizer → Synthesizer → Validator → Assembler), running daily per tracked repo, resilient to any single stage failing.
- GitHub data extraction: stars/forks/watchers/open-issues, 14-day traffic, referrers, popular paths, README/LICENSE/CONTRIBUTING presence, benchmark repos.
- 6-provider LLM fallback router (Groq → Gemini → OpenRouter → Hugging Face → Cloudflare Workers AI → Vercel AI Gateway) so no single free-tier rate limit ever blocks a run.
- Hallucination-guarding Validator — every AI-written recommendation gets its cited numbers cross-checked against real data before it's shown to anyone.
- REST + SSE API (ad-blocker-safe endpoint naming), API-key authentication on every route.
- Daily automated trigger (APScheduler) + real-time event push for instant UI updates.
- Postgres schema + Alembic migrations, ready for the existing Coolify/Hetzner VPS deployment pattern.
- 30/30 tests passing. 11 implementation tasks + 1 final whole-branch review, each independently reviewed by a fresh subagent — 5 real defects caught and fixed along the way (see `.agile-v/CAPA_LOG.md` and `.agile-v/DECISION_LOG.md` for the two most significant: a DB-session-poisoning bug that would've crashed the daily pipeline run, and a dead `/benchmarks` endpoint that silently never got real data written to it).

**Not yet done for backend:** actual VPS deployment (DNS, Coolify app, Postgres provisioning, `alembic upgrade head`) — code is ready, deploy is a manual step tracked as an open item.

### Frontend — ✅ Done (2026-07-21)

Next.js 16 App Router dashboard consuming the backend API:

- Overview page (tracked repos, sparklines, delta badges), repo detail page (trend charts, benchmark comparison, referrers, popular paths, recommendations), recommendations inbox, pipeline run history, settings (manage tracked repos)
- Instant updates everywhere on any CRUD action (dismiss, add/remove repo, manual run) — no page refresh, current tab and every other open tab, via TanStack Query mutations + the backend's SSE stream
- SSR-first rendering: every page is `force-dynamic` with parallel (`Promise.all`) server-side prefetch directly in `page.tsx`; page shell appears instantly, only data regions show inline skeletons, no `loading.tsx` anywhere
- Strict TypeScript throughout, types generated from the backend's live OpenAPI schema, shared `lib/`/`hooks/`/`providers/`/`components/ui/` layer, icon+color conventions on every title/label/button
- API key never reaches the browser — Next.js Route Handlers proxy every backend call server-side
- Production guardrails configured for Vercel (bot protection, security headers, no-crawl robots policy) — actual deployment still pending, tracked separately

**Status:** built via 20-task subagent-driven plan (`docs/superpowers/plans/2026-07-20-github-growth-bot-frontend.md`), each task independently reviewed, plus a final whole-branch review. One backend bug found along the way (no cascade-delete on repo foreign keys, causing a 500 on deleting a repo with history) — root-caused and fixed with a proper migration + regression test. A post-plan deep audit then found and closed one more gap: 6 starlette CVEs + 1 pytest CVE reached transitively via a pinned `fastapi` version, fixed by bumping dependencies. Gate 2-accepted (`GATE-0002`).

## Phase 2: Multi-Tenant SaaS Foundation (in design — 2026-07-21)

Everything from here on depends on this landing first: today the app is single-tenant (one shared static API key, one global set of tracked repos). This phase turns it into a real multi-tenant SaaS — anyone can sign in with their own GitHub account and track their own repos, fully isolated from every other user's data.

- **Auth:** Auth.js (NextAuth v5), GitHub OAuth provider only, JWT session (no DB adapter — Next.js still never touches Postgres directly, matching the existing "backend owns the DB" rule). Public-repo scope only for v1 (lower liability; growth metrics are inherently public-facing signals anyway).
- **Data isolation:** new `User` table; every existing table (`Repo`, `Snapshot`, `BenchmarkRepo`, `Referrer`, `PopularPath`, `Recommendation`, `PipelineRun`, `StageRun`) gains a `user_id` FK (`ondelete="CASCADE"`). Existing historical data backfills to the Product Owner's own account on first login — no data lost.
- **Security, defense-in-depth:** Auth.js session check → Route Handler mints a short-lived HMAC-signed internal token (closes the "what if the backend port is ever reachable directly" gap that a plain trusted header wouldn't) → existing `require_api_key` → new `require_user` dependency → every query filtered by `user_id` at the DB layer. OAuth tokens encrypted at rest (Fernet), never logged, never returned by any API response.
- **Billing:** free-for-everyone in v1 — no Stripe yet — but `plan` (default `"free"`) and `max_tracked_repos` (default `5`) columns ship now so a future plans/billing phase is a config change, not a schema migration.

### Applicable architecture concepts (from `docs/PROJECT_IDEA.md`'s 12) — reviewed against this project's actual scale

| # | Concept | Applied how | Why (or why not yet) |
|---|---|---|---|
| 2 | Caching | New in-memory TTL cache in the backend for expensive/rate-limited GitHub calls (benchmark/similar-repo search); TanStack Query client cache + SSR prefetch already cover the frontend side | Real, immediate payoff — GitHub search calls are the most rate-limit-sensitive part of the pipeline |
| 4 | Message Queue | Manual `POST /runs` moves off the synchronous request path onto FastAPI `BackgroundTasks` (immediate 202, run happens in background) | With multiple users able to trigger runs concurrently, blocking a web request on a multi-minute LLM-backed pipeline run is a real bug, not a hypothetical one |
| 5 | Publish–Subscribe | Existing SSE `EventBroadcaster` gets scoped per-user — a user's `/events` stream only ever receives events for their own data | Multi-tenant makes the current "broadcast to everyone" behavior an actual data-leak (User B would see User A's repo-added/run-completed events) |
| 6 | API Gateway | Formalizing what already exists: Next.js Route Handlers are the single entry point for auth, routing, and now internal-token minting; rate limiting added at this layer too | Already the architecture — this phase just adds the auth check that was missing |
| 7 | Circuit Breaker | Extends the existing per-stage pipeline isolation and `LLMRouter` provider fallback: a user's expired/revoked GitHub token now stops that user's run early (marked "needs reauth") instead of retry-hammering a dead token | One user's bad token must never affect another user's run or waste retry budget |
| 10 | Rate Limiting | `slowapi`, per-user and per-IP, on `POST /repos` and `POST /runs`; in-memory store (single-container deploy) | Public sign-up means public abuse surface for the first time — this wasn't a concern in the single-tenant version |
| 1 | Load Balancing | Not added | Vercel already load-balances the frontend at the edge; backend is one Coolify container serving personal-SaaS-scale traffic — revisit only if real load ever demands horizontal scaling |
| 3 | CDN | Not added (already satisfied) | Vercel's edge network already CDNs every static asset; nothing to build |
| 8 | Service Discovery | Not added | Exactly two services (frontend, backend) at fixed, env-configured URLs — a service mesh would be solving a problem this architecture doesn't have |
| 9 | Sharding | Not added | Single Postgres instance is nowhere near the row-count/throughput where sharding pays for itself; revisit only if a specific table's growth actually demands it |
| 11 | Consistent Hashing | Not added | No distributed cache or sharded store exists yet to need it — would be solving for infrastructure this project doesn't have |
| 12 | Auto Scaling | Not added | Vercel auto-scales the frontend inherently; Coolify can scale backend replicas later if traffic ever requires it — premature today |

The six left "not added" aren't skipped out of laziness — building them now would be solving problems this project doesn't have yet at personal-SaaS scale, which is its own kind of technical debt (complexity with no payoff). Each has a stated trigger for revisiting it later.

Full design: `docs/superpowers/specs/2026-07-21-multi-tenant-saas-design.md` (once written and approved).

## Phase 3: Visual & Portfolio Polish (planned, after Phase 2)

Fonts, icon/color consistency pass, and an "agentic pipeline" visualization — showing the 7-stage pipeline actually running live (which stage is active, what it found) rather than just its end results, since that's the most portfolio-differentiating thing this project has and it's currently invisible to a viewer.

## Phase 4+ (Deferred — will get their own design docs when picked up)

From the original feature request, explicitly scoped out of Phase 1, now understood to run per-user once Phase 2 lands:

- **README/docs/topics improvement suggestions** — SEO-friendly docs generation, missing-documentation detection, topic/tag recommendations
- **Issue/discussion auto-response** — bot reads new issues/discussions, drafts or posts responses
- **Release automation** — auto-generated release notes; demo GIF/video generation on new releases
- **Community & trend discovery** — monitor similar repos for contribution opportunities, recommend relevant communities/forums, analyze GitHub trends for discoverability

## Explicit Non-Goal (permanent, not a phase)

No auto-starring, auto-forking, auto-following, or any other artificial engagement inflation, ever. This was explicitly refused at project kickoff (see `.agile-v/DECISION_LOG.md` DEC-0001) and is enforced as a standing code-review policy (`.agile-v/POLICY.yaml` POL-0001).

## Timeline

| Date | Milestone |
|---|---|
| 2026-07-20 | Project kickoff, design brainstorm, backend spec + plan approved |
| 2026-07-20 | Backend built (11 tasks), reviewed, 30/30 tests passing |
| 2026-07-20 | Agile-V governance adopted, C1 retroactively traceable |
| 2026-07-20 | Gate 2 approved for backend sub-scope (GATE-0001) |
| 2026-07-21 | Frontend built (20 tasks), reviewed, one backend cascade-delete bug found + fixed, one dependency-CVE gap found + fixed |
| 2026-07-21 | Gate 2 approved for frontend sub-scope (GATE-0002) |
| TBD | VPS + Vercel deployment |
