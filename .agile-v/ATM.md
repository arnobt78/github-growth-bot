<!-- Cycle: C1 -->
# Assurance Traceability Matrix (ATM)

REQ → Artifact → Test → Validation status. Partitioned by cycle per `agile-v-lifecycle`.

## Cycle C1

| REQ | ART | TC | Validation | Notes |
|---|---|---|---|---|
| REQ-0000 | ART-0004 | TC-0005–0010 | verified | No write-capable GitHub method exists; confirmed by final review |
| REQ-0001 | ART-0005, ART-0006, ART-0009, ART-0009.1, ART-0012 | TC-0011–0015, TC-0025–0026, TC-0029 | verified | Includes CAPA-0001 regression test |
| REQ-0002 | ART-0004, ART-0005, ART-0012 | TC-0005–0012 | verified | Includes CAPA-0002 fix (benchmarks persistence) |
| REQ-0003 | ART-0002, ART-0005, ART-0012 | TC-0002, TC-0011–0012 | verified | Includes CAPA-0002 fix (watchers metric) |
| REQ-0004 | ART-0007, ART-0007.1 | TC-0016–0019 | verified | Includes fallback-order + sibling-retry fix |
| REQ-0005 | ART-0008, ART-0008.1 | TC-0020–0024 | verified | Includes graceful-degrade fix |
| REQ-0006 | ART-0003, ART-0010 | TC-0003–0004, TC-0027 | verified | Keyword-free endpoint naming confirmed |
| REQ-0007 | ART-0001, ART-0003 | TC-0001, TC-0003–0004 | verified | require_api_key confirmed on every router |
| REQ-0008 | ART-0002, ART-0010, ART-0010.1, ART-0011 | TC-0027–0028 | verified | Client-reuse fix; scheduler now uses `lifespan` (RISK-0003 resolved 2026-07-22) |
| REQ-0009 | ART-0001 | — | approved, not deployed | Manual VPS deploy steps pending |
| REQ-0010 | frontend/app/*, components/{overview,repo-detail,recommendations,runs,settings}/ | frontend test suite (8 tests) | verified | Frontend dashboard, Gate 2 (GATE-0002) |
| REQ-0011 | frontend/hooks/*, providers/*, app/api/events/route.ts | frontend test suite | verified | SSE + TanStack Query invalidation |
| REQ-0012 | frontend/lib/*, hooks/*, providers/*, types/api.d.ts, components/ui/* | frontend test suite | verified | Shared structure, generated types |
| REQ-0013 | frontend/lib/backend-client.ts, route-handler.ts, app/api/**/route.ts | frontend test suite | verified | API key server-side only |
| REQ-0014 | next.config.ts, vercel.json, app/robots.ts | — | implemented, not deployed | Vercel deploy pending |
| REQ-0015 | frontend/auth.ts, proxy.ts, app/sign-in/* | live OAuth E2E (2026-07-22) | verified | Gate 2 (GATE-0003) |
| REQ-0016 | backend/app/models.py, alembic 9bb84cb18218/2d5539f16118, scripts/backfill_owner_user.py | backend test suite (76 tests) | verified | Per-user data isolation |
| REQ-0017 | backend/app/internal_auth.py, token_crypto.py, deps.py, frontend/lib/internal-auth.ts | backend + frontend test suites | verified | Defense-in-depth auth chain |
| REQ-0018 | backend/app/pipeline/jobs.py, github_client.py, events.py, api/{runs,events}.py | backend test suite | verified | Per-user pipeline + circuit breaker |
| REQ-0019 | backend/app/rate_limit.py, api/{repos,runs}.py | backend test suite | verified | Per-user/IP rate limiting |
| REQ-0020 | backend/app/models.py::Draft, api/drafts.py, frontend/hooks/use-drafts.ts, components/drafts/* | backend test suite (test_drafts_api.py, 7 tests) + frontend SSE test | verified | Phase 4A, draft-and-approve infra |

**Unlinked-artifact check:** REQ-0010–0020 don't use the `ART-XXXX`/`TC-XXXX` numbering from `BUILD_MANIFEST.md` (that manifest only covers the backend's original 11-task build) — they reference file paths and test-suite names directly instead, consistent with how those sub-scopes' own governance was tracked in `STATE.md`/`APPROVALS.md`. Re-run this check at every Gate 2 per Compliance Auditor duty.
