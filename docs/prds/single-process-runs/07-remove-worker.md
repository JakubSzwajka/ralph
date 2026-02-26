# Remove worker subprocess module

## User Story

As a maintainer, I want dead code removed, so that the codebase stays clean and there's no confusion about how runs are executed.

## Acceptance Criteria

- [ ] `ralph/worker.py` deleted
- [ ] `serialize_config()` removed (no longer needed)
- [ ] `cleanup_stale_runs()` simplified or removed (no more orphaned PIDs)
- [ ] No remaining references to `subprocess`, `Popen`, or `start_new_session`
- [ ] `__main__.py` or any entry point no longer supports `python -m ralph.worker`

## Files

- `ralph/worker.py` — delete
- `ralph/tui/app.py` — remove `_launch_worker()`, `serialize_config` import
- `ralph/core/run_meta.py` — simplify `cleanup_stale_runs()` if still needed

## Notes

Do this last after all other tasks are verified working. The worker is the old path — removing it is cleanup.
