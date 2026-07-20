<!-- Cycle: C1 -->
# Build Manifest — C1 (Backend)

Built via `superpowers:subagent-driven-development` (11 tasks, fresh implementer + reviewer subagent per task, plus 1 final whole-branch review wave) prior to Agile-V adoption on this project; retroactively cataloged here for traceability. Revision suffix `.N` marks a post-review fix round on the same artifact.

| ART-ID | File | REQ | Task | Commits |
|---|---|---|---|---|
| ART-0001 | `backend/app/config.py`, `backend/app/main.py`, `backend/Dockerfile`, `backend/.dockerignore`, `backend/.env.example` | REQ-0007, REQ-0009 | Task 1 | 7bf1996 |
| ART-0001.1 | `backend/pyproject.toml` (pytest-asyncio config) | — (test infra) | Task 1 fix | 829b44b |
| ART-0002 | `backend/app/db.py`, `backend/app/models.py`, `backend/alembic/` | REQ-0001, REQ-0003, REQ-0004, REQ-0005, REQ-0008, REQ-0009 | Task 2 | 6248a5e |
| ART-0003 | `backend/app/deps.py`, `backend/app/api/repos.py` | REQ-0007 | Task 3 | d84bc01, 4137960, 3e4d623(revert) |
| ART-0004 | `backend/app/github_client.py` | REQ-0002, REQ-0000 | Task 4 | 08f7b02 |
| ART-0005 | `backend/app/pipeline/base.py`, `extractor.py`, `preprocessor.py` | REQ-0001, REQ-0002, REQ-0003 | Task 5 | 0657842 |
| ART-0006 | `backend/app/pipeline/analyzer.py`, `optimizer.py` | REQ-0001 | Task 6 | d7ffb06 |
| ART-0007 | `backend/app/llm_router.py` | REQ-0004 | Task 7 | 3462e79 |
| ART-0007.1 | `backend/app/llm_router.py` (sibling-model retry fix) | REQ-0004 | Task 7 fix | 37e7ff9 |
| ART-0008 | `backend/app/pipeline/synthesizer.py`, `validator.py` | REQ-0005 | Task 8 | 58e4a3f |
| ART-0008.1 | `backend/app/pipeline/synthesizer.py` (graceful-degrade fix) | REQ-0005 | Task 8 fix | 710fca2 |
| ART-0009 | `backend/app/pipeline/assembler.py`, `runner.py` | REQ-0001 | Task 9 | 0f45f93 |
| ART-0009.1 | `backend/app/pipeline/runner.py` (session rollback fix — CRITICAL) | REQ-0001 | Task 9 fix | 67c09eb |
| ART-0010 | `backend/app/api/insights.py`, `recommendations.py`, `runs.py`, `providers.py`, `backend/app/pipeline/jobs.py` | REQ-0006, REQ-0008 | Task 10 | 4d9ebbb |
| ART-0010.1 | `backend/app/pipeline/jobs.py` (client-reuse fix) | REQ-0008 | Task 10 fix | b86ca7d |
| ART-0011 | `backend/app/events.py`, `backend/app/api/events.py`, `backend/app/main.py` (scheduler) | REQ-0008 | Task 11 | 9154326 |
| ART-0012 | `backend/app/pipeline/assembler.py` (benchmark/referrer/path persistence), `preprocessor.py` (watchers fix), `api/insights.py` (date type), `tests/test_pipeline_integration.py` | REQ-0001, REQ-0002, REQ-0003 | Final review fix | 03d66fc |

## Frontend (C1 continuation — not yet built)

No artifacts yet for REQ-0010 – REQ-0014.
