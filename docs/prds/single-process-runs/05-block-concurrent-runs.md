# Block starting a new run while one is active

## User Story

As a user, I want the app to prevent me from starting a second run while one is active, so that I don't accidentally create conflicting sessions.

## Acceptance Criteria

- [ ] `r` key binding is disabled (or shows a message) while a run is in progress
- [ ] After run completes/stops/errors, `r` is re-enabled
- [ ] Status bar indicates when a run is active

## Files

- `ralph/tui/app.py` — guard `action_start_run()`

## Notes

Small task. Just a boolean flag checked before starting.
