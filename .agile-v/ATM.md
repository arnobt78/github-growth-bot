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
| REQ-0008 | ART-0002, ART-0010, ART-0010.1, ART-0011 | TC-0027–0028 | verified | Client-reuse fix; scheduler lifespan untested (RISK-0003) |
| REQ-0009 | ART-0001 | — | approved, not deployed | Manual VPS deploy steps pending |
| REQ-0010 | — | — | approved, not started | Frontend |
| REQ-0011 | — | — | approved, not started | Frontend |
| REQ-0012 | — | — | approved, not started | Frontend |
| REQ-0013 | — | — | approved, not started | Frontend |
| REQ-0014 | — | — | approved, not started | Frontend |

**Unlinked-artifact check:** none — every `ART-XXXX` in BUILD_MANIFEST.md maps to at least one REQ above. Re-run this check at every Gate 2 per Compliance Auditor duty.
