# Run Claude Code in-process instead of subprocess

## User Story

As a user, I want runs to execute in the same process as the TUI, so that the iteration loop works reliably and I don't get orphaned processes.

## Acceptance Criteria

- [ ] `RunScreen` starts an asyncio task that calls `run_ralph()` directly
- [ ] Text chunks from `run_ralph()` are streamed to the `RunScreen` live
- [ ] `meta.json` and `output.log` are updated as iterations complete
- [ ] `run_id` and `session_id` are generated in the TUI process
- [ ] No subprocess is spawned — `serialize_config()` and `Popen` calls removed from TUI

## Files

- `ralph/tui/app.py` — replace `_launch_worker()` with in-process async task
- `ralph/tui/screens.py` — `RunScreen` consumes `run_ralph()` output

## Notes

Depends on task 02 (RunScreen exists). The key change: `_launch_worker` becomes an async method that runs the loop directly.
