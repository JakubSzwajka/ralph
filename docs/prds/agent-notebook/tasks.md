---
prd: agent-notebook
generated: 2026-02-28
last-updated: 2026-02-28
---

# Tasks: Agent Notebook

> Summary: Add a shared notebook.md to PRD directories so agents can pass context to each other during implementation.

## Task List

- [x] **1. Update init script to create notebook.md** — copy notebook template alongside README.md
- [x] **2. Add notebook section to SKILL.md** — document the read/append contract for agents
- [x] **3. Add notebook to existing agent-notebook PRD** — bootstrap this PRD's own notebook as a smoke test

---

### 1. Update init script to create notebook.md
<!-- status: done -->

Add a line to `init_prd.sh` that copies `assets/templates/notebook.md` into the new PRD directory alongside README.md. No sed substitution needed — the template is static.

**Files:** `~/.agents/skills/smart-prd/scripts/init_prd.sh`
**Depends on:** —
**Validates:** Running `init_prd.sh test-slug` creates both `README.md` and `notebook.md` in the target directory.

---

### 2. Add notebook section to SKILL.md
<!-- status: done -->

Add an "Agent Notebook" section to SKILL.md that tells agents: (1) read `notebook.md` before starting any task from a PRD, (2) append a short note when you discover something worth sharing — constraints, decisions, gotchas, patterns. Reference the suggested note format from the template. Keep it under 15 lines — this is a contract, not a tutorial.

**Files:** `~/.agents/skills/smart-prd/SKILL.md`
**Depends on:** —
**Validates:** SKILL.md contains an "Agent Notebook" section with clear read/append instructions.

---

### 3. Add notebook to existing agent-notebook PRD
<!-- status: done -->

Copy the notebook template into `docs/prds/agent-notebook/notebook.md` to bootstrap this PRD's own notebook. Serves as a smoke test that the template works in practice.

**Files:** `docs/prds/agent-notebook/notebook.md`
**Depends on:** —
**Validates:** `docs/prds/agent-notebook/notebook.md` exists with the template header and suggested format comment.

---
