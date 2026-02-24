---
status: done
date: 2026-02-24
author: kuba
gh-issue: ""
---

# TUI Control Panel — Ralph as a Persistent Textual App

## Problem

Ralph is currently a one-shot CLI: pass args, watch a non-interactive Rich status ticker, exit. You can't pause the agent, scroll output, track task-level progress, browse PRDs, review past runs, or chain runs — you have to restart the process each time. As ralph gains features (file browser, run history, task tracking), bolting them onto argparse and Rich Live won't scale. Ralph needs to become a persistent interactive application.

## Proposed Solution

Replace the entire CLI experience with a Textual TUI app that owns ralph's full lifecycle. The app is a persistent session — you launch `ralph`, stay in it, and do everything from there:

1. **PRD Browser Screen** — scan `docs/prds/`, show a tree with frontmatter status, select a PRD and tasks file, configure run parameters (iterations, model, permission mode).

2. **Run Screen** — the main experience. Three-pane layout:
   - **Task progress panel** (left) — parsed from the tasks file on disk. Re-read after each iteration via a post-iteration hook. Shows `- [ ]` / `- [x]` checkboxes with the current task highlighted.
   - **Output pane** (center) — scrollable RichLog streaming the current iteration's output. Switchable to view past iterations.
   - **Iteration sidebar** (right or bottom) — list of completed iterations with duration, cost, status.

3. **Post-iteration hook** — after each `IterationResult` yields, re-read the tasks file and PRD from disk. The agent edits these during its iteration, so the TUI picks up changes at the natural boundary. No file watchers needed.

4. **Run controls** — pause/resume between iterations, stop early, adjust iterations remaining.

5. **Completion flow** — summary overlay with cost/time/tasks done. Options: "Run again" (same PRD), "Pick another PRD" (back to browser), or "Quit."

6. **History tab** — accessible anytime via keybinding. Lists past runs from `.ralph/runs/`, view iteration traces. Integrates with `run-history` PRD.

The underlying `core.py` and `run_ralph()` generator stay untouched — the TUI is a new consumer of the same async stream.

**Task format:** No strict schema enforced. The TUI parses `- [ ]` / `- [x]` checkboxes from whatever file `--tasks` points to. If it detects our `tasks.md` format (frontmatter + numbered sections), it extracts richer info (dependencies, descriptions). Works with any markdown task list.

## Key Cases

- Launch `ralph` with no args → PRD browser screen
- Launch `ralph 5 --prd X` → skip browser, go straight to run screen
- Live streaming output with auto-scroll (pause auto-scroll on manual scroll-up)
- Task panel updates after each iteration (disk re-read)
- Pause between iterations with `p` / Space — prevents next iteration from starting
- Stop early → summary → back to browser
- Switch between iteration outputs in the output pane
- View run history without leaving the app
- Footer shows contextual keybindings per screen
- Responsive layout, min ~80 cols
- `--no-tui` fallback for CI/piped usage (preserves current Rich output)

## Out of Scope

- Web-based UI (Textual web mode — future)
- Editing PRD/tasks content from within the TUI
- Multi-run management (multiple concurrent agents)
- File watching / inotify (we use post-iteration hooks instead)

## Open Questions

- Should pause also offer "skip this task" or "re-run this iteration"?
- How to surface agent errors mid-iteration (tool failures, API errors) in the TUI?

## References

- Current TUI: `ralph/cli.py` — `_build_status_table()` (line 22), `_run()` (line 171)
- Core loop: `ralph/core.py` — `run_ralph()` (line 148), `run_iteration()` (line 80)
- Textual: https://textual.textualize.io/
- Supersedes PRD: `interactive-file-browser` (folded in as the browser screen)
- Integrates with PRD: `run-history` (feeds the history tab)
