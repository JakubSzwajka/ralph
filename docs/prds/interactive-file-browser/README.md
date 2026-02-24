---
status: draft
date: 2026-02-24
author: kuba
gh-issue: ""
---

# Interactive File Browser on Startup

## Problem

Ralph currently requires PRD and tasks paths as CLI arguments (`--prd`, `--tasks`). If you forget to pass them, it defaults to `PRD.md` in the current directory — which may not exist or may not be the one you want. There's no way to browse available PRDs or task files before starting a run. This adds friction, especially when a project has multiple PRDs or task lists under `docs/prds/`.

## Proposed Solution

Add an interactive startup mode using Rich's tree/prompt widgets. When ralph is launched without explicit `--prd` or `--tasks` arguments, it presents a file tree browser that lets you:

1. Browse and select a PRD file from `docs/prds/` (or a configurable root)
2. Browse and select a tasks file/directory
3. Confirm selections and proceed to the agent loop

The browser should show a tree view of available files with keyboard navigation. If `--prd` and `--tasks` are provided on the CLI, skip the browser entirely (preserve current behavior for scripted usage).

## Key Cases

- Launch with no args → show interactive browser, scan `docs/prds/` for PRD directories
- Each PRD directory shown with its status from frontmatter (draft/accepted/in-progress)
- Select a PRD → auto-detect sibling task files in the same directory
- Option to manually pick a different tasks file
- Arrow keys / vim keys to navigate, Enter to select
- Confirm selection screen before starting the agent loop
- Graceful fallback if no PRDs found (prompt for manual path or create new)

## Out of Scope

- Creating new PRDs from the browser (use `/prd` skill for that)
- Editing PRD content inline
- Multi-PRD selection (one PRD per run)
- Remote/network file browsing

## Open Questions

- Should we use `textual` (full TUI framework) or stick with Rich prompts/tree? Textual gives proper keyboard nav but adds a dependency.
- Should the browser also show recent runs / history?
- Default scan directory: hardcode `docs/prds/` or make configurable in `~/.ralph/config.json`?

## References

- Current CLI: `ralph/cli.py` — argparse-based entry point
- Rich library: already a dependency for TUI status panel
- Textual: Rich-adjacent TUI framework (same author), would need adding as dependency
