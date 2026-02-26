# Change default iterations to 20

## User Story

As a user, I want the default iteration count to be 20, so that Ralph can work through more tasks without me specifying `--iterations` every time.

## Acceptance Criteria

- [ ] `RalphConfig.iterations` defaults to `20`
- [ ] CLI `--iterations` help text reflects new default
- [ ] `config.json` can override via `iterations` key
- [ ] Worker deserialization uses `20` as fallback

## Files

- `ralph/core/config.py`
- `ralph/cli/args.py`
- `ralph/worker.py`

## Notes

Small standalone change. Do this first since it's independent of the architectural work.
