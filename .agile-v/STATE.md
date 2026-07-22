# Project State

**Project:** github-growth-bot
**Current Cycle:** C1
**Bootstrapped:** 2026-07-20 (retroactive — backend was built via `superpowers` skills before Agile-V adoption; see PLAYBOOK.md §2 for how the two map together)

## Current Position in the V

**Backend sub-scope (REQ-0000–REQ-0009):** Stage 5 (Acceptance) complete — Gate 2 approved (GATE-0001, 2026-07-20). Deployment (RISK-0005/0006 pre-deploy actions, Gate 2's deployment condition per POL-0006) still open, separate from this acceptance.
**Frontend sub-scope (REQ-0010–REQ-0014):** Stage 5 (Acceptance) complete — built (20 tasks, subagent-driven), final whole-branch review clean, escalated backend cascade-delete bug found and fixed, post-plan deep audit found and closed one dependency-CVE gap (RISK-0013), Gate 2 approved (GATE-0002, 2026-07-21). Deployment (Vercel) itself still open, separate from this acceptance, per POL-0006.
**Multi-tenant SaaS sub-scope (REQ-0015–REQ-0019):** Stage 4 (Verification) complete — built (18 tasks, subagent-driven: 11 backend + 7 frontend), whole-backend review clean after 1 fix round, final whole-branch review clean after 1 fix round. Stage 5 (Acceptance/Gate 2) **not yet formally logged** — code-complete and reviewed, but live end-to-end verification with a real GitHub OAuth App hasn't run yet (needs the Product Owner to register one; see Open Items below).

## Open Items Requiring Attention

1. ~~INT-0001 (CHECKPOINTS.md) — PENDING.~~ **CLOSED 2026-07-20 — Approved.** See `APPROVALS.md` GATE-0001. Backend sub-scope of C1 formally accepted.
2. ~~INT-0002 (CHECKPOINTS.md) — PENDING.~~ **CLOSED 2026-07-21 — Approved.** See `APPROVALS.md` GATE-0002. Frontend sub-scope of C1 formally accepted.
3. **Deployment not executed (either surface).** Backend: RISK-0005 (CORS env var) and RISK-0006 (manual Alembic migration step) are open pre-deploy actions. Frontend: Vercel deploy itself hasn't run. Both need their own Gate 2 evidence per POL-0006 before any Coolify/Vercel release action.
4. **Remote configured and current.** `https://github.com/arnobt78/github-growth-bot`, branch `main`. Local commits through the multi-tenant SaaS build are committed but **not yet pushed** as of this session (see Session Log below).
5. **Multi-tenant SaaS live E2E verification not yet run.** Needs: a real GitHub OAuth App registered by the Product Owner (client id/secret, callback URL `http://localhost:3000/api/auth/callback/github` for dev), both servers running, a real browser sign-in. This is the one remaining open item before Gate 2 can be requested for REQ-0015–REQ-0019 — everything else (code, tests, reviews) is done. Not something the controller can complete unilaterally (creating an OAuth App is the Product Owner's own GitHub account action).

## File Integrity

Git-tracked; multi-tenant SaaS build commits are present locally but not yet pushed as of this session's end (verify with `git status`/`git log origin/main..HEAD` at next session start per Directive 8/`agile-v-compliance` File Integrity rule).

## Next Action

The multi-tenant SaaS sub-scope needs the Product Owner to register a real GitHub OAuth App and complete a live sign-in verification (see Open Item 5) before Gate 2 can be requested for REQ-0015–REQ-0019. Once that's done (or if the Product Owner chooses to accept the sub-scope on code-review evidence alone, same as how backend/frontend Gate 2s were granted), push the pending commits and log the Gate 2 decision. Deployment itself (VPS + Vercel) remains a separate, later action per POL-0006 regardless.

## Session Log — 2026-07-20 (continued)

Evidence Summary presented for `INT-0001` (Gate 2, backend sub-scope). Product Owner requested end-of-day project documentation (`README.md`, `CLAUDE.md`, `docs/PROJECT_WALKTHROUGH.md`, `docs/PROJECT_PLAN.md`, created) and offered to push to GitHub. On follow-up, Product Owner confirmed repo details (`github-growth-bot`, public) and explicitly **Approved** Gate 2 for the backend sub-scope via `AskUserQuestion`. Logged as `GATE-0001`; `INT-0001` closed. Repository created and pushed: `https://github.com/arnobt78/github-growth-bot` (branch `main`, all 20 commits including the `.agile-v/` bootstrap and today's docs).

**Frontend brainstorming explicitly deferred to next session** ("we'll do tomorrow").

**Resume point for next session:** read this file first. Backend sub-scope is fully accepted (Gate 2 closed) — next work is either (a) Stage 1 (Requirements formalization / Gate 1) for the frontend sub-scope via `superpowers:brainstorming`, or (b) resolving RISK-0005/RISK-0006 and executing the actual VPS deployment (needs its own Gate 2 per POL-0006, since "accepted" ≠ "deployed"). No open `CHECKPOINTS.md` interrupts as of this log entry.

## Incident + Remediation — 2026-07-20 (same day, after Gate 2 closure)

**What happened:** The controller's original first commit accidentally included 3 private VPS-infrastructure docs (real IP, internal hostnames, other-project subdomains) that were then pushed to the public repo. Full detail: `CAPA_LOG.md` CAPA-0003, `DECISION_LOG.md` DEC-0019, `RISK_REGISTER.md` RISK-0011.

**Remediation completed:** Old repository (`arnobt78/github-growth-bot`) deleted by the Product Owner on GitHub; local `.git` wiped (`rm -rf .git`) by the Product Owner; controller re-initialized git from a clean working tree (all files verified present, sensitive docs correctly excluded via `.gitignore`), created ONE clean commit, created a new repository at the same URL, and pushed. Verified via `git log --all` (empty result for the 3 filenames) and GitHub API (old repo confirmed 404).

**Current repo state:** Single commit `31d7c1a` on `main` at `https://github.com/arnobt78/github-growth-bot`. This supersedes all prior commit SHAs referenced elsewhere in `.agile-v/` (e.g. `BUILD_MANIFEST.md`'s per-task commit list, `APPROVALS.md` GATE-0001's evidence reference) — those SHAs are now historical references to work *content*, not resolvable commits in the current repository. Not rewritten retroactively in this session (would require touching every file that cites a SHA); flagged here as the authoritative note on why old SHAs won't `git show` successfully going forward.

**Gate 2 (GATE-0001) status:** Still valid — it approved the backend *content/scope*, which is unchanged and fully intact in the new single commit. The approval is not invalidated by a history rewrite that changed no code, only commit-graph shape.

## Session Log — 2026-07-21

Frontend built end-to-end: 20-task subagent-driven plan (`docs/superpowers/plans/2026-07-20-github-growth-bot-frontend.md`), each task independently reviewed, one session-limit interruption recovered mid-Task-14 (implementer's completed work verified and finished directly), one escalated backend fix (no cascade-delete on repo FKs — 500 on deleting a repo with history; root-caused, fixed with a proper Alembic migration + SQLite-test-infra fix + regression test), one final whole-branch review (2 Important findings: missing `onError` parity on the dismiss-recommendation mutation, and `run_completed` SSE not invalidating `recommendations` — both fixed and re-verified).

Product Owner then requested a deep audit before test/commit. Audit covered: `pytest`, `tsc --noEmit`, `eslint`, `next build`, dead-code/orphan-file scan, mutation error-handling parity, SSE invalidation completeness, API-key gating, ad-blocker-safe naming, `npm audit`, `pip-audit`. Everything came back clean except one real gap: `pip-audit` found 6 starlette CVEs (via `fastapi==0.115.6`'s pin) + 1 pytest CVE, not previously logged. Fixed by bumping `fastapi`→0.139.2 (resolves `starlette`→1.3.1), `pytest`→9.1.1, `pytest-asyncio`→1.4.0, plus `httpx2` as a new test-only dep (starlette 1.3.1's `TestClient` otherwise emits a new deprecation warning). Logged as `RISK-0013` (Resolved), commit `24d31d9`. A fresh subagent independently re-verified the fix (tests, `pip-audit`, no runtime-code impact, `httpx2` confirmed test-scope-only) — clean, no issues.

Product Owner then explicitly authorized pushing to GitHub pending clean review ("commit in github if all okay as flawless after code review"). Logged as `GATE-0002` (Approved) for the frontend sub-scope, closing `INT-0002`. Governance docs (`STATE.md`, `REQUIREMENTS.md`, `CHECKPOINTS.md`, `APPROVALS.md`, `docs/PROJECT_PLAN.md`, `docs/PROJECT_WALKTHROUGH.md`) updated to reflect frontend acceptance before push.

Pushed to `https://github.com/arnobt78/github-growth-bot` at `main`: `3081105..f6f42ee` (29 commits — full frontend build, escalated backend fix, final-review fix, CVE fix, this governance update).

**Resume point for next session:** read this file first. Both C1 sub-scopes are Gate 2-accepted and pushed; remaining work is deployment only (see Next Action above).

## Session Log — 2026-07-21/22

Product Owner asked to keep extending the project toward a portfolio-showcase SaaS. Brainstormed (`superpowers:brainstorming`) the multi-tenant SaaS pivot: GitHub OAuth login, per-user data isolation, defense-in-depth authorization — decomposed as its own sub-project (visual polish and the deferred feature phases explicitly deferred until this foundation lands, per the design's own decomposition). Design spec written and approved (`docs/superpowers/specs/2026-07-21-multi-tenant-saas-design.md`), including a review of `docs/PROJECT_IDEA.md`'s 12 general architecture concepts against this project's actual scale (6 applied — Caching, Message Queue, Pub-Sub, API Gateway, Circuit Breaker, Rate Limiting; 6 deliberately deferred as premature at personal-SaaS scale, each with a stated revisit trigger — see `docs/PROJECT_PLAN.md` Phase 2's table).

18-task implementation plan written and executed via `superpowers:subagent-driven-development`, fresh implementer + reviewer per task, work directly on `main`:

**Backend (Tasks 1-11):** `User` model + two-phase (nullable→backfill→not-null) migration, Fernet token encryption, custom HMAC-signed internal auth token, `require_user` dependency, per-user scoping across repos/insights/recommendations/runs, per-user SSE (`EventBroadcaster`), `GitHubClient` circuit breaker (`GitHubAuthError`) + benchmark-search TTL cache, per-user pipeline execution + `BackgroundTasks`-based async run trigger, `slowapi` rate limiting. A whole-backend review (after Task 10) found 1 Medium (the daily scheduler had no exception isolation around per-repo token decryption — one corrupted token could abort every tenant's nightly run) + 3 Minor issues; all fixed in one round and re-verified (RISK-0016).

**Frontend (Tasks 12-17):** Auth.js (NextAuth) v5, GitHub OAuth (`read:user public_repo` scope only), JWT session. `proxy.ts` (this Next.js version's rename of `middleware.ts` — confirmed via the bundled docs, not assumed from training data) protects every page. `lib/backend-client.ts` centralizes auth-awareness so all 13 pre-existing Route Handlers and every SSR `page.tsx` needed zero changes. Sign-in page, nav-sidebar avatar/sign-out, per-user SSE auth on the frontend side. Along the way: found and fixed a real bug in the plan's own reference code (`next-auth`'s `authorized` callback defaults to allow-all unless explicitly configured, silently defeating `proxy.ts`'s redirect — caught via live dev-server testing, not just static review); found `lucide-react`'s installed version removed the `Github` icon entirely (replaced with a local inline-SVG substitute); found and fixed 2 real, pre-existing-since-original-scaffold dependency vulnerabilities never previously caught (`sharp` HIGH-severity libvips CVEs, fixed via override; `@hono/node-server` moderate, accepted — RISK-0014/0015).

**Final whole-branch review** (all 18 tasks, opus): 0 Critical/Important, 2 Medium (undocumented shared-secret requirements between backend/frontend `.env` files; `auth.ts`'s sign-in callback didn't check the user-upsert call's response, so a misconfigured deploy would silently create no `User` row) + 2 Minor + 1 nit — all fixed in one round (RISK-0017). Backend: 69/69 tests, `pip-audit` clean. Frontend: `tsc`/`eslint`/`build` clean, 8/8 tests.

Governance updated: REQ-0015–REQ-0019 added to `REQUIREMENTS.md` (all `verified [C1]` except the live-OAuth piece of REQ-0015), RISK-0014–0017 logged, `docs/PROJECT_PLAN.md` Phase 2 marked done.

**Resume point for next session:** read this file first. The multi-tenant SaaS sub-scope is code-complete and reviewed clean but **not yet pushed to origin** and **not yet Gate-2-accepted** — next step is either (a) the Product Owner registers a real GitHub OAuth App and does a live sign-in verification, or (b) the Product Owner accepts the sub-scope on review evidence alone (matching how backend/frontend Gate 2s were granted) and authorizes pushing now, deferring live verification. No open `CHECKPOINTS.md` interrupts as of this log entry.
