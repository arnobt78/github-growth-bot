# Multi-Tenant SaaS Foundation — Design Spec

Approved by Product Owner (Arnob Mahmud) during brainstorming, 2026-07-21. Full narrative: `docs/PROJECT_PLAN.md` Phase 2. Architecture-concepts rationale (which of the 12 in `docs/PROJECT_IDEA.md` apply, and why the rest don't yet): same file, same section.

## 1. Problem

The app is single-tenant today: one shared static `API_KEY` gates every backend route, and there is exactly one global list of tracked repos. To become a real product (and a credible portfolio SaaS showcase), anyone should be able to sign in with their own GitHub account and track their own repos, fully isolated from every other user's data — with no reduction in the existing security/performance bar.

## 2. Auth

- **Auth.js (NextAuth v5)**, GitHub OAuth provider only. Public-repo scope only (`read:user` + default public read — no `repo` scope) for v1: lower liability, and growth metrics (stars, forks, traffic, referrers) are inherently public-facing signals anyway.
- **JWT session strategy** — no NextAuth database adapter. Next.js never gets a direct Postgres connection; the "backend owns the DB" rule from the existing architecture is unchanged.
- On first sign-in, Auth.js's `signIn`/`jwt` callbacks call a new backend endpoint `POST /users/upsert` (via the existing server-only `lib/api.ts`) with the GitHub profile + OAuth access token. The backend creates/updates the `User` row, encrypting the token before it touches the DB.
- Middleware protects every authenticated route (`/`, `/repos/*`, `/recommendations`, `/runs`, `/settings`); unauthenticated visitors land on a public sign-in page.

## 3. Data model

New `User` table (`backend/app/models.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `github_id` | unique, indexed | GitHub's numeric user id — the durable identity, not username (usernames change) |
| `username` | string | display only |
| `avatar_url` | string | for `SafeImage` |
| `email` | string, nullable | GitHub may not expose it |
| `access_token_encrypted` | string | Fernet-encrypted, `TOKEN_ENCRYPTION_KEY` env var, never returned by any API response or logged |
| `plan` | string, default `"free"` | schema-ready for future billing, no billing logic in v1 |
| `max_tracked_repos` | int, default `5` | enforced on `POST /repos` |
| `created_at` | datetime | |

Every existing table gains `user_id` FK, `ondelete="CASCADE"`: `Repo`, `Snapshot`, `BenchmarkRepo`, `Referrer`, `PopularPath`, `Recommendation`, `PipelineRun`, `StageRun`. One Alembic migration. A one-time backfill (script, not manual SQL) assigns pre-existing rows to the Product Owner's own account, matched by `github_id` on first post-deploy login — no history lost.

## 4. Request authorization — defense in depth

```
Browser → Next.js Route Handler → Backend
```

1. Route Handler calls `auth()` (Auth.js server helper). No session → 401, backend never called.
2. Route Handler mints a short-lived (60s) HMAC-signed internal token: `{sub: github_id, exp}`, signed with a new `INTERNAL_AUTH_SECRET` env var (shared only between the Next.js and backend deploys, never exposed to the browser).
3. Backend's existing `require_api_key` dependency is unchanged — still proves "this request came from our trusted Next.js layer."
4. New `require_user` dependency verifies the signed token's signature + expiry, extracts `github_id`, loads the matching `User` row (404 if none — never leaks whether a `github_id` exists).
5. Every repo-scoped query (`repos`, `snapshots`, `insights`, `benchmarks`, `referrers`, `popular-paths`, `recommendations`, `runs`, `run stages`) filters by that `user_id` at the query layer. Fetching another user's resource by id returns 404, not 403 (never confirm existence to an unauthorized caller).

A hole in any single layer (a misconfigured network boundary, a forgotten header) still leaves the others standing — the plain-header approach considered during brainstorming was rejected specifically because it's spoofable if the backend port is ever reachable directly; the signed token isn't.

## 5. Pipeline changes

- `GitHubClient` takes a per-user decrypted access token instead of one global env-var token. Each pipeline run for a repo authenticates as that repo's owning user — this also gives every user their own 5,000/hr GitHub rate-limit budget instead of one shared budget.
- The daily APScheduler job keeps its existing shape (iterate all `Repo` rows) — it now resolves each repo's owning user's token before extraction, nothing else about its control flow changes.
- Manual trigger (`POST /runs`) moves off the synchronous request path onto FastAPI `BackgroundTasks` — immediate `202`, the run happens in the background, and it only runs the calling user's own tracked repos (Message Queue concept, `PROJECT_PLAN.md` Phase 2 table).
- Circuit breaker extension: a user's expired/revoked GitHub token stops that user's run early (`PipelineRun` marked "needs reauth") instead of retry-hammering a dead token — isolated per-user, same isolation principle as the existing per-stage `PipelineRunner` design.
- New in-memory TTL cache in `GitHubClient` for the benchmark/similar-repo search call specifically (the most rate-limit-expensive call in the pipeline) — Caching concept, `PROJECT_PLAN.md` Phase 2 table.

## 6. SSE (`/events`) — per-user scoping

The existing `EventBroadcaster` currently fans out every event to every connected client. That's now a real data leak (User B would see User A's `repo_added`/`run_completed` events) — every published event gains a `user_id`, and `GET /events` only forwards events matching the connected client's own (verified) identity. Pub-Sub concept, `PROJECT_PLAN.md` Phase 2 table.

## 7. Rate limiting

`slowapi`, per-user and per-IP, on `POST /repos` and `POST /runs`. In-memory store — sufficient for the current single-container deploy; Redis-backed only becomes necessary if this ever runs multi-instance.

## 8. Testing

TDD throughout, matching existing project convention:

- `require_user`: valid token → correct user loaded; expired/invalid/missing token → 401.
- Row-scoping: user A cannot read/mutate user B's repo/recommendation/run by id (404, not 403).
- Token encryption round-trip: encrypt → store → decrypt → matches original.
- SSE per-user scoping: two connected clients, one event published for user A, only user A's connection receives it.
- Migration/backfill: existing pre-migration rows correctly assigned to the Product Owner's account; no rows lost, no rows duplicated.
- Rate limiter: exceeding the per-user limit on `POST /repos`/`POST /runs` returns 429, not 500 or a silent pass-through.

## 9. Risk checked during spec review

GitHub's Traffic API (`/repos/{owner}/{repo}/traffic/views|clones`, referrers, popular paths — the data behind REQ-0002/REQ-0003) requires push access to the repo. GitHub's own scope docs confirm `public_repo` grants read/write (push-level) access for public repositories specifically — matching what the Traffic API requires — so `public_repo` scope (§2) should be sufficient for a user's own public repos, no `repo` scope needed. The implementation plan's first task still does one live API call against a real public repo to confirm this before the rest of the pipeline work depends on it, since GitHub's docs don't spell this endpoint/scope interaction out explicitly.

## 10. Explicitly out of scope for this phase

Billing/Stripe (schema-ready only, see `plan`/`max_tracked_repos`), private-repo support, visual/portfolio polish (Phase 3), the four deferred feature phases (Phase 4+) — each gets its own spec later, per `docs/PROJECT_PLAN.md`.
