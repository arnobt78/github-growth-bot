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

---

## GATE-0003

- **Gate type:** Gate 2 (Acceptance)
- **Cycle:** C1
- **Scope:** Multi-tenant SaaS sub-scope (REQ-0015–REQ-0019) — 18-task subagent-driven build (`docs/superpowers/plans/2026-07-21-github-growth-bot-multi-tenant-saas.md`), whole-backend review (1 fix round, RISK-0016), final whole-branch review (1 fix round, RISK-0017), local dev Postgres migrated to the multi-tenant schema, live end-to-end GitHub OAuth sign-in verified in a real browser against a real registered OAuth App (real avatar/username rendered in the nav sidebar, per-user dashboard correctly empty for the new tenant)
- **Decision:** Approved
- **Conditions:** None. (Deployment itself remains separately gated per POL-0006 — REQ-0015–REQ-0019 stay scoped to "code verified, live locally" until the actual VPS/Vercel deploy runs under its own Gate 2. The design spec's one flagged open risk — whether `public_repo` OAuth scope is sufficient for GitHub's Traffic API on a real tracked repo — is deferred to the first repo added post-launch, not blocking this acceptance.)
- **Approver:** Arnob Mahmud
- **Role/Authority:** Project Owner / Sole Stakeholder (per config.json authority_matrix)
- **Timestamp:** 2026-07-22
- **Signature Method:** Explicit selection via AskUserQuestion in chat interface (non-regulated context — name + timestamp is the required minimum per `agile-v-compliance`'s signature table)
- **Evidence Reference:** commit `7f0b127` (governance traceability update, HEAD of accepted work); pushed to `https://github.com/arnobt78/github-growth-bot` at `main`
- **Closes:** `INT-0003` (CHECKPOINTS.md), `resume_token=GATE2-C1-MULTITENANT-20260722`

---

## GATE-0004

- **Gate type:** Gate 2 (Acceptance)
- **Cycle:** C1
- **Scope:** Phase 4A automation engine core (REQ-0020) — 3-task subagent-driven build (`docs/superpowers/plans/2026-07-22-phase4a-automation-engine-core.md`), one fix round on Task 1, final whole-branch review clean (opus). Plus a post-build deep audit (fresh opus subagent, independent of the build) that found and closed 2 real type-drift gaps (`ProviderStatusOut` response_model, `upsertUser`'s hand-typed payload/return), and a GitGuardian-flagged test-only dummy secret fixed at the source (RISK-0018).
- **Decision:** Approved
- **Conditions:** None. (Deployment itself remains separately gated per POL-0006.)
- **Approver:** Arnob Mahmud
- **Role/Authority:** Project Owner / Sole Stakeholder (per config.json authority_matrix)
- **Timestamp:** 2026-07-23
- **Signature Method:** Explicit instruction in chat ("commit in github if all okay as flawless after code review") following a full deep-audit report — non-regulated context, name + timestamp is the required minimum per `agile-v-compliance`'s signature table
- **Evidence Reference:** commit `da64454` (documentation currency update, HEAD of accepted work); pushed to `https://github.com/arnobt78/github-growth-bot` at `main`
- **Closes:** Phase 4A Stage 5 acceptance (no `CHECKPOINTS.md` interrupt was opened for this sub-scope — same as multi-tenant SaaS, approval requested directly via Evidence Summary rather than a durable interrupt)

Next entry will be `GATE-0005`.
