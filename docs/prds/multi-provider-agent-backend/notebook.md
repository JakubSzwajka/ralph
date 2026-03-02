# Notebook

Shared scratchpad for agents working on this PRD. Read before starting a task. Append notes as you go.

---

<!--
Suggested note format (not enforced):

### [Task N] Short title
- **Found:** what you discovered
- **Decision:** what you chose and why
- **Watch out:** gotchas for future agents
-->

### [Task planning] Multi-provider decomposition
- **Found:** Provider coupling currently lives in `ralph/core/loop.py` (SDK query + block parsing), `ralph/core/config.py` (Claude permission type import), and CLI/docs text.
- **Decision:** Split work into provider primitives, adapter registry, Claude parity extraction, Codex adapter, then loop wiring/validation and tests.
- **Watch out:** Repo currently has no committed test suite under `tests/`; add deterministic provider tests that do not require external credentials.
