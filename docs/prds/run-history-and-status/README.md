---
status: done
date: 2026-02-25
author: "kuba"
gh-issue: ~
---

# Run History & Status in TUI

## Problem

When a run is triggered from the TUI, there's no visibility into it. If you navigate to a file preview, the run output disappears and there's no way to know it's still running. Past runs are recorded in `.ralph/runs/` as trace files but there's no way to browse them from the TUI. You have to manually inspect JSONL files on disk to understand what happened.

## Proposed Solution

Add a **Run History panel** to the TUI that lists all runs (past and active) by reading `.ralph/runs/*/meta.json`. Each entry shows a summary row: timestamp, status (running/complete/error/max-iterations), iteration progress, duration, and which context files were used. Selecting a run shows its details — iteration summaries, duration per iteration, and final status. An active run shows a live-updating status indicator (spinner or progress bar) in the list and in the run bar at the bottom.

The traces module already writes `meta.json` with `started_at`, `completed_at`, `status`, `iterations_requested`, `iterations_completed`, and `total_duration_s`. The TUI reads these to populate the history. For active runs, the meta file is updated incrementally so the UI can poll or watch it.

## Key Cases

- View list of all past runs sorted by most recent, each showing status badge, timestamp, iteration count, and duration
- See which run is currently active with a live status indicator (e.g., "Iteration 3/10" updating in real-time)
- Select a past run to see its detail: per-iteration summary (duration, complete/partial), context files used, model, final status
- Run bar at the bottom shows live progress of the active run even while browsing files (e.g., "Running: 3/10 iterations")
- Link runs to context files — `meta.json` already stores `prd` path, extend it to store `context_files` list so you can see which PRDs a run was for

## Out of Scope

- Switching back to the live streaming output of an active run (separate feature — "attach to run")
- Deleting or managing run trace files from the TUI
- Replaying or re-running a past run configuration
- Diffing between runs

## Open Questions

- Should the history be a separate screen (pushed on top) or a panel/tab within the existing layout?
- How much detail to show inline vs. in a detail view — do we need to render iteration JSONL events or is the meta summary enough?
- Should `meta.json` be extended to include `context_files` now, or is that a separate change to the traces module?

## References

- Traces module: `ralph/traces/writer.py` — `RunRecorder` writes `meta.json` and iteration JSONL
- Run data lives in `.ralph/runs/<timestamp>/meta.json`
- TUI run execution: `ralph/tui.py` — `_execute_run` method
