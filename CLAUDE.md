# CLAUDE.md

Instructions for Claude Code (or any AI agent) working in this repository.

## What this project is

A multi-tenant GitHub account analytics/growth SaaS, growing into a draft-and-approve automation platform (Phase 4). Full context: [`README.md`](README.md), [`docs/PROJECT_WALKTHROUGH.md`](docs/PROJECT_WALKTHROUGH.md), [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md).

## Start every session here

1. Read `.agile-v/STATE.md` first — it says exactly what's done, what's in progress, and what's blocked.
2. If `.agile-v/CHECKPOINTS.md` has a `PENDING` row, that's an open decision waiting on the human (Arnob Mahmud) — don't build past it silently.
3. `.agile-v/PLAYBOOK.md` explains how this project maps onto the Agile-V governance framework and which specialized skills/agents to reach for.

## Hard constraints (never violate these)

- **No artificial engagement.** Never add code that auto-stars, auto-forks, auto-follows, or otherwise inflates a GitHub metric programmatically. See `.agile-v/REQUIREMENTS.md` REQ-0000 and `POLICY.yaml` POL-0001.
- **Every backend endpoint except `GET /api/health` requires `Authorization: Bearer <API_KEY>`.** New routers must include `dependencies=[Depends(require_api_key)]`.
- **Endpoint paths never contain** `analytics`, `analysis`, `tracking`, `performance`, or `metrics` (ad-blocker filter avoidance) — use `insights`/`snapshots`/`benchmarks`/`runs` instead.
- **No secrets committed.** `.env.example` holds placeholders only.
- **Build Agent does not verify its own work.** Every non-trivial change gets reviewed by a fresh subagent with no shared context before it's considered done (Red Team Protocol).

## Architecture conventions to follow

**Backend (`backend/`, Python/FastAPI):**

- Pipeline stages implement `class Stage: name: str; def run(self, ctx: PipelineContext) -> PipelineContext`. This contract is load-bearing — `PipelineRunner` isolates each stage's exceptions per-stage; breaking the interface breaks that resilience model.
- Any code sharing a DB session with `PipelineRunner` must not assume the session is clean after an exception — see `.agile-v/CAPA_LOG.md` CAPA-0001 for why (`self.db.rollback()` is required in the runner's exception handler; don't remove it).
- `LLMRouter`'s provider order and Groq model allowlist (`app/llm_router.py`) are policy-locked — changing them needs a Change Request (`.agile-v/CHANGE_LOG.md`), not a silent edit.
- Tests live in `backend/tests/`, one file per module being tested, TDD style (failing test → implementation → passing test). Full suite: `.venv/bin/python -m pytest -v`. Should stay at 100% pass with pristine output (no stray warnings).
- Every resource is per-user scoped (`user_id` FK, filtered in the query, never fetch-then-check) via `app/deps.py::require_user`. Cross-user access to an existing resource returns 404, never 403 (no existence leak). New endpoints must give every response a Pydantic `response_model` — never a bare `list[dict]` — so the frontend's OpenAPI-generated types stay complete.
- Draft-and-approve pattern (`app/api/drafts.py`, Phase 4A+): any feature that acts externally (posts, replies, publishes) writes a `Draft` row instead of acting directly; nothing external happens until a human approves it via `PATCH /drafts/{id}`.

**Frontend (`frontend/` — Next.js App Router, TypeScript):**

- Engineering standards for SSR, prefetch/hydrate, TanStack Query, SSE, UI, and agent reuse rules: [`docs/PROJECT_IDEA.md`](docs/PROJECT_IDEA.md).
- SSR data-fetching goes directly in `page.tsx` (Server Components); only genuinely interactive code goes in `use client` components.
- No `loading.tsx` files. Page shell (headers, labels, icons, buttons, card frames) renders instantly; only data-bearing regions show inline skeletons matching the real content's dimensions.
- Independent server prefetches run in parallel (`Promise.all`), never sequential `await`s.
- Every title/subtitle/label/button carries a `lucide-react` icon with semantic color tied to what it represents.
- Shared structure: `lib/`, `hooks/`, `providers/`, `types/` (generated from the backend's OpenAPI schema — never hand-duplicate), `components/ui/`.
- The browser never holds the backend's API key — Next.js Route Handlers proxy every backend call server-side.
- CRUD mutations use TanStack Query + SSE-driven cache invalidation so every open tab updates instantly without a page refresh.

**Deployment:**

- Backend → Coolify app on the existing Hetzner VPS, subdomain of `arnobmahmud.com`, Postgres as a separate Coolify-managed service. Follow `docs/DOCKER_VPS_BACKEND_PLAYBOOK.md` / `docs/SUBDOMAIN_ARNOBMAHMUD_SETUP.md` exactly — these are the user's own established, battle-tested conventions from other projects, don't reinvent them.
- Frontend → Vercel, guardrails per `docs/VERCEL_PRODUCTION_GUARDRAILS.md`.
- Never deploy without Human Gate 2 approval logged in `.agile-v/APPROVALS.md` (POL-0006).

## Process conventions

- No unrequested summary/changelog `.md` files. Documentation happens in code comments (explain _why_, not _what_) and in the explicitly-requested docs listed in `README.md`.
- Don't create new abstractions, backwards-compat shims, or speculative flexibility beyond what's asked — YAGNI throughout.
- Dependencies stay current and vulnerability-free before any milestone is called done.
- When implementing multi-step work, prefer the pattern already used for the backend: `superpowers:brainstorming` → design spec → `superpowers:writing-plans` → implementation plan → `superpowers:subagent-driven-development` (fresh implementer + reviewer subagent per task, final whole-branch review at the end).

## Where things are

- Design specs: `docs/superpowers/specs/`
- Implementation plans: `docs/superpowers/plans/`
- Governance/traceability: `.agile-v/` (see `PLAYBOOK.md` for the full file index and what each one is for)
- Backend source: `backend/app/`
- Backend tests: `backend/tests/`
- The user's personal cross-project reference docs (VPS/Coolify/Vercel/LLM-fallback/image-component patterns) live in `docs/*.md` — read these before reinventing a pattern they've already solved elsewhere.
