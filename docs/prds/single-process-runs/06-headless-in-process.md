# Run headless mode in-process

## User Story

As a user running Ralph without a TUI (piped output, CI), I want runs to execute in-process, consistent with the TUI path.

## Acceptance Criteria

- [ ] `_run_headless()` calls `run_ralph()` directly (no subprocess)
- [ ] Output streams to stdout as before
- [ ] `meta.json` and `output.log` are still written
- [ ] `Ctrl+C` cleanly stops the run
- [ ] Discord notifications still fire after each iteration

## Files

- `ralph/cli/app.py` — `_run_headless()`

## Notes

Check if headless already calls `run_ralph()` directly or goes through the worker. If it already does, this may just need minor cleanup.
