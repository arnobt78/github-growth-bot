# Phase 4E: Notifications & Alerting — Design Spec

Sub-project 4E of `docs/PROJECT_PLAN.md`'s Phase 4 (Professional Automation & Growth Platform). Depends only on 4A (Draft plumbing, done). Chosen as the next sub-project to build (of 4C/4D/4E, all now unblocked) per `PROJECT_PLAN.md`'s own recommended-build-order table and lowest external-setup friction — one Resend API key vs. 4C's four separate platform app registrations or 4D's Reddit OAuth app.

## Scope

Resend (transactional email) sends an alert in exactly three situations, matching `PROJECT_PLAN.md`'s 4E description:

1. A scheduled analytics run left one or more of a user's tracked repos `degraded` (a pipeline stage errored).
2. A scheduled run hit `needs_reauth` for a user (their stored GitHub token was rejected).
3. A scheduled content run generated one or more new `Draft` rows for a user.

**Explicitly out of scope for 4E:**

- Manual (`POST /runs`, `POST /runs/content`) trigger failures do not email — the user is actively watching the dashboard live via SSE when they click "Run now," so email would be redundant. Product-owner-confirmed decision.
- No in-app notification history/center. The existing SSE-driven live UI already covers "while you're looking"; email covers "while you're not." Adding a persisted notification log is a new feature nobody asked for — YAGNI.
- No digest/batching beyond what's already natural (one email per user per scheduled run per condition, not one email per repo). A user with 3 degraded repos gets one email listing all 3, not three emails.
- No unsubscribe/preference-per-alert-type UI. One on/off lever exists implicitly: leaving `notification_email` unset and having no public GitHub email means no emails ever send. If per-alert-type toggles are wanted later, that's a follow-up, not part of 4E.

## Data model

Two new nullable columns on `User`, one migration (`alembic revision --autogenerate`, manually reviewed per this project's established habit):

```python
class User(Base):
    ...
    # Fallback recipient for alert emails when the OAuth-scope-derived `email`
    # column is empty (GitHub's public_repo scope doesn't guarantee a public
    # email exists). Settings page lets the user set/clear this directly.
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Rate-limit guard: needs_reauth persists until the user reconnects GitHub,
    # so the daily scheduler would otherwise re-detect and re-email it every
    # single day. Null means "never sent" (or eligible to send again).
    last_reauth_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

## Email sending

New `backend/app/email_client.py`, structurally identical to `app/github_client.py`'s `httpx.Client` pattern — same constructor shape, same "raise on auth failure, otherwise fail soft" philosophy adapted for email (a Resend outage must never crash a scheduled job):

```python
import httpx


class EmailClient:
    def __init__(self, api_key: str, from_address: str, http_client: httpx.Client | None = None):
        self._from = from_address
        self._http = http_client or httpx.Client(
            base_url="https://api.resend.com",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )

    def send(self, to: str, subject: str, html: str) -> bool:
        """Returns False (never raises) on failure — a Resend outage degrades
        to "no email sent" for that one alert, same resilience contract as
        every other external call in this pipeline (GitHub API, LLM providers)."""
        try:
            resp = self._http.post(
                "/emails",
                json={"from": self._from, "to": [to], "subject": subject, "html": html},
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPError:
            return False
```

## Notification logic

New `backend/app/notifications.py`. One shared branded HTML template helper (inline styles only — no external CSS/images, matches email-client-compatibility norms) plus three sender functions, each resolving the recipient the same way and no-oping silently if there isn't one:

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.email_client import EmailClient
from app.models import User

REAUTH_COOLDOWN = timedelta(hours=24)


def _recipient(user: User) -> str | None:
    return user.notification_email or user.email


def _render_email(title: str, body_html: str, cta_label: str, cta_path: str) -> str:
    settings = get_settings()
    cta_url = f"{settings.frontend_base_url}{cta_path}"
    return f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #0f172a;">{title}</h2>
      <div style="color: #334155; line-height: 1.6;">{body_html}</div>
      <a href="{cta_url}" style="display: inline-block; margin-top: 16px; padding: 10px 20px;
         background: #0ea5e9; color: white; border-radius: 6px; text-decoration: none;">{cta_label}</a>
    </div>
    """


def _client() -> EmailClient:
    settings = get_settings()
    return EmailClient(api_key=settings.resend_api_key, from_address=settings.email_from)


def notify_pipeline_degraded(user: User, repo_names: list[str]) -> None:
    to = _recipient(user)
    if not to or not repo_names:
        return
    body = "The following tracked repos had an issue during today's run: " + ", ".join(repo_names)
    html = _render_email("Some repos need attention", body, "View runs", "/runs")
    _client().send(to, "GitHub Growth Bot: a repo run had issues", html)


def notify_needs_reauth(db: Session, user: User) -> None:
    to = _recipient(user)
    if not to:
        return
    now = datetime.now(timezone.utc)
    if user.last_reauth_notified_at and now - user.last_reauth_notified_at < REAUTH_COOLDOWN:
        return
    html = _render_email(
        "Reconnect your GitHub account",
        "Your GitHub sign-in has expired or was revoked, so today's run couldn't fetch your repo data.",
        "Reconnect",
        "/settings",
    )
    if _client().send(to, "GitHub Growth Bot: please reconnect GitHub", html):
        user.last_reauth_notified_at = now
        db.commit()


def notify_drafts_ready(user: User, draft_count: int) -> None:
    to = _recipient(user)
    if not to or draft_count < 1:
        return
    html = _render_email(
        f"{draft_count} new draft{'s' if draft_count != 1 else ''} ready",
        "New content suggestions are waiting for your review.",
        "Review drafts",
        "/drafts",
    )
    _client().send(to, "GitHub Growth Bot: new drafts ready to review", html)
```

- `notify_needs_reauth` only commits (updating the rate-limit timestamp) if the send actually succeeded — a failed send should be retried on the next scheduled run, not silently marked as "already notified."
- These three functions take already-resolved `User`/data, not `user_id` — the caller (batch job functions below) already has the `User` row loaded from its own per-repo `db.get(User, ...)` call.

## Wiring into the batch job functions

`run_pipeline_for_all_repos` and `run_content_pipeline_for_all_repos` (`app/pipeline/jobs.py`, `app/pipeline/content_jobs.py`) each gain one new parameter:

```python
def run_pipeline_for_all_repos(db: Session, user_id: int | None = None, notify: bool = False) -> None:
```

Defaults to `False` so the two manual-trigger routes (`app/api/runs.py`'s `POST /runs` and `POST /runs/content`, which call these functions directly) are unaffected without any change to their call sites.

**`run_pipeline_for_all_repos`:** the existing per-repo loop already computes `ctx.errors` per repo and already tracks `failed_auth_user_ids`. Add a `degraded: dict[int, list[str]] = {}` alongside it; when a repo's run isn't a `needs_reauth` case but `ctx.errors` is non-empty, append `f"{repo.owner}/{repo.name}"` under `degraded[repo.user_id]`. After the existing loop, if `notify`: for each `user_id, names` in `degraded.items()`, load the `User` row (already have `db.get(User, ...)` available) and call `notify_pipeline_degraded`; for each `user_id` in `failed_auth_user_ids`, load the `User` row and call `notify_needs_reauth(db, user)`.

**`run_content_pipeline_for_all_repos`:** capture `run_started_at = datetime.now(timezone.utc)` before the loop. After the loop, if `notify`: for each `user_id` in `processed_user_ids`, count `Draft` rows with that `user_id` and `created_at >= run_started_at` (a plain `db.query(Draft).filter(...).count()`); if `> 0`, load the `User` row and call `notify_drafts_ready`.

`app/main.py`'s two scheduler wrappers (`_scheduled_pipeline_run`, `_scheduled_content_pipeline_run`) pass `notify=True` explicitly — the only two call sites that do.

## Backend API: user profile

Today `app/api/users.py` only has `POST /users/upsert` (auth-flow-only, no `require_user`). 4E adds the first per-user-scoped endpoints on this router:

```text
GET   /users/me   -> UserOut (extended with notification_email), current user's own row
PATCH /users/me   -> UserOut, body: {"notification_email": str | None}
```

- Both use `Depends(require_user)`, matching every other per-user resource.
- `UserOut` gains `notification_email: str | None`.
- `PATCH` sets the column directly (empty string from the frontend is normalized to `None` — "clear the fallback" should actually clear it, not store `""`), commits, publishes a new `user_updated` SSE event via the existing `broadcaster.publish("user_updated", {}, user_id=current_user.id)` pattern, matching every other mutating endpoint's real-time-sync convention.
- Path `users/me` contains none of the forbidden ad-blocker substrings.

## Real-time sync

- New event type: `user_updated`, published on successful `PATCH /users/me`.
- `hooks/use-live-events.ts`'s `EVENT_QUERY_MAP` gains: `user_updated: [queryKeys.users.me]` (new query-key group, see below).
- Payload is `{}` (no fields needed — matches the existing empty-payload precedent for `run_completed`/`drafts_generated`; the client just refetches).

## Frontend

- `lib/query-keys.ts`: add `users: { me: ["users", "me"] as const }`.
- `lib/api-types.ts`: `UserOut` (already imported) gains `notification_email` once regenerated from the live OpenAPI schema — no new type alias needed.
- `lib/api.ts`: add `getMe: () => backendFetch<UserOut>("/users/me")` and `updateMe: (payload: { notification_email: string | null }) => backendFetch<UserOut>("/users/me", { method: "PATCH", body: JSON.stringify(payload) })`.
- New Route Handler `app/api/users/me/route.ts`:
  ```ts
  import { api } from "@/lib/api";
  import { proxyRoute } from "@/lib/route-handler";

  export async function GET() {
    return proxyRoute(() => api.getMe());
  }

  export async function PATCH(request: Request) {
    const payload = (await request.json()) as { notification_email: string | null };
    return proxyRoute(() => api.updateMe(payload));
  }
  ```
- `hooks/use-me.ts` (new): `useMe()` query (`queryKeys.users.me`, `fetchJson<UserOut>("/api/users/me")`, matching `use-provider-status.ts`'s exact shape) + `useUpdateMe()` mutation (`fetchJson` PATCH, `onSuccess` → `queryClient.setQueryData(queryKeys.users.me, updated)`, matching the existing `use-drafts.ts`/`use-recommendations.ts` cache-update-not-refetch pattern).
- `app/settings/page.tsx`: extend the existing `Promise.all([api.listRepos(), api.providerStatus()])` to a third parallel call, `api.getMe()`, `queryClient.setQueryData(queryKeys.users.me, me)` alongside the two existing `setQueryData` calls. Still one `Promise.all`, no waterfall.
- `components/settings/notification-settings-card.tsx` (new): Client Component, `useMe()` + `useUpdateMe()`. Shows the effective recipient (`me.notification_email || me.email || "No email on file"`), a text input pre-filled with `me.notification_email ?? ""`, a Save button calling `updateMe.mutate({ notification_email: value.trim() || null })` with an `onError` toast (matching `settings-client.tsx`'s existing `deleteRepo` error-toast pattern) and `disabled` while `isPending`. Icon: `Mail` from `lucide-react`, color `text-amber-500` (checked against `nav-sidebar.tsx`'s existing icon-color set — amber isn't used by a top-level nav item, and this is a settings sub-section not a nav item, so exact-uniqueness across the whole app isn't required, just non-clashing within the Settings page's existing `text-sky-500` "Tracked repos" heading).
- `components/settings/settings-client.tsx`: render `<NotificationSettingsCard />` after the existing `<ProviderStatusTable />`, same `space-y-8` vertical rhythm as the other two sections.

## Config

`backend/app/config.py`'s `Settings` gains three fields (all default `""`, matching the existing optional-provider-key pattern):

```python
resend_api_key: str = ""
email_from: str = ""
frontend_base_url: str = ""
```

`backend/.env.example` documents all three, including where to get a Resend API key and that `EMAIL_FROM` must be a verified sender on that Resend account. The Product Owner's real key/from-address for this project go directly into gitignored `backend/.env` only — never into `.env.example`, never committed, never logged (`EmailClient` never logs its API key or request/response bodies, matching `GitHubClient`'s existing no-token-logging convention).

## Testing

Backend (new `backend/tests/test_notifications.py`, plus targeted additions to `test_pipeline_per_user.py`/`test_content_jobs.py`/`test_users_api.py`):

- `EmailClient.send` returns `True` on a mocked 200 response, `False` (no raise) on a mocked network error — matches `GitHubClient`'s own test style for its `_get` wrapper.
- `notify_pipeline_degraded` / `notify_needs_reauth` / `notify_drafts_ready` each: no-op (client never called) when `_recipient` returns `None`; calls the client with the right `to` when a `notification_email` or fallback `email` exists.
- `notify_needs_reauth`: does not send (and does not touch `last_reauth_notified_at`) when the last send was < 24h ago; does send and updates the timestamp when `None` or stale; does NOT update the timestamp if the mocked send returns `False`.
- `run_pipeline_for_all_repos(db, notify=True)`: mocks `notify_pipeline_degraded`/`notify_needs_reauth`, seeds a degraded repo + a needs_reauth user, asserts both are called with the right arguments; asserts neither is called when `notify=False` (the existing manual-trigger default).
- `run_content_pipeline_for_all_repos(db, notify=True)`: seeds a run that produces ≥1 Draft, asserts `notify_drafts_ready` called with the correct count; asserts not called when zero drafts were produced.
- `GET /users/me`: returns the calling user's own row including `notification_email`.
- `PATCH /users/me`: sets `notification_email`; empty string normalizes to `None`; publishes `user_updated` via the same `unittest.mock.patch("app.api.users.broadcaster.publish")` pattern `test_drafts_api.py` already established for `draft_updated`.

Frontend (new `frontend/tests/use-me.test.tsx` or extend an existing hooks test file — check current Vitest conventions first):

- `useUpdateMe`'s mutation correctly `setQueryData`s on success.
- `EVENT_QUERY_MAP` includes `user_updated` → `queryKeys.users.me`.

Both suites stay at 100% pass, zero warnings, matching the rest of this codebase.

## Migration & type-generation sequencing

Same established order as every prior sub-project (see 4A's spec for the full rationale):

1. Add `User` columns + migration, review the autogenerated migration, `alembic upgrade head`.
2. Build/test `EmailClient`, `notifications.py`, and the `notify` wiring in isolation.
3. Build/test `GET`/`PATCH /users/me`.
4. Start the local backend, regenerate frontend types (`npm run generate:types`), then build the frontend layer (types already regenerate `UserOut` → api.ts → query-keys → hook → Route Handler → Settings card → SSE mapping).

## Non-goals restated (from Phase 4's governing decisions, still binding)

- This is not an "external-facing action" in the draft-and-approve sense (POL-driven decision #2) — it's a system notification to the account owner about their own data, not a post to a third-party platform on their behalf. No `Draft` row involved.
- No n8n, no new service, no new deploy target — `EmailClient` is a plain `httpx` call from the existing FastAPI app, same shape as every other external integration in this codebase.
