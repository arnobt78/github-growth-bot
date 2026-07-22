# GitHub Growth Bot

A personal, account-wide GitHub "command center": a multi-agent analytics pipeline that tracks your repos' stars/forks/watchers/traffic over time, benchmarks them against similar public repos, and surfaces LLM-synthesized, hallucination-checked recommendations — all organic growth tooling, with a hard rule against ever artificially inflating any metric.

## Status

**Phase 1 backend: done.** 30/30 tests passing, independently reviewed. **Phase 1 frontend: not started.** See [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) for the full roadmap and [`docs/PROJECT_WALKTHROUGH.md`](docs/PROJECT_WALKTHROUGH.md) for how it all works.

This project is governed by [Agile-V](.agile-v/PLAYBOOK.md) for requirement traceability, review discipline, and decision logging — see `.agile-v/STATE.md` for exactly where things stand right now.

## Architecture

```bash
GitHub API ──▶ Extractor ──▶ Preprocessor ──▶ Analyzer ──▶ Optimizer ──▶ Synthesizer ──▶ Validator ──▶ Assembler ──▶ Postgres
                                                                              │
                                                              Groq → Gemini → OpenRouter → HF → Cloudflare → Vercel AI Gateway
                                                                     (multi-provider LLM fallback router)
                                                                              │
                                                              FastAPI (REST + SSE) ──▶ Next.js dashboard (planned)
```

A 7-stage pipeline runs daily (and on-demand) per tracked repo. Each stage is isolated — one stage failing never crashes the run or loses data already gathered. See `docs/superpowers/specs/2026-07-20-github-growth-bot-design.md` for the full design rationale.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy + Alembic, Postgres, httpx, APScheduler
- **Frontend (planned):** Next.js App Router, TypeScript, TanStack Query, Tailwind + shadcn/ui, Server-Sent Events for instant cache invalidation
- **Deployment:** Backend on Coolify (Hetzner VPS), frontend on Vercel

## Quick Start (backend)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, API_KEY, GITHUB_TOKEN, at least one LLM provider key
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 3000
```

Run tests: `.venv/bin/python -m pytest -v` (30/30 passing).

## Non-Goal

This project will never auto-star, auto-fork, auto-follow, or otherwise artificially inflate any GitHub metric. That's against GitHub's Acceptable Use Policies and isn't what this is for — every growth suggestion here is organic (better docs, better discoverability, better community engagement).

## Docs

- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) — phased roadmap, what's done vs. next
- [`docs/PROJECT_WALKTHROUGH.md`](docs/PROJECT_WALKTHROUGH.md) — how the system actually works, end to end
- [`docs/superpowers/specs/`](docs/superpowers/specs/) — design specs
- [`docs/superpowers/plans/`](docs/superpowers/plans/) — implementation plans
- [`.agile-v/`](.agile-v/) — requirements traceability, decisions, risk register, validation records
- [`CLAUDE.md`](CLAUDE.md) — instructions for AI coding agents working in this repo
