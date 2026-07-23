# AI-Powered GitHub Growth Command Center - Next.js, FastAPI, PostgreSQL, Tailwind CSS Full-Stack Project

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Next.js](https://img.shields.io/badge/Next.js-16.2-black)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19.2-blue)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-316192)](https://www.postgresql.org/)
[![Launch with Diploi](https://diploi.com/launch.svg)](https://diploi.com/launch/arnobt78/github-growth-bot)

A personal / multi-tenant **GitHub growth command center**: track stars, forks, watchers, and traffic over time, benchmark against similar public repos, and get LLM-synthesized recommendations — with a hard rule against ever artificially inflating any GitHub metric.

This repository is **actively developed** (not a finished product). Backend pipelines, Next.js dashboard, Auth.js GitHub OAuth, draft-and-approve automation, and SSE live updates are in place; production Coolify/Vercel deployment is still open. Check [`.agile-v/STATE.md`](.agile-v/STATE.md) for the latest gate status.

---

## Table of contents

1. [Features](#features)
2. [Non-goals](#non-goals)
3. [Architecture](#architecture)
4. [Tech stack](#tech-stack)
5. [Project structure](#project-structure)
6. [How it works](#how-it-works)
7. [Frontend routes and UI](#frontend-routes-and-ui)
8. [API reference](#api-reference)
9. [Environment variables](#environment-variables)
10. [Local development](#local-development)
11. [Tests](#tests)
12. [Reusing patterns in other projects](#reusing-patterns-in-other-projects)
13. [Keywords glossary](#keywords-glossary)
14. [Further documentation](#further-documentation)
15. [Contributing / status](#contributing--status)
16. [Security](#security)
17. [License](#license)

---

## Features

| Area                     | What you get                                                                                                               |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **Repo tracking**        | Add/remove GitHub repos you own or care about; data is scoped per signed-in user.                                          |
| **Snapshots & insights** | Historical stars / forks / watchers and derived insight summaries (paths avoid ad-blocker keywords — see API section).     |
| **Benchmarks**           | Compare your repo against similar public repos.                                                                            |
| **Traffic**              | Referrers and popular paths from GitHub traffic APIs (when the token has access).                                          |
| **Recommendations**      | LLM-written, validator-checked growth suggestions; dismiss/update from the UI.                                             |
| **Pipeline runs**        | Trigger analytics runs on demand; view stage history. Daily scheduler also kicks runs off.                                 |
| **Drafts (automation)**  | Content/automation ideas land as **drafts** — humans approve or reject before anything external happens.                   |
| **Live UI**              | Server-Sent Events (SSE) invalidate TanStack Query caches so open tabs update without a full page refresh.                 |
| **Multi-provider LLM**   | Groq → Gemini → OpenRouter → Hugging Face → Cloudflare → Vercel AI Gateway, with graceful degradation if keys are missing. |
| **Auth**                 | GitHub OAuth via Auth.js (NextAuth v5); backend never trusts the browser with the service API key.                         |

---

## Non-goals

This project will **never**:

- Auto-star, auto-fork, or auto-follow
- Otherwise programmatically inflate GitHub metrics

That violates GitHub’s Acceptable Use Policies and is out of product scope. Suggestions stay organic (docs, discoverability, community).

---

## Architecture

```text
GitHub API
    │
    ▼
Extractor → Preprocessor → Analyzer → Optimizer → Synthesizer → Validator → Assembler
                                                              │
                                              LLMRouter (multi-provider fallback)
                                                              │
                                                         Postgres
                                                              │
                                              FastAPI (REST + SSE)
                                                              │
                         Next.js Route Handlers (BFF)  ←── API_KEY + internal user token
                                                              │
                                                    Browser (no backend API key)
```

**Analytics pipeline** (per tracked repo): seven isolated stages. One stage failing does not wipe earlier work.

**Content pipeline** (when enabled): parallel seven-stage path that writes `Draft` rows (`pipeline_kind="content"`) for human approval.

**Frontend BFF:** the browser calls `/api/...` on Next.js. Route Handlers call FastAPI with `Authorization: Bearer <API_KEY>` and an HMAC-signed per-user token. Secrets stay on the server.

```mermaid
flowchart LR
  Browser --> NextBFF[Next_Route_Handlers]
  NextBFF --> FastAPI
  FastAPI --> Postgres
  FastAPI --> GitHubAPI[GitHub_API]
  FastAPI --> LLMRouter
  FastAPI -->|SSE| NextBFF
```

---

## Tech stack

### Backend

| Piece                     | Role (beginner view)                                                          |
| ------------------------- | ----------------------------------------------------------------------------- |
| **Python 3.12 + FastAPI** | Fast HTTP API framework; auto OpenAPI docs at `/docs` when the server runs.   |
| **SQLAlchemy + Alembic**  | ORM for models; Alembic applies database migrations (`alembic upgrade head`). |
| **PostgreSQL**            | Primary datastore for users, repos, snapshots, runs, recommendations, drafts. |
| **httpx**                 | Async/sync HTTP client for GitHub and LLM providers.                          |
| **APScheduler**           | In-process scheduler for daily analytics (+ offset content) runs.             |
| **sse-starlette**         | Streams Server-Sent Events to the frontend.                                   |
| **cryptography (Fernet)** | Encrypts GitHub OAuth tokens at rest.                                         |
| **slowapi**               | Rate limits sensitive POSTs (e.g. add repo, trigger runs).                    |

### Frontend

| Piece                                 | Role (beginner view)                                      |
| ------------------------------------- | --------------------------------------------------------- |
| **Next.js 16 App Router**             | React framework; Server Components + Route Handlers.      |
| **React 19 + TypeScript**             | UI + static typing.                                       |
| **Auth.js (next-auth v5)**            | GitHub OAuth sign-in and session cookies.                 |
| **TanStack Query**                    | Client cache for API data; mutations + invalidation.      |
| **Tailwind CSS 4 + shadcn / Base UI** | Styling and accessible primitives.                        |
| **lucide-react**                      | Icons on titles/actions.                                  |
| **Recharts**                          | Trend charts / sparklines.                                |
| **Sonner**                            | Toast notifications.                                      |
| **openapi-typescript**                | Generates `frontend/types/api.d.ts` from backend OpenAPI. |

### Deployment targets (planned)

- Backend → Coolify on a VPS + managed Postgres
- Frontend → Vercel

Production deploy is **not** assumed live in this README.

---

## Project structure

```text
github-bot/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry, health, lifespan/scheduler
│   │   ├── api/                 # Routers: repos, insights, runs, drafts, …
│   │   ├── pipeline/            # Stage runners (analytics + content)
│   │   ├── models.py            # SQLAlchemy tables
│   │   ├── llm_router.py        # Multi-provider LLM fallback
│   │   └── deps.py              # Auth dependencies
│   ├── alembic/                 # Migrations
│   ├── tests/                   # pytest
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/                     # Pages + Route Handlers (App Router)
│   ├── components/              # Feature UI + components/ui
│   ├── hooks/                   # TanStack Query hooks + SSE
│   ├── providers/               # Query, theme, live events
│   ├── lib/                     # API client, query keys, auth helpers
│   ├── types/                   # OpenAPI-generated types
│   ├── auth.ts                  # Auth.js config
│   ├── .env.local.example
│   └── package.json
├── docs/                        # Plans, walkthrough, engineering playbook
├── .agile-v/                    # Requirements, gates, decisions
├── CLAUDE.md                    # Agent instructions
├── SECURITY.md                  # Vulnerability reporting
├── LICENSE
└── README.md
```

---

## How it works

### 1. Sign-in

1. User visits `/sign-in` and authenticates with GitHub (OAuth App).
2. Auth.js stores a session on the frontend.
3. On first login, the frontend provisions the user via `POST /users/upsert` (API key only).
4. Later API calls include an **internal user token** so the backend scopes data to that `User`.

### 2. Track repos and run the pipeline

1. User adds a repo in Settings / Overview.
2. `POST /runs` starts the analytics pipeline (or the daily scheduler does).
3. Stages run in order; each stage is isolated — failures are recorded per `stage_run`.
4. Snapshots, benchmarks, traffic rows, and recommendations land in Postgres.
5. SSE event `run_completed` (and related events) tell open browsers to invalidate React Query keys.

### 3. Drafts (approve before acting)

Anything that would eventually post or act externally is stored as a **Draft**. Humans `PATCH` to `approved` or `rejected`. No silent external side effects.

### 4. Instant UI updates

```text
Mutation or pipeline event
        → backend publishes SSE
        → frontend useLiveEvents invalidates query keys
        → lists / detail / badges refetch
        → no full page reload
```

Engineering standards for SSR, prefetch, and cache sync live in [`docs/PROJECT_IDEA.md`](docs/PROJECT_IDEA.md).

### Pipeline stage sketch (backend)

```python
class Stage:
    name: str
    def run(self, ctx: PipelineContext) -> PipelineContext:
        ...
```

Analytics order: `extractor` → `preprocessor` → `analyzer` → `optimizer` → `synthesizer` → `validator` → `assembler`.

---

## Frontend routes and UI

| Route              | Purpose                                                               |
| ------------------ | --------------------------------------------------------------------- |
| `/`                | Overview: tracked repos, deltas, sparklines                           |
| `/repos/[id]`      | Detail: trends, benchmarks, referrers, popular paths, recommendations |
| `/recommendations` | Inbox of growth suggestions                                           |
| `/drafts`          | Draft-and-approve inbox                                               |
| `/runs`            | Pipeline run history + trigger runs                                   |
| `/settings`        | Manage repos + LLM provider status                                    |
| `/sign-in`         | GitHub OAuth                                                          |

**Reuse inside this app**

- Pages are thin Server Components that prefetch + `HydrationBoundary`.
- Interactive pieces live under `components/<feature>/` as `"use client"` only when needed.
- Data access: `hooks/use-*.ts` + `lib/query-keys.ts` + `lib/api.ts`.
- UI primitives: `components/ui/` (button, card, table, skeleton, …).
- Live sync: `providers/live-events-provider.tsx` → `hooks/use-live-events.ts`.

**Pattern for a new list page**

1. Add backend endpoint + OpenAPI type.
2. Extend `queryKeys` and `lib/api`.
3. Add a Route Handler under `app/api/...`.
4. Prefetch in `page.tsx` with `Promise.all` when multiple queries.
5. Build a client component that skeletons **data slots only** (keep titles visible).
6. On mutation, invalidate every related key; map any new SSE event in `use-live-events`.

---

## API reference

Base URL (local): `http://localhost:8000`

**Auth**

- Almost every route: `Authorization: Bearer <API_KEY>`
- User-scoped routes also need the internal user token header (minted by the frontend BFF).
- Exception: `GET /api/health` (no API key).
- Exception: `POST /users/upsert` (API key only — used at sign-in provisioning).

**Naming:** paths use `insights` / `snapshots` / `benchmarks` / `runs` — **not** words like `analytics` / `metrics` (ad-blocker filters).

| Method   | Path                        | Notes                     |
| -------- | --------------------------- | ------------------------- |
| `GET`    | `/api/health`               | Liveness                  |
| `GET`    | `/repos`                    | List tracked repos        |
| `POST`   | `/repos`                    | Add repo (rate limited)   |
| `GET`    | `/repos/{id}`               | Repo detail               |
| `DELETE` | `/repos/{id}`               | Remove repo               |
| `GET`    | `/repos/{id}/snapshots`     | Time series               |
| `GET`    | `/repos/{id}/insights`      | Derived insights          |
| `GET`    | `/repos/{id}/benchmarks`    | Peer comparison           |
| `GET`    | `/repos/{id}/referrers`     | Traffic referrers         |
| `GET`    | `/repos/{id}/popular-paths` | Popular content paths     |
| `GET`    | `/recommendations`          | List recommendations      |
| `PATCH`  | `/recommendations/{id}`     | Update / dismiss          |
| `GET`    | `/drafts`                   | List drafts               |
| `PATCH`  | `/drafts/{id}`              | `approved` \| `rejected`  |
| `GET`    | `/runs`                     | List pipeline runs        |
| `POST`   | `/runs`                     | Start analytics run (202) |
| `POST`   | `/runs/content`             | Start content run (202)   |
| `GET`    | `/runs/{id}/stages`         | Per-stage status          |
| `GET`    | `/providers/status`         | LLM provider readiness    |
| `POST`   | `/users/upsert`             | Provision user from OAuth |
| `GET`    | `/events`                   | SSE stream                |

Interactive docs (when server is up): `http://localhost:8000/docs`

Example health check:

```bash
curl -s http://localhost:8000/api/health
```

---

## Environment variables

You **do need** env files for a real local run (database, API key, OAuth, encryption, HMAC).  
**LLM provider keys are optional** — metrics/snapshots still work; AI recommendations degrade gracefully if every LLM key is empty.

Copy examples, never commit real secrets:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

### Backend — `backend/.env`

| Variable                                       | Required?                         | How to get / set                                                                                                                   |
| ---------------------------------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                                 | **Yes**                           | Postgres URL, e.g. `postgresql+psycopg://user:password@localhost:5432/github_growth_bot`. Create DB: `createdb github_growth_bot`. |
| `API_KEY`                                      | **Yes**                           | Shared service key. `openssl rand -base64 32`. **Must match** frontend `BACKEND_API_KEY`.                                          |
| `TOKEN_ENCRYPTION_KEY`                         | **Yes** (for OAuth token storage) | Fernet key only: `.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`             |
| `INTERNAL_AUTH_SECRET`                         | **Yes**                           | HMAC secret. `openssl rand -base64 32`. **Must match** frontend `INTERNAL_AUTH_SECRET`.                                            |
| `CORS_ORIGINS`                                 | **Yes** for browser/dev           | JSON array, e.g. `["http://localhost:3000"]`.                                                                                      |
| `GROQ_API_KEY`                                 | Optional                          | [Groq console](https://console.groq.com/keys)                                                                                      |
| `GEMINI_API_KEY`                               | Optional                          | [Google AI Studio](https://aistudio.google.com/app/apikey)                                                                         |
| `OPENROUTER_API_KEY`                           | Optional                          | [OpenRouter](https://openrouter.ai/keys)                                                                                           |
| `HUGGINGFACE_API_KEY`                          | Optional                          | [HF tokens](https://huggingface.co/settings/tokens)                                                                                |
| `CLOUDFLARE_API_KEY` / `CLOUDFLARE_ACCOUNT_ID` | Optional                          | Cloudflare dashboard                                                                                                               |
| `VERCEL_AI_GATEWAY_KEY`                        | Optional                          | Vercel AI Gateway docs                                                                                                             |

> Older single-user setups sometimes used a raw `GITHUB_TOKEN`. Multi-tenant mode stores per-user OAuth tokens (encrypted). Prefer GitHub OAuth via the frontend for full product behavior.

### Frontend — `frontend/.env.local`

| Variable               | Required?           | How to get / set                                                                               |
| ---------------------- | ------------------- | ---------------------------------------------------------------------------------------------- |
| `BACKEND_URL`          | **Yes**             | `http://localhost:8000` locally.                                                               |
| `BACKEND_API_KEY`      | **Yes**             | Same value as backend `API_KEY`.                                                               |
| `AUTH_SECRET`          | **Yes**             | Auth.js cookie encryption. `openssl rand -base64 32` (frontend-only).                          |
| `AUTH_GITHUB_ID`       | **Yes** for sign-in | GitHub → Settings → Developer settings → [OAuth Apps](https://github.com/settings/developers). |
| `AUTH_GITHUB_SECRET`   | **Yes** for sign-in | Generated once on the OAuth App page — copy immediately.                                       |
| `INTERNAL_AUTH_SECRET` | **Yes**             | Same value as backend `INTERNAL_AUTH_SECRET`.                                                  |

**GitHub OAuth App settings (local)**

- Homepage URL: `http://localhost:3000`
- Authorization callback URL: `http://localhost:3000/api/auth/callback/github`

GitHub allows **one callback URL per OAuth App** — use a separate OAuth App for production.

Shared secret checklist:

```text
backend API_KEY          ==  frontend BACKEND_API_KEY
backend INTERNAL_AUTH_SECRET  ==  frontend INTERNAL_AUTH_SECRET
```

A mismatch usually shows up as silent **401**s with little explanation.

---

## Local development

### Prerequisites

- Python 3.12+
- Node.js 20+ (recommended)
- PostgreSQL running locally
- GitHub OAuth App credentials (for UI sign-in)

### Terminal 1 — backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill required vars (see above)
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Check: [http://localhost:8000/api/health](http://localhost:8000/api/health) and [http://localhost:8000/docs](http://localhost:8000/docs).

### Terminal 2 — frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill required vars
npm run dev
```

Open: [http://localhost:3000](http://localhost:3000)

### Suggested smoke path

1. Health endpoint OK
2. Sign in with GitHub
3. Add a repo in Settings
4. Trigger a run on `/runs`
5. Watch Overview / Recommendations update (SSE)

Optional: regenerate OpenAPI types after backend schema changes:

```bash
cd frontend
npm run generate:types   # backend must be on :8000
```

---

## Tests

```bash
# Backend
cd backend
.venv/bin/python -m pytest -v

# Frontend
cd frontend
npm test
npm run lint
npx tsc --noEmit
```

---

## Reusing patterns in other projects

| Pattern                                     | Where to look                                 | Why reuse it                                     |
| ------------------------------------------- | --------------------------------------------- | ------------------------------------------------ |
| BFF proxy (browser never holds service key) | `frontend/app/api/*`, `lib/backend-client.ts` | Safer than calling private APIs from the browser |
| Stable query keys                           | `frontend/lib/query-keys.ts`                  | One place to invalidate after CRUD               |
| SSE → cache invalidation                    | `hooks/use-live-events.ts`                    | Multi-tab freshness without polling              |
| Shell-first SSR pages                       | `frontend/app/**/page.tsx`                    | Instant chrome + data-slot skeletons             |
| Isolated pipeline stages                    | `backend/app/pipeline/`                       | Failure isolation + testability                  |
| LLM provider fallback                       | `backend/app/llm_router.py`                   | Survive rate limits / outages                    |
| Draft-and-approve                           | `backend/app/api/drafts.py`                   | Human gate before external side effects          |

Portable engineering rules (Next **and** Vite SPA): [`docs/PROJECT_IDEA.md`](docs/PROJECT_IDEA.md).

Example invalidation idea after a mutation:

```ts
await queryClient.invalidateQueries({ queryKey: queryKeys.repos.all });
await queryClient.invalidateQueries({
  queryKey: queryKeys.recommendations.all,
});
// SSE may invalidate the same keys in other open tabs
```

---

## Keywords glossary

| Term                      | Meaning                                                                                      |
| ------------------------- | -------------------------------------------------------------------------------------------- |
| **BFF**                   | Backend-for-frontend — Next Route Handlers that talk to FastAPI on the server.               |
| **SSR**                   | Server-side rendering — HTML prepared on the server before the browser paints.               |
| **RSC**                   | React Server Components — components that run on the server by default.                      |
| **Hydration**             | Attaching React interactivity to server-rendered HTML; TanStack `dehydrate` seeds the cache. |
| **SSE**                   | Server-Sent Events — one-way live stream from server to browser.                             |
| **OpenAPI**               | Machine-readable API contract; used to generate TypeScript types.                            |
| **Alembic**               | Database migration tool for SQLAlchemy.                                                      |
| **Fernet**                | Symmetric encryption helper used for tokens at rest.                                         |
| **Draft-and-approve**     | Write a proposal row first; human approves before external action.                           |
| **LLMRouter**             | Tries multiple AI providers in order until one succeeds.                                     |
| **Ad-blocker-safe paths** | Avoid URL segments that common blockers filter (`analytics`, `metrics`, …).                  |

---

## Further documentation

| Doc                                                          | Contents                                  |
| ------------------------------------------------------------ | ----------------------------------------- |
| [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)               | Phased roadmap                            |
| [`docs/PROJECT_WALKTHROUGH.md`](docs/PROJECT_WALKTHROUGH.md) | End-to-end product walkthrough            |
| [`docs/PROJECT_IDEA.md`](docs/PROJECT_IDEA.md)               | Global engineering playbook for agents    |
| [`CLAUDE.md`](CLAUDE.md)                                     | Conventions for AI coding agents          |
| [`docs/superpowers/specs/`](docs/superpowers/specs/)         | Design specs                              |
| [`docs/superpowers/plans/`](docs/superpowers/plans/)         | Implementation plans                      |
| [`.agile-v/`](.agile-v/)                                     | Requirements, approvals, risks, decisions |
| [`SECURITY.md`](SECURITY.md)                                 | Private vulnerability reporting           |

---

## Contributing / status

- Treat this as a **work-in-progress** learning and production-bound codebase.
- Read [`.agile-v/STATE.md`](.agile-v/STATE.md) before large changes.
- Prefer small PRs; keep secrets out of git; follow `CLAUDE.md` hard constraints.
- Ideas and polite issues/PRs are welcome once you can run the stack locally.

---

## Security

Please **do not** open public GitHub issues for security vulnerabilities.

See [`SECURITY.md`](SECURITY.md) for how to report privately to **<contact@arnobmahmud.com>**.

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT). Feel free to use, modify, and distribute the code as per the terms of the license.

---

## Happy Coding! 🎉

This is an **open-source project** — feel free to use, enhance, and extend it further!

If you have any questions or want to share your work, reach out via GitHub or my portfolio at [https://www.arnobmahmud.com](https://www.arnobmahmud.com).
