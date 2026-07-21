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

## Phase 2+ (Deferred — will get their own design docs when picked up)

From the original feature request, explicitly scoped out of Phase 1:

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
