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

### Frontend — 🔜 Next

Next.js App Router dashboard consuming the backend API:

- Overview page (tracked repos, sparklines, delta badges)
- Repo detail page (trend charts, benchmark comparison, referrers, recommendations)
- Recommendations inbox (cross-repo feed, dismiss/filter)
- Pipeline run history (debugging view)
- Settings (manage tracked repos)
- Instant updates everywhere on any CRUD action (dismiss, add/remove repo, manual run) — no page refresh, via TanStack Query + the backend's SSE stream
- SSR-first rendering: page shell appears instantly, only data regions show inline skeletons
- Strict TypeScript, shared component library, icon+color conventions throughout
- Deployed to Vercel with production guardrails (bot protection, security headers, no-crawl robots policy)

**Status:** design approved (see spec), not yet built. Will follow the same process as the backend: brainstorm → design doc → implementation plan → subagent-driven build → final review.

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
| TBD | Gate 2 approval for backend sub-scope |
| TBD | Frontend brainstorm + design |
| TBD | Frontend build |
| TBD | VPS + Vercel deployment |
