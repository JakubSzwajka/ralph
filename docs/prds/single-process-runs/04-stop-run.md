# Stop a running session with Ctrl+C or k

## User Story

As a user, I want to stop a run mid-way, so that I can abort if something goes wrong without killing the whole app.

## Acceptance Criteria

- [ ] `k` or `Ctrl+C` on `RunScreen` cancels the asyncio task
- [ ] `ClaudeSDKClient` is disconnected cleanly on cancellation
- [ ] Run is marked `KILLED` in `meta.json`
- [ ] Log file is flushed and closed
- [ ] App returns to file browser after stop
- [ ] `r` key is re-enabled after stop

## Files

- `ralph/tui/screens.py` — `RunScreen` key bindings and cancellation logic
- `ralph/core/loop.py` — ensure `CancelledError` is handled in `run_iteration`

## Notes

Depends on task 03. The `finally` block in `run_iteration` already calls `client.disconnect()`, so cancellation should be clean.
