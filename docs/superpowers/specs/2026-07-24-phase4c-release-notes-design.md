# Phase 4C: Release Notes Generation — Design Spec

Sub-project 4C of `docs/PROJECT_PLAN.md`'s Phase 4 (Professional Automation & Growth Platform). Depends on 4A (Draft plumbing) and 4B (Agentic Content Pipeline), both done.

## Scope

`PROJECT_PLAN.md`'s original 4C row bundles three things: release-notes generation, demo-asset regeneration (that's 4G's own sub-project), and cross-posting Drafts to LinkedIn/X/Reddit/Dev.to. This build ships **release-notes generation only**.

**Explicitly out of scope, deliberately:**

- **Cross-posting to LinkedIn/X/Reddit/Dev.to.** Each platform needs its own developer app registration (OAuth for LinkedIn/X/Reddit, an API key for Dev.to) — real external setup only the Product Owner can do, matching the same pattern as the GitHub OAuth App registration in Phase 2. Building the posting/approval UI now, with no real credentials to ever exercise it, would be speculative. When the Product Owner registers these apps, cross-posting becomes its own small follow-up: a new `Draft.kind` per platform, reusing the exact same Drafts-inbox approve/reject flow already built.
- **4G's demo-asset regeneration.** That's its own sub-project with its own dependencies (Playwright + ffmpeg); 4C leaves no half-built hook for it, since 4G's design will define what it actually needs from a release event when it's built.
- **GitHub webhooks.** This project has no deployed public URL yet (VPS/Vercel deployment is still pending, gated separately per POL-0006), so GitHub cannot call a webhook endpoint that doesn't exist. Release detection is a scheduled poll instead — see below.

## Detection: scheduled poll via the existing content pipeline

No new scheduler job. Release detection folds into the existing daily content pipeline (`run_content_pipeline_for_all_repos`, `ContentExtractor` → `ContentAnalyzer` → ... → `ContentAssembler`) exactly as `PROJECT_PLAN.md`'s architecture describes: "one pipeline template, several `PipelineContext` inputs." A new `release_notes` `ContentTask` kind is just one more task type the existing Synthesizer/Validator/Assembler machinery already handles generically.

**New `GitHubClient` method** (`backend/app/github_client.py`), matching the existing GET-method conventions exactly (401 raises `GitHubAuthError`, otherwise `raise_for_status()`):

```python
def list_releases(self, owner: str, name: str, limit: int = 2) -> list[dict]:
    return self._get(f"/repos/{owner}/{name}/releases", params={"per_page": limit}).json()
```

GitHub's releases endpoint returns newest-first by default, so `list_releases(..., limit=1)[0]` is the latest release (`{"tag_name": ..., "body": ..., "published_at": ..., ...}`), or an empty list if the repo has no releases at all.

**New `Repo` column** (one migration, `alembic revision --autogenerate`, manually reviewed per this project's established habit):

```python
class Repo(Base):
    ...
    # Last release tag_name we've already generated (or attempted to generate)
    # release notes for. Null means "never checked" — the repo's current
    # latest release, even if it predates tracking, still gets a Draft the
    # first time the content pipeline runs for it.
    last_release_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

## `ContentExtractor`

One additional fetch alongside the existing `repo`/`readme`/`topics` calls:

```python
releases = self.gh_client.list_releases(owner, name, limit=1)
ctx.raw["latest_release"] = releases[0] if releases else None
```

## `ContentAnalyzer`

Appends a `release_notes` task only when there's a latest release AND its tag differs from what we've already drafted for, AND it has non-empty release notes to work from:

```python
latest_release = raw.get("latest_release")
if latest_release and latest_release.get("tag_name") != ctx.repo.last_release_tag:
    body = (latest_release.get("body") or "").strip()
    if body:
        tasks.append(ContentTask(
            kind="release_notes",
            target=latest_release["tag_name"],
            structured=False,
            current=None,
            source_material={"tag": latest_release["tag_name"], "raw_notes": body, "repo_name": ctx.repo.name},
        ))
```

If `body` is empty (a release with no notes at all — common for lightweight/auto-created tags), no task is created. There is nothing real to synthesize from, and inventing feature/fix descriptions from a bare tag name would be exactly the kind of fabrication this project's Validator philosophy exists to prevent — the existing metric-number check wouldn't catch a fabricated *prose* claim like "added dark mode." Skipping is the safe default; the release will be picked up again on the next daily run in case its body gets filled in later, since `last_release_tag` is only advanced on a successful (`task.valid`) Draft — see Assembler below, not at detection time.

`ContentPreprocessor`/`ContentOptimizer` need no changes — their truncation logic only ever touches `source_material["readme"]`, which `release_notes` tasks don't set.

## `ContentSynthesizer`

One new prompt entry in `_KIND_PROMPTS`:

```python
"release_notes": (
    "Rewrite the following raw release notes for {repo_name} (tag {tag}) as clear, "
    "user-facing release notes in markdown. Group changes under headings like "
    "'Features', 'Fixes', 'Other' only where the raw notes actually support that "
    "grouping — do not invent categories or claims not present in the raw notes below. "
    "Respond with the release notes text only, no commentary.\n\n"
    "Raw notes:\n{raw_notes}"
),
```

`_build_prompt`'s `fields` dict gains `"repo_name"`, `"tag"`, `"raw_notes"` pulled from `task.source_material`, defaulting to `""` like every existing field — no other change to `_generate_candidates`/`_parse_candidate` (this is a free-text/`structured=False` kind, so it flows through the exact same unstructured-candidate path `readme_suggestion`/`missing_doc_suggestion` already use).

## `ContentValidator`

No change needed. The existing metric-claim number-check (`_METRIC_CLAIM_PATTERN`-scoped, from the Phase 4B final-review fix) already applies uniformly to every free-text candidate — if a release-notes candidate happens to cite a fabricated star/fork count, it's caught the same way a README candidate would be. The judge-based best-of-3 selection is kind-agnostic already.

## `ContentAssembler`

Two changes: the kind-specific `content` shape, and the `last_release_tag` advance-on-success:

```python
def _content_for(self, task: ContentTask) -> dict:
    if task.kind == "seo_suggestion":
        ...
    if task.kind in ("missing_doc_suggestion", "release_notes"):
        return {"suggested": task.winner, "reason": task.winner_reason}
    return {"current": task.current, "suggested": task.winner, "reason": task.winner_reason}
```

```python
def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
    for task in ctx.tasks:
        if not task.valid:
            continue
        self.db.add(Draft(
            user_id=ctx.repo.user_id,
            repo_id=ctx.repo.id,
            kind=task.kind,
            target=task.target,
            content=self._content_for(task),
            status="pending",
        ))
        if task.kind == "release_notes":
            ctx.repo.last_release_tag = task.target
    self.db.commit()
    return ctx
```

`last_release_tag` only advances when a Draft was actually written (`task.valid`, inside the existing `if not task.valid: continue` guard) — a transient LLM/provider outage doesn't silently skip a release forever; the same release is retried on the next daily content-pipeline run until it succeeds. This mirrors Phase 4E's `notify_needs_reauth` reasoning: only commit state that reflects a real, completed action.

## Frontend

- `frontend/types/drafts.ts`: `DraftKind` union gains `"release_notes"`. New `ReleaseNotesContent = MissingDocSuggestionContent` type alias (identical shape: `{suggested, reason}`) for readability at the call site, even though structurally it's the same as `missing_doc_suggestion`.
- `frontend/components/drafts/drafts-client.tsx`: `DRAFT_KIND_LABELS` gains `release_notes: "Release notes"` (the `satisfies Record<DraftKind, string>` constraint means the build fails if this is forgotten). The card header gains the release tag for this kind specifically — the one place `draft.target` carries information a reader actually needs (for every other kind, `target` duplicates what the kind label already implies — "readme", "topics", "description", or a doc filename shown inside the content itself):
  ```tsx
  {DRAFT_KIND_LABELS[draft.kind] ?? draft.kind}
  {draft.kind === "release_notes" && ` (${draft.target})`}
  ```
- `frontend/components/drafts/draft-content.tsx`: new `if (kind === "release_notes" && isMissingDocSuggestion(content))` branch, identical JSX to the existing `missing_doc_suggestion` branch (same shape, same rendering — a single `<pre>` block + `Reason`). Not merged into one shared condition with `missing_doc_suggestion`, to match this file's existing convention of one explicit branch per `kind` (readme/missing_doc/topic/seo each get their own block even where two blocks would render identically).

No new hooks, no new Route Handler, no new backend API endpoint — `release_notes` Drafts flow through the exact same `/drafts`, `GET /drafts`, `PATCH /drafts/{id}`, `drafts_generated` SSE event, and `DraftsClient` rendering loop every other kind already uses. This is the entire point of the Draft-queue architecture: a new content producer needs zero new plumbing.

## Testing

Backend:

- `test_github_client.py`: `list_releases` returns the mocked releases list; empty list when the repo has none.
- `test_extractor.py` (or wherever `ContentExtractor` is tested): `ctx.raw["latest_release"]` populated correctly; `None` when `list_releases` returns empty.
- `test_analyzer.py`: a `release_notes` task is appended when the release tag differs from `repo.last_release_tag` and `body` is non-empty; no task when the tag matches (already drafted); no task when `body` is empty; no task when there's no release at all.
- `test_synthesizer_validator.py` (or wherever prompt-building is tested): `_build_prompt` produces the expected string for a `release_notes` task with all three new fields substituted.
- `test_content_jobs.py` (or the assembler's own test file): a valid `release_notes` task writes a `Draft` with `content == {"suggested": ..., "reason": ...}` and advances `repo.last_release_tag`; an invalid (non-`task.valid`) `release_notes` task writes no Draft and leaves `last_release_tag` unchanged, proving the retry-until-success behavior.

Frontend:

- `draft-content.test.tsx`: `release_notes` kind renders the suggested text + reason, matching the `missing_doc_suggestion` test's shape.
- `drafts-client.test.tsx` (if one exists covering `DRAFT_KIND_LABELS`/header rendering) or a new assertion: the release tag renders in the header for `release_notes` drafts, and does NOT render an extra target string for other kinds.

Both suites stay at 100% pass, zero warnings, matching the rest of this codebase.

## Migration & type-generation sequencing

Same established order as every prior sub-project:

1. Add `Repo.last_release_tag`, run `alembic revision --autogenerate`, review, do not run `alembic upgrade head` against real Postgres in this build (deferred to the Product Owner, same as every prior migration).
2. Build/test `GitHubClient.list_releases`, `ContentExtractor`, `ContentAnalyzer`, `ContentSynthesizer`, `ContentAssembler` changes, each independently testable.
3. No new backend API surface, so no OpenAPI type regeneration is needed for this sub-project — verified `frontend/types/api.d.ts`'s `DraftOut.content` is already `{ [key: string]: unknown }` (untyped JSON), so the frontend's own `types/drafts.ts` (hand-written per-kind shapes, not generated) is the only type surface that needs a change.
4. Build the frontend layer (types → `DRAFT_KIND_LABELS` → `DraftContent` branch → header target display).

## Non-goals restated (from Phase 4's governing decisions, still binding)

- Nothing here posts anywhere external — a `release_notes` Draft sits in the same approve/reject-only inbox as every other Draft kind; approving it today has no on-approve side effect (same as every Draft kind before it — no producer in this codebase has ever wired an on-approve action yet, matching 4A's own stated non-goal).
- No n8n, no new service, no new deploy target, no new scheduler job — this sub-project adds zero new moving parts to the running system, only one new task kind inside infrastructure that already exists and runs daily.
