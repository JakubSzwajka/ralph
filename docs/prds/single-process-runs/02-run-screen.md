# Add live Run Screen to TUI

## User Story

As a user, I want to see live streaming output when a run starts, so that I can monitor what Claude is doing in real-time.

## Acceptance Criteria

- [ ] New `RunScreen` Textual screen that displays live streaming text
- [ ] Shows iteration progress (`Iteration 2/20`), elapsed time, and status (`RUNNING`/`DONE`/`ERROR`/`KILLED`)
- [ ] `r` confirm flow pushes `RunScreen` instead of spawning subprocess
- [ ] `Esc`/`Backspace` returns to file browser when run is finished
- [ ] Run output is written to `output.log` as before (for history)
- [ ] `meta.json` is written/updated as before (for history)

## Files

- `ralph/tui/screens.py` — add `RunScreen`
- `ralph/tui/app.py` — wire up `RunScreen` instead of `_launch_worker()`

## Notes

This is the core UI piece. The run itself is wired in the next task. This task can scaffold the screen with placeholder content first.
