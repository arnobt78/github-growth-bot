# Revalidation Log

`REVAL-XXXX` with Date, Trigger, Scope, Results, Decision, Reviewer. Triggers: LLM model change, runtime/platform major update, skill file change, >5 CRs since last revalidation, 12-month interval.

No revalidations performed yet — project is newly under Agile-V governance as of 2026-07-20 (C1). First scheduled trigger: 12-month interval from 2026-07-20 (2027-07-20), or earlier if any of the following occur first:

- Groq deprecates `llama-3.1-8b-instant` / `llama-3.3-70b-versatile` on 2026-08-16 (not used by this codebase, but confirms the provider's deprecation cadence — spot-check `app/llm_router.py`'s allowlist against Groq's current model catalog at that date).
- Any change to `app/llm_router.py`'s provider/model configuration.
- FastAPI major version bump (currently pinned `fastapi==0.115.6`) — re-check `@app.on_event` deprecation status (RISK-0003).
- `config.json`'s `model_versions` (Claude tiers used for agent tooling) change.
