---
status: draft
date: 2026-02-28
author: kuba
gh-issue: ""
---

# Agent Notebook — shared scratchpad for PRD implementation context

## Problem

Agents working on PRD tasks lose context between sessions. When agent A discovers an API quirk, an architectural constraint, or makes a non-obvious decision during task 1, agent B starting task 3 has no way to know. Each agent re-discovers the same things or makes conflicting choices. There's no feedback loop from implementation back into the PRD directory.

## Proposed Solution

Add a `notebook.md` file to each PRD directory. The init script auto-creates it alongside README.md. Agents are instructed to append short notes during implementation and read existing notes before starting work. The SKILL.md gets a new section explaining the notebook contract.

The notebook is freeform with a suggested note template — not enforced, just nudged. Notes accumulate chronologically and are never deleted.

## Key Cases

- Init script creates `notebook.md` with header and suggested template when creating a new PRD
- Agents read notebook.md before starting any task from the PRD
- Agents append a note after discovering something worth sharing (constraint, decision, gotcha, pattern)
- Notebook stays useful as a scannable log — no noise, no ceremony
- Existing PRDs without a notebook can have one added manually or by re-running a setup step

## Out of Scope

- Structured/machine-parseable format — this is for agents reading prose
- Per-task notebooks — one per PRD is enough
- Automatic summarization or pruning of old notes
- Validation script enforcement of notebook content

## Open Questions

- Should the notebook have a soft line cap like README (250 lines)?

## References

- smart-prd skill: `~/.agents/skills/smart-prd/SKILL.md`
