# Agile-V Playbook — github-growth-bot

Operational guide for running this project under Agile-V going forward. Read this once per session after `STATE.md`.

## 1. Session Start Protocol

1. Read `STATE.md` first — current cycle, stage, status.
2. If `CHECKPOINTS.md` has any `PENDING` row, resolve it before starting new work (ask the human for the decision; don't silently proceed past an open gate).
3. Read only the current-stage's files — don't re-read archived `cycles/CN/` snapshots unless doing cross-cycle impact analysis.
4. Load `agile-v-core` always; load `agile-v-pipeline`/`agile-v-lifecycle`/`agile-v-compliance` on demand per task shape (already loaded and cached in this project's working context as of C1 bootstrap).

## 2. This Project's V-Model Mapping

| V-Model Stage | This project's equivalent |
|---|---|
| Stage 1: Requirements | `superpowers:brainstorming` → design spec in `docs/superpowers/specs/` (source of truth REQUIREMENTS.md points to) |
| Stage 2: Validation / Gate 1 | Human approves the design spec (informal today; use `AskUserQuestion`-driven approval + APPROVALS.md `GATE-XXXX Gate 1` entry going forward) |
| Stage 3: Synthesis | `superpowers:writing-plans` → task plan, then `superpowers:subagent-driven-development` (implementer + task-reviewer per task) |
| Stage 4: Verification | Final whole-branch review (dispatch on highest-tier model, per Directive 4 — Build Agent never verifies own work) |
| Stage 5: Acceptance / Gate 2 | `VALIDATION_SUMMARY.md` + `EVAL_RESULTS.md` PASS → Human approves → `APPROVALS.md` `GATE-XXXX Gate 2` entry closes the `CHECKPOINTS.md` interrupt |

**Why this mapping:** C1's backend was built with `superpowers` skills before Agile-V was adopted on this project. Rather than force a parallel/conflicting process, Agile-V governance wraps the same superpowers workflow — REQUIREMENTS.md/DECISION_LOG.md/RISK_REGISTER.md/CAPA_LOG.md/ATM.md are the traceability layer on top of it, not a replacement for it.

## 3. Domain Build Agents Available (of the 24 Agile-V skills installed)

Use these when a task calls for a specialized role rather than generic implementation:

- **requirement-architect** — converting new product intent → REQ-IDs (use for any new feature group from the deferred list: README suggestions, issue auto-response, release automation, community discovery).
- **logic-gatekeeper** — validating REQs for ambiguity/hardware constraints before build starts.
- **threat-modeler** — STRIDE analysis before REQ-writing, if a future cycle touches auth/secrets more deeply (e.g. if REQ-0013's API-key-only approach is revisited).
- **ux-spec-author** — for REQ-0010–0012's dashboard flows, before frontend implementation.
- **build-agent-python** — backend feature work (extends generic build-agent with this repo's Python/FastAPI conventions).
- **build-agent-js** / **build-agent-nestjs** — NOT this project's frontend stack (Next.js App Router, not NestJS); use build-agent-js generically or just `superpowers:subagent-driven-development` with Next.js-aware task briefs, matching how the backend was actually built.
- **test-designer** — designs verification suites from REQs only, before build, to avoid success-bias (recommended for the frontend cycle, since the backend's tests were written by the same implementer subagent as the code — acceptable for TDD but test-designer gives an independent angle for high-risk REQs).
- **red-team-verifier** — the formal Agile-V name for what this project's `task-reviewer`/`final-whole-branch-reviewer` subagents already do. Equivalent, already in use.
- **compliance-auditor** — reviews RISK_REGISTER.md/CAPA_LOG.md at cycle boundaries, flags overdue CAPAs (>2 cycles) and unlinked ATM entries.
- **release-manager** — for REQ-0009/REQ-0014's actual VPS/Vercel deployment, after Gate 2 approval only (POL-0006).
- **observability-planner** — worth invoking once the dashboard (REQ-0010) is live, to define metrics/alerts for the daily scheduler and LLM provider health.
- **discovery-analyst** — if future feature requests come in messy/unstructured, converts them to hypotheses before requirement-architect formalizes REQs.
- **documentation-agent** — repo-wide docs suite (ISO 9001/V-Model docs), on request only — not auto-triggered, this project intentionally avoids unrequested summary/doc files per the Product Owner's explicit standing preference.

## 4. Codebase Conventions to Preserve (for consistency across all future work)

**Backend (Python/FastAPI):**
- Pipeline stages: `class Stage: name: str; def run(self, ctx: PipelineContext) -> PipelineContext`. Never break this contract — REQ-0001's whole resilience model depends on every stage honoring it identically.
- Every new API endpoint: `dependencies=[Depends(require_api_key)]` (POL-0002), path avoids ad-blocker keywords (POL-0003).
- Any DB-writing code sharing a session with `PipelineRunner`: be aware of CAPA-0001's lesson — a stage's own exception handling must not assume the shared session is clean afterward.
- `LLMRouter` provider order and Groq allowlist are policy-locked (POL / REQ-0004) — changing them requires a CR (CHANGE_LOG.md), not a silent edit.

**Frontend (Next.js, when built):**
- SSR data-fetching directly in `page.tsx`; only `use client` code in `components/`.
- No `loading.tsx` files; targeted inline skeletons on data-bearing regions only.
- Parallel `Promise.all` prefetch, not sequential `await`s.
- Every title/label/button: `lucide-react` icon + semantic color.
- `lib/`/`hooks/`/`providers/`/`types/`/`components/ui/` shared structure; types generated from backend OpenAPI schema.
- Browser never holds the backend API key (REQ-0013) — Route Handlers proxy.

**Deployment:**
- Backend: Coolify app on existing Hetzner VPS, subdomain of `arnobmahmud.com`, Postgres as separate Coolify-managed service. Follow `docs/SUBDOMAIN_ARNOBMAHMUD_SETUP.md` / `docs/DOCKER_VPS_BACKEND_PLAYBOOK.md` exactly (existing project convention, don't reinvent).
- Frontend: Vercel, guardrails per `docs/VERCEL_PRODUCTION_GUARDRAILS.md`.
- Both require Gate 2 approval (POL-0006) before executing.

**General:**
- No artificial engagement (REQ-0000) — every new feature touching the GitHub API gets checked against this before merge.
- No unrequested summary/`.md` documentation files (Product Owner's standing preference, independent of Agile-V's own documentation norms — Agile-V's `.agile-v/*` files are the exception, since they were explicitly requested).
- Strict TypeScript, no dead code, no debug logs left behind, walkthrough-style code comments only where genuinely non-obvious.

## 5. Cycle Boundary Checklist (before opening C2 or archiving C1)

1. All C1 REQs (REQ-0000–REQ-0014) reach `verified` status.
2. `VALIDATION_SUMMARY.md` shows EvalGate PASS for the full cycle (not just backend sub-scope).
3. Compliance Auditor pass: no open Critical risks, no overdue CAPAs, ATM fully linked.
4. Gate 2 approval recorded in `APPROVALS.md`, `CHECKPOINTS.md` interrupt closed.
5. Snapshot living docs → `.agile-v/cycles/C1/` (frozen, read-only). `DECISION_LOG.md`/`CHANGE_LOG.md` are never archived (append-only timeline continues).
6. Open C2 in `STATE.md` for the next deferred feature group, or continue C1 if more work is identified within the same scope.
