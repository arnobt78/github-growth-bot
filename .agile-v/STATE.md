# Project State

**Project:** github-growth-bot
**Current Cycle:** C1
**Bootstrapped:** 2026-07-20 (retroactive — backend was built via `superpowers` skills before Agile-V adoption; see PLAYBOOK.md §2 for how the two map together)

## Current Position in the V

**Backend sub-scope (REQ-0000–REQ-0009):** Stage 5 (Acceptance) complete — Gate 2 approved (GATE-0001, 2026-07-20). Deployment (RISK-0005/0006 pre-deploy actions, Gate 2's deployment condition per POL-0006) still open, separate from this acceptance.
**Frontend sub-scope (REQ-0010–REQ-0014):** Stage 5 (Acceptance) complete — built (20 tasks, subagent-driven), final whole-branch review clean, escalated backend cascade-delete bug found and fixed, post-plan deep audit found and closed one dependency-CVE gap (RISK-0013), Gate 2 approved (GATE-0002, 2026-07-21). Deployment (Vercel) itself still open, separate from this acceptance, per POL-0006.

## Open Items Requiring Attention

1. ~~INT-0001 (CHECKPOINTS.md) — PENDING.~~ **CLOSED 2026-07-20 — Approved.** See `APPROVALS.md` GATE-0001. Backend sub-scope of C1 formally accepted.
2. ~~INT-0002 (CHECKPOINTS.md) — PENDING.~~ **CLOSED 2026-07-21 — Approved.** See `APPROVALS.md` GATE-0002. Frontend sub-scope of C1 formally accepted.
3. **Deployment not executed (either surface).** Backend: RISK-0005 (CORS env var) and RISK-0006 (manual Alembic migration step) are open pre-deploy actions. Frontend: Vercel deploy itself hasn't run. Both need their own Gate 2 evidence per POL-0006 before any Coolify/Vercel release action.
4. **Remote configured and current.** `https://github.com/arnobt78/github-growth-bot`, branch `main`. Local commits are pushed through the frontend build + CVE fix as of this session (see Session Log below for exact SHA).

## File Integrity

Git-tracked, working tree clean as of last check (verify with `git status` at next session start per Directive 8/`agile-v-compliance` File Integrity rule).

## Next Action

Both C1 sub-scopes (backend, frontend) are Gate 2-accepted. Remaining work is deployment-only: resolve RISK-0005/RISK-0006 and execute the VPS deploy (backend), then the Vercel deploy (frontend) — each needs its own Gate 2 evidence per POL-0006 before the deploy skill/agent runs.

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

**Resume point for next session:** read this file first. Both C1 sub-scopes are Gate 2-accepted; remaining work is deployment only (see Next Action above).
