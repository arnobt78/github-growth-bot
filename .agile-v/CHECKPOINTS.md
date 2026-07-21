# Checkpoints (Durable Human-Gate Interrupts)

Append-only. On pause: `PENDING` row with `resume_token`. Resume only from file state + matching token in `APPROVALS.md`/`STATE.md`. If `due_at` passes while `PENDING`, escalate per project policy and append `ESCALATED`/`EXPIRED` before forcing resume.

| INTERRUPT-ID | Cycle | Gate | Scope | Status | resume_token | Opened | due_at |
|---|---|---|---|---|---|---|---|
| INT-0001 | C1 | Gate 2 | Backend sub-scope acceptance (REQ-0000–REQ-0009) — see VALIDATION_SUMMARY.md | CLOSED (Approved, GATE-0001) | GATE2-C1-BACKEND-20260720 | 2026-07-20 | — (personal project, no SLA clock) |
| INT-0002 | C1 | Gate 2 | Frontend sub-scope acceptance (REQ-0010–REQ-0014) — 20-task subagent-driven build, final whole-branch review, escalated cascade-delete fix, post-plan CVE audit/fix | CLOSED (Approved, GATE-0002) | GATE2-C1-FRONTEND-20260721 | 2026-07-21 | — (personal project, no SLA clock) |
