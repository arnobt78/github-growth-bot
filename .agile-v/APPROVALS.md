# Human Gate Approval Records

Append-only. `GATE-XXXX` with Gate type, Cycle, Scope, Decision (Approved/Conditional/Rejected), Conditions, Approver (full name), Role/Authority, Timestamp (ISO 8601), Signature Method, Evidence Reference (commit hash). Durable HITL: closing entries include `resume_token` + `INTERRUPT-ID` matching CHECKPOINTS.md.

**Regulatory context:** non-regulated → minimum signature is this file's entry with name + timestamp (per `agile-v-compliance`'s signature table); no digital signature/authority-matrix verification required.

---

## GATE-0001

- **Gate type:** Gate 2 (Acceptance)
- **Cycle:** C1
- **Scope:** Backend sub-scope (REQ-0000–REQ-0009) — see VALIDATION_SUMMARY.md, EVAL_RESULTS.md
- **Decision:** Approved
- **Conditions:** None. (Deployment itself remains separately gated — RISK-0005/RISK-0006 pre-deploy actions and POL-0006 still apply before any Coolify/Vercel release.)
- **Approver:** Arnob Mahmud
- **Role/Authority:** Project Owner / Sole Stakeholder (per config.json authority_matrix)
- **Timestamp:** 2026-07-20
- **Signature Method:** Explicit selection via AskUserQuestion in chat interface (non-regulated context — name + timestamp is the required minimum per `agile-v-compliance`'s signature table)
- **Evidence Reference:** commits `03d66fc` (final backend fix, HEAD of verified work) and `e90ac17` (governance bootstrap); pushed to `https://github.com/arnobt78/github-growth-bot` at `main`
- **Closes:** `INT-0001` (CHECKPOINTS.md), `resume_token=GATE2-C1-BACKEND-20260720`

---

## GATE-0002

- **Gate type:** Gate 2 (Acceptance)
- **Cycle:** C1
- **Scope:** Frontend sub-scope (REQ-0010–REQ-0014) — 20-task subagent-driven build (`docs/superpowers/plans/2026-07-20-github-growth-bot-frontend.md`), final whole-branch review, one escalated backend fix (cascade-delete on repo FKs), one post-plan deep audit that found and closed a dependency-CVE gap (RISK-0013)
- **Decision:** Approved
- **Conditions:** None for source acceptance. Actual Vercel deployment remains separately gated per POL-0006 — REQ-0014 stays `implemented [C1]` (guardrail code verified, not yet live) until that deploy runs under its own Gate 2.
- **Approver:** Arnob Mahmud
- **Role/Authority:** Project Owner / Sole Stakeholder (per config.json authority_matrix)
- **Timestamp:** 2026-07-21
- **Signature Method:** Explicit instruction in chat ("commit in github if all okay as flawless after code review") following a full deep-audit report — non-regulated context, name + timestamp is the required minimum per `agile-v-compliance`'s signature table
- **Evidence Reference:** commit `24d31d9` (dependency-CVE fix, HEAD of accepted work) through the full frontend build range; pushed to `https://github.com/arnobt78/github-growth-bot` at `main`
- **Closes:** `INT-0002` (CHECKPOINTS.md), `resume_token=GATE2-C1-FRONTEND-20260721`

Next entry will be `GATE-0003`.
