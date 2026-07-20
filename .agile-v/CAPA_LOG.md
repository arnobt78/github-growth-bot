# CAPA Log

`CAPA-XXXX` with Cycle, Trigger, Nonconformity, Root Cause (5-Whys), Corrective Action, Preventive Action, Effectiveness Verification, Status, Owner. Triggers: CRITICAL finding, recurring NC across cycles, regression FAIL with no CR, 3-attempt escalation.

---

## CAPA-0001

**Cycle:** C1
**Trigger:** CRITICAL finding (Task 9 task-review)
**Nonconformity:** `PipelineRunner.run_for_repo()` caught a stage's exception per-stage (correct isolation intent) but never called `self.db.rollback()` before the runner's own subsequent `StageRun` insert/commit. When a stage sharing the runner's DB session (Preprocessor, Assembler) failed via a real constraint violation, the poisoned SQLAlchemy session caused the runner's *own* logging write to raise `PendingRollbackError`, uncaught — crashing the entire pipeline run. This was the exact failure mode Task 9 (Assembler + PipelineRunner) existed to prevent.

**Root Cause (5-Whys):**
1. Why did the pipeline crash on a DB error? → The runner's `StageRun` insert after a failed stage raised `PendingRollbackError`.
2. Why did that insert raise? → The session was left in a "pending rollback" state by the failed stage's own failed commit.
3. Why was the session left poisoned? → SQLAlchemy requires an explicit `rollback()` after any exception during a flush/commit; none was called.
4. Why wasn't `rollback()` called? → The implementation task's brief specified per-stage exception catching for isolation, but didn't explicitly call out session-state cleanup as part of that contract — the plan's Task 9 spec was correct on *intent* (never crash) but incomplete on the *mechanism* needed to guarantee it for DB-sharing stages.
5. Why didn't the initial test suite catch it? → The only test at implementation time (`_BoomStage` raising a plain `RuntimeError`) never touched the shared DB session, so it never exercised the poisoning path — a coverage gap in the original task brief's example test, not implementer error.

**Corrective Action:** Added `self.db.rollback()` as the first statement in `PipelineRunner`'s per-stage `except Exception` block (`backend/app/pipeline/runner.py`), before any other error-handling logic. Commit `67c09eb`.

**Preventive Action:** Added a regression test (`test_runner_rolls_back_shared_session_after_stage_db_integrity_error` in `backend/tests/test_runner.py`) using a real NOT-NULL constraint violation (not a synthetic exception) to prove the fix and guard against recurrence. Documented in DECISION_LOG DEC-0013 and RISK_REGISTER RISK-0002 so future cycles touching shared-session pipeline code are aware of this failure class.

**Effectiveness Verification:** Task reviewer independently reproduced both RED (bug present without fix: `PendingRollbackError` propagates) and GREEN (bug absent with fix) rather than trusting the implementer's report. Full backend suite (26/26 at the time, later 30/30) re-run clean. Re-review verdict: Approved.

**Status:** verified-effective — closed
**Owner:** Arnob Mahmud

---

## CAPA-0003

**Cycle:** C1
**Trigger:** Human-reported — sensitive data exposed in a public repository
**Nonconformity:** The controller agent's first git commit (`git add -A` followed later by a targeted `git add <one file>` without first clearing the stale staging area) accidentally included 8 of the user's personal cross-project reference docs, 3 of which contained real infrastructure details: Hetzner VPS IP address, Coolify internal sslip.io hostnames, and the subdomains/names/ports of several *other* unrelated projects the user runs on the same VPS. This commit was later pushed to a public GitHub repository (`arnobt78/github-growth-bot`), exposing that infrastructure topology publicly. A subsequent commit removed the files from the working tree but did not remove them from git history — the content remained fully retrievable from the public repo until this CAPA's corrective action.

**Root Cause (5-Whys):**
1. Why were sensitive docs pushed publicly? → They were present in the first commit's content.
2. Why were they in the first commit? → `git add -A` (run to investigate unexpected files found in the project directory) staged them, and staging was never cleared before the intended commit.
3. Why wasn't staging cleared? → The controller ran a follow-up `git add <specific-file>` assuming it would scope the commit to just that file, not accounting for the fact that `git commit` commits the full index, not just the most recent `git add` target.
4. Why didn't a pre-commit check catch this? → No `git status`/`git diff --stat` review step existed between staging and committing at that point in the session — the controller trusted the most recent `add` command's scope rather than verifying the actual index state.
5. Why did a later "removal" commit fail to actually fix it? → Removing a file in a new commit only affects the current tree snapshot; it does not remove the file's content from earlier commits still reachable in branch history — a git mechanics gap in the initial fix attempt (by the user, addressed collaboratively once flagged).

**Corrective Action:** Full remediation performed: (1) local git history rewritten with `git-filter-repo` to purge the 3 files from every commit — superseded when (2) the user independently ran `rm -rf .git` locally and deleted the GitHub repository entirely, after which the controller re-initialized git from scratch (`git init`), staged only current, `.gitignore`-respecting content (verified empty grep for the 3 filenames before committing), created one clean commit, and pushed to a newly created repository at the same URL (`https://github.com/arnobt78/github-growth-bot`). Old repository confirmed deleted via GitHub API (404-equivalent response) before recreation.

**Preventive Action:** Documented in this CAPA and in DECISION_LOG DEC-0019 as a standing process rule: after any broad `git add -A`/`git add .`, always run `git status` (and `git diff --stat` for staged content) to review the full index before committing — never trust the scope of the most recent `add` command alone. Applies to all future cycles/agents on this project and is a good general rule to carry into other projects.

**Effectiveness Verification:** `git log --all -- <the 3 filenames>` returns empty on the rebuilt repository (confirmed twice — once after the filter-repo rewrite, once after the full rebuild). GitHub API search for the old repository returns a "does not exist" validation error, confirming deletion. New repository's single commit reviewed file-by-file (`git status --short`) before commit to confirm no other unwanted local files (e.g. `.claude/settings.json`, a local tooling config file) were accidentally included.

**Status:** verified-effective — closed
**Owner:** Arnob Mahmud

---

## CAPA-0002

**Cycle:** C1
**Trigger:** Important finding at final whole-branch review (post-Gate, whole-codebase visibility)
**Nonconformity:** `Assembler` computed but never persisted `BenchmarkRepo`/`Referrer`/`PopularPath` data despite `Preprocessor` populating it in `ctx.normalized` every run. `GET /repos/{id}/benchmarks` — a documented API endpoint (REQ-0002) — would always return `[]` in production. Separately, `Preprocessor` read `watchers_count` for the `watchers` metric, which GitHub's REST API returns as an alias for `stargazers_count`, not a distinct value — silently tracking a duplicate metric instead of real watcher/subscriber counts.

**Root Cause (5-Whys):**
1. Why did `/benchmarks` return empty? → `Assembler` never wrote `BenchmarkRepo` rows.
2. Why didn't `Assembler` write them? → Task 9's brief only specified persisting `Snapshot` + `Recommendation`.
3. Why did the brief omit benchmark/referrer/path persistence? → A scope gap in the implementation plan (`docs/superpowers/plans/2026-07-20-github-growth-bot-backend.md`) written before implementation began — the design spec (REQ-0002/REQ-0003) required this data be tracked, but the plan's Task 9 breakdown under-specified the Assembler's write surface.
4. Why wasn't this caught during per-task review? → Each task reviewer only had visibility into their own task's diff, per the Context Engineering rule (fresh context per subagent) — no single task's diff showed the gap between "data computed" (Task 5) and "data persisted" (Task 9); it only became visible with whole-codebase context at the final review.
5. Why did `watchers` duplicate `stars`? → A field-name assumption in the original plan (`repo_data.get("watchers_count", 0)`) that wasn't checked against GitHub's actual API semantics during planning.

**Corrective Action:** `Assembler.run()` extended to persist `BenchmarkRepo`/`Referrer`/`PopularPath` rows from `ctx.normalized`; `Preprocessor` switched to `subscribers_count`. Commit `03d66fc`.

**Preventive Action:** Added `test_pipeline_integration.py`, running the real 7-stage pipeline end-to-end (not stage-by-stage) — the class of gap this CAPA addresses (data computed in one stage, silently never consumed by a later one) is exactly what an end-to-end test catches that isolated unit tests cannot. Recorded in DECISION_LOG DEC-0015. Process learning applied going forward (see PLAYBOOK.md): plan-writing for future cycles should explicitly trace each REQ's full data lifecycle (computed → persisted → exposed) across task boundaries, not just per-task interfaces.

**Effectiveness Verification:** Fix independently re-verified by a dedicated verification subagent against the diff and live source (not the report alone): field mappings checked against `models.py` column definitions, `subscribers_count` fixture value deliberately set different from `stargazers_count` to prove the test isn't tautological, integration test confirmed to use real stage classes (not fakes). Full suite 30/30 passing.

**Status:** verified-effective — closed
**Owner:** Arnob Mahmud
