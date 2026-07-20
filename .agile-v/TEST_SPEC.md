<!-- Cycle: C1 -->
# Test Specification — C1 (Backend)

30 tests across 11 files, all origin [C1]. Written test-first (TDD) per task by implementer subagents; existence and quality independently checked by task-reviewer subagents (real-behavior assertions required, mocks only at true I/O boundaries — GitHub API via `httpx.MockTransport`, LLM providers via `httpx.MockTransport`/`MagicMock`, never the system under test itself).

| TC-ID | File | Covers | REQ | Cycle |
|---|---|---|---|---|
| TC-0001 | `tests/test_health.py` | Health endpoint | REQ-0007 (exemption) | [C1] |
| TC-0002 | `tests/test_models.py` | ORM create/query | REQ-0001, REQ-0003 | [C1] |
| TC-0003–0004 | `tests/test_repos_api.py` | Repo CRUD, API-key rejection | REQ-0007 | [C1] |
| TC-0005–0010 | `tests/test_github_client.py` | GitHub REST wrapper (repo, traffic, referrers, paths, README b64, has_file, search) | REQ-0002, REQ-0000 | [C1] |
| TC-0011–0012 | `tests/test_extractor_preprocessor.py` | Extractor raw population, Preprocessor delta computation, watchers=subscribers_count | REQ-0002, REQ-0003 | [C1] |
| TC-0013–0015 | `tests/test_analyzer_optimizer.py` | Finding generation (license/topics/benchmark-gap/referrer-spike), impact-effort ranking | REQ-0001 | [C1] |
| TC-0016–0019 | `tests/test_llm_router.py` | Provider fallback order, sibling-model retry on any failure, all-providers-fail | REQ-0004 | [C1] |
| TC-0020–0024 | `tests/test_synthesizer_validator.py` | JSON synthesis, number-validation (accept real / reject fabricated), graceful degrade on LLM failure / non-list JSON | REQ-0005 | [C1] |
| TC-0025–0026 | `tests/test_runner.py` | Per-stage isolation on plain exception, session rollback on real IntegrityError (regression test for CAPA-0001) | REQ-0001 | [C1] |
| TC-0027 | `tests/test_read_endpoints.py` | Snapshots/insights/recommendations/runs/providers read paths | REQ-0006 | [C1] |
| TC-0028 | `tests/test_events.py` | Broadcaster pub/sub, SSE auth | REQ-0008 | [C1] |
| TC-0029 | `tests/test_pipeline_integration.py` | Full 7-stage pipeline through real `PipelineRunner`, production wiring (`build_stages` pattern) | REQ-0001 | [C1] |

**Regression baseline for C2+:** all 30 above — any future cycle touching backend files must re-run this full suite (`cd backend && .venv/bin/python -m pytest -v`) before Gate 2, per `agile-v-lifecycle` regression rules.

**Known coverage gaps** (tracked, not blocking — see RISK_REGISTER): no test drives the scheduler's `startup`/`shutdown` lifespan handlers (TestClient fixtures don't use the lifespan context-manager form); no test hits the live SSE stream end-to-end through the module-singleton broadcaster with a real published event.
