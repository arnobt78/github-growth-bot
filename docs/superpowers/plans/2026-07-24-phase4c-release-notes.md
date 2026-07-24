# Phase 4C: Release Notes Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `release_notes` `ContentTask` kind, folded into the existing daily content pipeline, detects a tracked repo's new GitHub release and drafts polished release notes as a `Draft` — reusing the entire existing best-of-3/LLM-as-judge/Drafts-inbox machinery with zero new pipeline, scheduler job, or backend API surface.

**Architecture:** `GitHubClient` gains one new GET method (`list_releases`). `ContentExtractor` fetches the latest release into `ctx.raw`. `ContentAnalyzer` appends a `release_notes` task only when the release is new (compared against a new `Repo.last_release_tag` column) and has real notes to work from. `ContentSynthesizer` gets one new prompt template. `ContentAssembler` writes the Draft and advances `last_release_tag` only on success. Frontend renders the new kind via one new `DraftContent` branch identical in shape to `missing_doc_suggestion`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, httpx, pytest (backend); Next.js 16 App Router, Vitest (frontend).

## Global Constraints

- No new scheduler job, no new pipeline, no new backend API endpoint — `release_notes` flows through the exact same `/drafts` API, `drafts_generated` SSE event, and Drafts inbox every other kind already uses.
- No task is created when the latest release's body is empty/whitespace-only — nothing real to synthesize from; inventing content is exactly what this project's Validator philosophy exists to prevent.
- `Repo.last_release_tag` only advances when the resulting task is `valid` (a Draft was actually written) — a transient LLM outage must not permanently skip a release; it retries on the next daily run.
- Manual `POST /runs/content` behavior is unaffected — this plan changes what tasks get generated, not when/how the pipeline runs.
- Full spec: `docs/superpowers/specs/2026-07-24-phase4c-release-notes-design.md`.

---

### Task 1: `Repo.last_release_tag` column + migration

**Files:**
- Modify: `backend/app/models.py` (`Repo` class)
- Create: `backend/alembic/versions/<hash>_add_last_release_tag_to_repos.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `Repo.last_release_tag: str | None` — nullable, consumed by `app/pipeline/content/analyzer.py` (Task 4) and `app/pipeline/content/assembler.py` (Task 6).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_models.py`:

```python
def test_repo_last_release_tag_defaults_none_and_is_settable():
    db = SessionLocal()
    user = User(
        github_id="777",
        username="release-tester",
        avatar_url="https://avatars.githubusercontent.com/u/777",
        email=None,
        access_token_encrypted="ciphertext-placeholder",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    repo = Repo(owner="octocat", name="hello-world", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    assert repo.last_release_tag is None

    repo.last_release_tag = "v1.2.0"
    db.commit()
    db.refresh(repo)

    assert repo.last_release_tag == "v1.2.0"
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py::test_repo_last_release_tag_defaults_none_and_is_settable -v`
Expected: FAIL with `AttributeError: 'Repo' object has no attribute 'last_release_tag'`

- [ ] **Step 3: Add the column to the model**

In `backend/app/models.py`, inside `class Repo(Base):`, immediately after the existing `tracked_since` column (`tracked_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)`), add:

```python
    # Last release tag_name we've already generated (or attempted to generate)
    # release notes for. Null means "never checked" — the repo's current
    # latest release, even if it predates tracking, still gets a Draft the
    # first time the content pipeline runs for it. Only advances when a Draft
    # was actually written (see ContentAssembler) — a transient LLM outage
    # must not permanently skip a release.
    last_release_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py -v`
Expected: all pass, including the new test.

- [ ] **Step 5: Generate and review the Alembic migration**

Run: `cd backend && .venv/bin/python -m alembic revision --autogenerate -m "add last_release_tag to repos"`

This creates `backend/alembic/versions/<hash>_add_last_release_tag_to_repos.py` with `down_revision = '9cb171d67eae'` (the current head, confirm with `.venv/bin/python -m alembic heads` before trusting this value). Open it and confirm it matches this shape:

```python
def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('repos', sa.Column('last_release_tag', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('repos', 'last_release_tag')
    # ### end Alembic commands ###
```

Do **not** run `alembic upgrade head` against a real database in this task — same as every prior migration in this project, that's the Product Owner's own follow-up step.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/alembic/versions/*_add_last_release_tag_to_repos.py backend/tests/test_models.py
git commit -m "feat(4c): add Repo.last_release_tag"
```

---

### Task 2: `GitHubClient.list_releases`

**Files:**
- Modify: `backend/app/github_client.py`
- Test: `backend/tests/test_github_client.py`

**Interfaces:**
- Produces: `GitHubClient.list_releases(owner: str, name: str, limit: int = 2) -> list[dict]`. Consumed by `app/pipeline/content/extractor.py` (Task 3).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_github_client.py`. First extend the existing `mock_transport` fixture's `handler` function with one new branch (add it before the final `return httpx.Response(404)` line):

```python
        if request.url.path == "/repos/octocat/hello-world/releases":
            return httpx.Response(200, json=[
                {"tag_name": "v1.2.0", "body": "- Added dark mode\n- Fixed crash on startup", "published_at": "2026-07-20T00:00:00Z"},
                {"tag_name": "v1.1.0", "body": "- Initial release", "published_at": "2026-06-01T00:00:00Z"},
            ])
```

Then add these two new test functions:

```python
def test_list_releases_returns_latest_first(gh_client):
    releases = gh_client.list_releases("octocat", "hello-world", limit=1)
    assert releases[0]["tag_name"] == "v1.2.0"


def test_list_releases_returns_empty_list_for_repo_with_no_releases():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    http = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    client = GitHubClient(token="fake-token", http_client=http)

    assert client.list_releases("octocat", "empty-repo") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_github_client.py -v -k list_releases`
Expected: FAIL with `AttributeError: 'GitHubClient' object has no attribute 'list_releases'`

- [ ] **Step 3: Implement `list_releases`**

In `backend/app/github_client.py`, add this method to `class GitHubClient:` (place it near `search_similar_repos`, the other method that returns a list rather than a single dict):

```python
    def list_releases(self, owner: str, name: str, limit: int = 2) -> list[dict]:
        return self._get(f"/repos/{owner}/{name}/releases", params={"per_page": limit}).json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_github_client.py -v`
Expected: all pass, including the 2 new tests, no regressions to existing tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/github_client.py backend/tests/test_github_client.py
git commit -m "feat(4c): add GitHubClient.list_releases"
```

---

### Task 3: `ContentExtractor` fetches the latest release

**Files:**
- Modify: `backend/app/pipeline/content/extractor.py`
- Test: `backend/tests/test_content_extractor.py`

**Interfaces:**
- Consumes: `GitHubClient.list_releases` (Task 2).
- Produces: `ctx.raw["latest_release"]: dict | None`. Consumed by `app/pipeline/content/analyzer.py` (Task 4).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_content_extractor.py`. First extend the existing `_fake_gh_client` helper to also stub `list_releases` (add this line inside the function, before `return gh`):

```python
    gh.list_releases.return_value = [{"tag_name": "v1.2.0", "body": "- Added dark mode", "published_at": "2026-07-20T00:00:00Z"}]
```

Then add:

```python
def test_extractor_populates_latest_release():
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    gh = _fake_gh_client()

    ctx = ContentExtractor(gh_client=gh).run(ctx)

    assert ctx.raw["latest_release"]["tag_name"] == "v1.2.0"
    gh.list_releases.assert_called_once_with("octocat", "hello-world", limit=1)


def test_extractor_latest_release_is_none_when_no_releases_exist():
    repo = Repo(owner="octocat", name="hello-world")
    ctx = ContentPipelineContext(repo=repo)
    gh = _fake_gh_client()
    gh.list_releases.return_value = []

    ctx = ContentExtractor(gh_client=gh).run(ctx)

    assert ctx.raw["latest_release"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_extractor.py -v -k latest_release`
Expected: FAIL with `KeyError: 'latest_release'`

- [ ] **Step 3: Implement the fetch**

In `backend/app/pipeline/content/extractor.py`, modify the `run` method's body to add the releases fetch and populate `ctx.raw["latest_release"]`. Full new method body:

```python
    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        owner, name = ctx.repo.owner, ctx.repo.name
        repo_data = self.gh_client.get_repo(owner, name)

        missing_docs = [f for f in STANDARD_DOC_FILES if not self.gh_client.has_file(owner, name, f)]
        releases = self.gh_client.list_releases(owner, name, limit=1)

        ctx.raw = {
            "repo": repo_data,
            "readme": self.gh_client.get_readme(owner, name),
            "topics": repo_data.get("topics", []),
            "description": repo_data.get("description"),
            "stars": repo_data.get("stargazers_count", 0),
            "missing_docs": missing_docs,
            "latest_release": releases[0] if releases else None,
        }
        return ctx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_extractor.py -v`
Expected: all pass, including the 2 new tests, no regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content/extractor.py backend/tests/test_content_extractor.py
git commit -m "feat(4c): ContentExtractor fetches the latest release"
```

---

### Task 4: `ContentAnalyzer` creates a `release_notes` task

**Files:**
- Modify: `backend/app/pipeline/content/analyzer.py`
- Test: `backend/tests/test_content_analyzer.py`

**Interfaces:**
- Consumes: `ctx.raw["latest_release"]` (Task 3), `ctx.repo.last_release_tag` (Task 1).
- Produces: a `ContentTask(kind="release_notes", target=<tag>, structured=False, current=None, source_material={"tag", "raw_notes", "repo_name"})` appended to `ctx.tasks` under the conditions below. Consumed by `app/pipeline/content/synthesizer.py` (Task 5) and `app/pipeline/content/assembler.py` (Task 6).

- [ ] **Step 1: Write the failing tests**

The existing `_ctx` test helper in `backend/tests/test_content_analyzer.py` builds a bare `Repo(owner="octocat", name="hello-world")` with no `last_release_tag` set (so it's `None` by default on the transient instance) and no `latest_release` key in `raw` by default. Add these 4 tests:

```python
def test_analyzer_builds_release_notes_task_for_new_release():
    ctx = _ctx(latest_release={"tag_name": "v1.2.0", "body": "- Added dark mode"})
    ctx = ContentAnalyzer().run(ctx)

    release_task = next(t for t in ctx.tasks if t.kind == "release_notes")
    assert release_task.target == "v1.2.0"
    assert release_task.current is None
    assert release_task.structured is False
    assert release_task.source_material == {"tag": "v1.2.0", "raw_notes": "- Added dark mode", "repo_name": "hello-world"}


def test_analyzer_skips_release_notes_task_when_tag_already_drafted():
    ctx = _ctx(latest_release={"tag_name": "v1.2.0", "body": "- Added dark mode"})
    ctx.repo.last_release_tag = "v1.2.0"

    ctx = ContentAnalyzer().run(ctx)

    assert not any(t.kind == "release_notes" for t in ctx.tasks)


def test_analyzer_skips_release_notes_task_when_body_is_empty():
    ctx = _ctx(latest_release={"tag_name": "v1.2.0", "body": ""})
    ctx = ContentAnalyzer().run(ctx)

    assert not any(t.kind == "release_notes" for t in ctx.tasks)


def test_analyzer_skips_release_notes_task_when_no_release_exists():
    ctx = _ctx(latest_release=None)
    ctx = ContentAnalyzer().run(ctx)

    assert not any(t.kind == "release_notes" for t in ctx.tasks)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_analyzer.py -v -k release_notes`
Expected: FAIL — `StopIteration` (no `release_notes` task exists yet) on the first test; the other 3 should already pass vacuously since no `release_notes` task is ever created yet (confirm this is genuinely the pre-implementation state, not a false pass).

- [ ] **Step 3: Implement the task creation**

In `backend/app/pipeline/content/analyzer.py`, add the release-notes block to the end of `run`, immediately before `ctx.tasks = tasks; return ctx`. Full updated method:

```python
    def run(self, ctx: ContentPipelineContext) -> ContentPipelineContext:
        raw = ctx.raw
        topics = raw.get("topics", [])
        tasks: list[ContentTask] = [
            ContentTask(
                kind="readme_suggestion",
                target="readme",
                structured=False,
                current=raw.get("readme"),
                source_material={"readme": raw.get("readme") or "", "topics": topics, "description": raw.get("description")},
            ),
        ]

        for filename in raw.get("missing_docs", []):
            tasks.append(ContentTask(
                kind="missing_doc_suggestion",
                target=filename,
                structured=False,
                current=None,
                source_material={"filename": filename, "readme": raw.get("readme") or ""},
            ))

        if len(topics) < _MIN_TOPICS:
            tasks.append(ContentTask(
                kind="topic_suggestion",
                target="topics",
                structured=True,
                current=topics,
                source_material={"topics": topics, "readme": raw.get("readme") or "", "description": raw.get("description")},
            ))

        tasks.append(ContentTask(
            kind="seo_suggestion",
            target="description",
            structured=True,
            current=raw.get("description"),
            source_material={"description": raw.get("description"), "readme": raw.get("readme") or "", "topics": topics},
        ))

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

        ctx.tasks = tasks
        return ctx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_analyzer.py -v`
Expected: all pass, including the 4 new tests, no regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content/analyzer.py backend/tests/test_content_analyzer.py
git commit -m "feat(4c): ContentAnalyzer creates a release_notes task for new releases"
```

---

### Task 5: `ContentSynthesizer` release-notes prompt

**Files:**
- Modify: `backend/app/pipeline/content/synthesizer.py`
- Test: `backend/tests/test_content_synthesizer.py`

**Interfaces:**
- Consumes: `ContentTask(kind="release_notes", source_material={"tag", "raw_notes", "repo_name"})` (Task 4).
- Produces: no new public interface — `release_notes` tasks now flow through the existing `_generate_candidates`/`_parse_candidate` free-text path with no other code changes.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_content_synthesizer.py`:

```python
def test_synthesizer_builds_release_notes_prompt():
    task = ContentTask(
        kind="release_notes",
        target="v1.2.0",
        structured=False,
        current=None,
        source_material={"tag": "v1.2.0", "raw_notes": "- Added dark mode", "repo_name": "hello-world"},
    )
    ctx = _ctx_with_task(task)
    llm = _fake_llm(["## Features\n- Dark mode"])

    ctx = ContentSynthesizer(llm_router=llm).run(ctx)

    assert ctx.tasks[0].candidates == ["## Features\n- Dark mode"]
    sent_prompt = llm.chat_completion.call_args_list[0].args[0][1]["content"]
    assert "hello-world" in sent_prompt
    assert "v1.2.0" in sent_prompt
    assert "- Added dark mode" in sent_prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_synthesizer.py -v -k release_notes`
Expected: FAIL — `KeyError: 'release_notes'` from `_KIND_PROMPTS[task.kind]` inside `_build_prompt`.

- [ ] **Step 3: Add the prompt and field**

In `backend/app/pipeline/content/synthesizer.py`, add a new entry to `_KIND_PROMPTS` (after the existing `"seo_suggestion"` entry):

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

Then update `_build_prompt`'s `fields` dict to include the 3 new keys (full updated method):

```python
    def _build_prompt(self, task: ContentTask) -> str:
        fields = {
            "readme": task.source_material.get("readme") or "",
            "topics": task.source_material.get("topics") or [],
            "description": task.source_material.get("description") or "",
            "filename": task.source_material.get("filename", ""),
            "repo_name": task.source_material.get("repo_name", ""),
            "tag": task.source_material.get("tag", ""),
            "raw_notes": task.source_material.get("raw_notes", ""),
        }
        return _KIND_PROMPTS[task.kind].format(**fields)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_synthesizer.py -v`
Expected: all pass, including the new test, no regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content/synthesizer.py backend/tests/test_content_synthesizer.py
git commit -m "feat(4c): ContentSynthesizer gains a release_notes prompt"
```

---

### Task 6: `ContentAssembler` writes the Draft and advances `last_release_tag`

**Files:**
- Modify: `backend/app/pipeline/content/assembler.py`
- Test: `backend/tests/test_content_assembler.py`

**Interfaces:**
- Consumes: a `release_notes` `ContentTask` with `valid`/`winner`/`winner_reason` set by the (unmodified) `ContentValidator`.
- Produces: `Draft(kind="release_notes", target=<tag>, content={"suggested": ..., "reason": ...})`; `Repo.last_release_tag` advanced to the task's `target` only when `task.valid` is `True`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_content_assembler.py`:

```python
def test_assembler_writes_release_notes_draft_and_advances_last_release_tag(seed_user):
    db, repo = _db_and_repo(seed_user)
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [
        ContentTask(kind="release_notes", target="v1.2.0", structured=False, current=None, winner="## Features\n- Dark mode", winner_reason="clear and accurate", valid=True),
    ]

    ctx = ContentAssembler(db_session=db).run(ctx)

    draft = db.query(Draft).filter_by(repo_id=repo.id, kind="release_notes").one()
    assert draft.target == "v1.2.0"
    assert draft.content == {"suggested": "## Features\n- Dark mode", "reason": "clear and accurate"}

    db.refresh(repo)
    assert repo.last_release_tag == "v1.2.0"
    db.close()


def test_assembler_does_not_advance_last_release_tag_for_invalid_task(seed_user):
    db, repo = _db_and_repo(seed_user)
    ctx = ContentPipelineContext(repo=repo)
    ctx.tasks = [
        ContentTask(kind="release_notes", target="v1.2.0", structured=False, current=None, winner=None, winner_reason=None, valid=False),
    ]

    ctx = ContentAssembler(db_session=db).run(ctx)

    assert db.query(Draft).filter_by(repo_id=repo.id, kind="release_notes").count() == 0
    db.refresh(repo)
    assert repo.last_release_tag is None
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_assembler.py -v -k release_notes`
Expected: FAIL — the draft's `content` will be `{"current": None, "suggested": ..., "reason": ...}` (falls through to the generic branch) instead of `{"suggested": ..., "reason": ...}`, and `repo.last_release_tag` stays `None`.

- [ ] **Step 3: Implement the assembler changes**

In `backend/app/pipeline/content/assembler.py`, update `_content_for` (change the `missing_doc_suggestion`-only check to include `release_notes`):

```python
    def _content_for(self, task: ContentTask) -> dict:
        if task.kind == "seo_suggestion":
            return {
                "current": task.current,
                "suggested_description": task.winner["description"],
                "keywords": task.winner["keywords"],
                "reason": task.winner_reason,
            }
        if task.kind in ("missing_doc_suggestion", "release_notes"):
            return {"suggested": task.winner, "reason": task.winner_reason}
        return {"current": task.current, "suggested": task.winner, "reason": task.winner_reason}
```

Then update `run` to advance `last_release_tag` (full updated method):

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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_content_assembler.py -v`
Expected: all pass, including the 2 new tests, no regressions to the existing `test_assembler_writes_draft_per_valid_task` test (which doesn't include a `release_notes` task, so its 4-drafts assertion is unaffected).

Then run the full backend suite once:

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all pass (139 existing + new tests from Tasks 1-6), pristine output.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/content/assembler.py backend/tests/test_content_assembler.py
git commit -m "feat(4c): ContentAssembler writes release_notes Drafts and advances last_release_tag"
```

---

### Task 7: Frontend types + `DRAFT_KIND_LABELS` + header target display

**Files:**
- Modify: `frontend/types/drafts.ts`
- Modify: `frontend/components/drafts/drafts-client.tsx`
- Test: `frontend/tests/drafts-client.test.tsx` (new file)

**Interfaces:**
- Produces: `DraftKind` includes `"release_notes"`; `ReleaseNotesContent` type; `DRAFT_KIND_LABELS.release_notes`. Consumed by `app/components/drafts/draft-content.tsx` (Task 8).

- [ ] **Step 1: Write the failing test**

First check `frontend/tests/` for the closest existing component test that mocks hooks the way this one will need to (`drafts-client.tsx` uses `useDrafts`, `useReviewDraft`, `useTriggerContentRun`, `useRepos`) — `frontend/tests/notification-settings-card.test.tsx` (from the prior Phase 4E build) is the most recent precedent for the `vi.spyOn(module, "hookName").mockReturnValue(...)` pattern; use that same style here.

Create `frontend/tests/drafts-client.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DraftsClient } from "@/components/drafts/drafts-client";
import * as useDraftsModule from "@/hooks/use-drafts";
import * as useReposModule from "@/hooks/use-repos";

const baseDraft = {
  id: 1,
  repo_id: 10,
  status: "pending" as const,
  created_at: "2026-07-24T00:00:00Z",
  reviewed_at: null,
};

function mockHooks(drafts: unknown[]) {
  vi.spyOn(useDraftsModule, "useDrafts").mockReturnValue({ data: drafts } as ReturnType<typeof useDraftsModule.useDrafts>);
  vi.spyOn(useDraftsModule, "useReviewDraft").mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDraftsModule.useReviewDraft>);
  vi.spyOn(useDraftsModule, "useTriggerContentRun").mockReturnValue({ mutate: vi.fn(), isPending: false } as unknown as ReturnType<typeof useDraftsModule.useTriggerContentRun>);
  vi.spyOn(useReposModule, "useRepos").mockReturnValue({ data: [{ id: 10, owner: "octocat", name: "hello-world" }] } as unknown as ReturnType<typeof useReposModule.useRepos>);
}

describe("DraftsClient release_notes header", () => {
  it("shows the release tag in the header for a release_notes draft", () => {
    mockHooks([{ ...baseDraft, kind: "release_notes", target: "v1.2.0", content: { suggested: "## Features", reason: "clear" } }]);
    render(<DraftsClient />);
    expect(screen.getByText(/Release notes/)).toBeInTheDocument();
    expect(screen.getByText(/\(v1\.2\.0\)/)).toBeInTheDocument();
  });

  it("does not append a target suffix for other kinds", () => {
    mockHooks([{ ...baseDraft, kind: "readme_suggestion", target: "readme", content: { current: "# Old", suggested: "# New", reason: null } }]);
    render(<DraftsClient />);
    expect(screen.getByText("README suggestion")).toBeInTheDocument();
    expect(screen.queryByText(/\(readme\)/)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/drafts-client.test.tsx`
Expected: FAIL — `release_notes` isn't a valid `DRAFT_KIND_LABELS` key yet (TypeScript will also flag `"release_notes"` as not assignable to `DraftKind` if strict enough, but the test's `content`/`kind` fields are loosely typed via the mocked `data` array, so the runtime failure is: no "Release notes" text renders, and no `(v1.2.0)` suffix renders).

- [ ] **Step 3: Add the type and label**

In `frontend/types/drafts.ts`, add after `SeoSuggestionContent`:

```ts
export type ReleaseNotesContent = MissingDocSuggestionContent;
```

Update the `DraftKind` union:

```ts
export type DraftKind =
  | "readme_suggestion"
  | "missing_doc_suggestion"
  | "topic_suggestion"
  | "seo_suggestion"
  | "release_notes";
```

In `frontend/components/drafts/drafts-client.tsx`, update `DRAFT_KIND_LABELS`:

```ts
const DRAFT_KIND_LABELS: Record<string, string> = {
  readme_suggestion: "README suggestion",
  missing_doc_suggestion: "Missing doc",
  topic_suggestion: "Topic suggestion",
  seo_suggestion: "SEO suggestion",
  release_notes: "Release notes",
} satisfies Record<DraftKind, string>;
```

Then update the card header JSX. Find this block:

```tsx
                  <p className="text-xs font-medium text-muted-foreground">
                    {draft.repo_id !== null ? repoNameById.get(draft.repo_id) ?? `repo #${draft.repo_id}` : "Account-level"}
                    {" · "}
                    {DRAFT_KIND_LABELS[draft.kind] ?? draft.kind}
                  </p>
```

Replace it with:

```tsx
                  <p className="text-xs font-medium text-muted-foreground">
                    {draft.repo_id !== null ? repoNameById.get(draft.repo_id) ?? `repo #${draft.repo_id}` : "Account-level"}
                    {" · "}
                    {DRAFT_KIND_LABELS[draft.kind] ?? draft.kind}
                    {draft.kind === "release_notes" && ` (${draft.target})`}
                  </p>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/drafts-client.test.tsx`
Expected: `2 passed`

Then run `npx tsc --noEmit` — expected clean (the `satisfies Record<DraftKind, string>` constraint now requires `release_notes` in `DRAFT_KIND_LABELS`, which is present).

- [ ] **Step 5: Commit**

```bash
git add frontend/types/drafts.ts frontend/components/drafts/drafts-client.tsx frontend/tests/drafts-client.test.tsx
git commit -m "feat(4c): add release_notes DraftKind, label, and header tag display"
```

---

### Task 8: `DraftContent` release-notes rendering

**Files:**
- Modify: `frontend/components/drafts/draft-content.tsx`
- Test: `frontend/tests/draft-content.test.tsx`

**Interfaces:**
- Consumes: `ReleaseNotesContent` type (Task 7).
- Produces: `DraftContent` renders `kind === "release_notes"` content.

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/draft-content.test.tsx`, inside the existing `describe("DraftContent", ...)` block, after the `missing_doc_suggestion` test:

```tsx
  it("renders suggested text and reason for release_notes", () => {
    render(<DraftContent kind="release_notes" content={{ suggested: "## Features\n- Dark mode", reason: "based on the raw release body" }} />);
    expect(screen.getByText(/Dark mode/)).toBeInTheDocument();
    expect(screen.getByText("based on the raw release body")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/draft-content.test.tsx -t release_notes`
Expected: FAIL — falls through to the `JSON.stringify` fallback branch, so neither `Dark mode` nor the reason text render as the test expects (the raw JSON string renders instead, which doesn't match `screen.getByText(/Dark mode/)`'s expectation of a standalone text node).

- [ ] **Step 3: Add the release_notes branch**

In `frontend/components/drafts/draft-content.tsx`, add a new branch immediately after the existing `missing_doc_suggestion` block:

```tsx
  if (kind === "release_notes" && isMissingDocSuggestion(content)) {
    return (
      <div>
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-xs">{content.suggested}</pre>
        <Reason reason={content.reason} />
      </div>
    );
  }
```

(This reuses `isMissingDocSuggestion` as the type guard since `ReleaseNotesContent` is a type alias of the identical shape — matches the file's existing convention of one explicit branch per `kind` even when two kinds share a shape.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/draft-content.test.tsx`
Expected: all pass, including the new test, no regressions.

Then run the full frontend verification:

Run: `cd frontend && npx tsc --noEmit && npx eslint . && npx vitest run && npx next build`
Expected: all clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/drafts/draft-content.tsx frontend/tests/draft-content.test.tsx
git commit -m "feat(4c): DraftContent renders release_notes drafts"
```

---

## Final whole-branch review

After all 8 tasks: dispatch a final whole-branch code reviewer (opus, per this project's established pattern) covering the full diff since this plan's first commit. Confirm: backend full suite passes with no warnings, `pip-audit` clean; frontend `tsc`/`eslint`/`vitest`/`next build` all clean; `last_release_tag` genuinely only advances on `task.valid`; the empty-body skip genuinely prevents fabricated release notes; no regression to any existing `readme_suggestion`/`missing_doc_suggestion`/`topic_suggestion`/`seo_suggestion` task's behavior from the new `release_notes` branch anywhere it was added (Analyzer, Synthesizer, Assembler, frontend). Then update `.agile-v/REQUIREMENTS.md` (new REQ), `.agile-v/STATE.md`, `docs/PROJECT_PLAN.md` (mark 4C's release-notes scope done), and `docs/PROJECT_WALKTHROUGH.md` before the Product Owner's Gate 2 review — same sequence as every prior sub-project.
