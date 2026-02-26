---
status: accepted
date: 2026-02-26
author: "kuba"
gh-issue: ~
---

# Detached Agent Runs with Process Management

## Problem

Agent runs are currently tied to the TUI process. When you trigger a run via the app, the Claude SDK client lives inside a Textual worker — if you close the TUI, the agent dies. This makes it impossible to start a run, close the app, and come back later to check results. It also blocks the core use case: spinning up multiple concurrent agent runs and monitoring them all from the TUI.

There's no process orchestration layer. The old traces module was removed, so nothing writes run status to disk. The TUI can't browse running or past processes, and there's no way to stop a running agent.

## Proposed Solution

Introduce a **worker process model** where agent runs execute as independent OS processes, fully detached from the TUI. The TUI becomes a browser/launcher/manager that communicates with workers through the filesystem.

Each run gets a directory under `.ralph/runs/<id>/` containing a `meta.json` file. The **worker process** (a standalone Python entrypoint) writes this file on start (pid, config, status=running), updates it each iteration (progress, duration), and writes final status on exit (done/error/killed). The TUI polls these files (~1s interval) to show live status.

Launching a run: TUI spawns the worker via `subprocess.Popen` with `start_new_session=True` so it survives TUI exit. Killing a run: TUI reads the pid from `meta.json` and sends `SIGTERM`.

## Key Cases

- Launch a new agent run from TUI — spawns detached worker process, immediately visible in run list
- List all runs (active + past) with status, progress, duration, start time
- Monitor active run progress — TUI polls `meta.json`, shows "Iteration 3/10" updating live
- Kill a running agent from TUI — sends SIGTERM, worker catches it and writes final status
- Survive TUI restart — reopen TUI, all active/past runs still visible from their `meta.json` files
- Multiple concurrent runs — each is an independent process with its own status directory
- Worker writes structured status: pid, status (running/done/error/killed), iterations progress, duration, config used, context files

## Out of Scope

- Streaming agent output back into TUI in real-time (attach-to-run is a separate feature)
- Re-running a past run configuration
- Diffing between runs
- Remote/distributed execution — workers are local processes only
- Resource limits or scheduling (e.g., max concurrent runs)

## Open Questions

- What should the run ID format be? Timestamp-based (simple) vs UUID (unique but opaque)?
- Should the worker log full agent output to a file (e.g., `output.log`) alongside `meta.json`, or just the structured summary?
- How to handle orphaned processes (worker still running but `meta.json` says running, pid is stale)? Pid validation on TUI startup?
- Should `meta.json` schema be formalized (dataclass/pydantic model shared between worker and TUI)?

## References

- Current run execution: `ralph/tui/app.py` — `_execute_run` method (Textual worker, will be replaced)
- Agent loop: `ralph/core/loop.py` — `run_ralph` / `run_iteration` (reused by worker)
- Headless CLI: `ralph/cli/headless.py` — existing non-TUI execution path (related pattern)
- Removed traces module: commit `d06d30a` — previously wrote `meta.json`, was stripped in MVP cleanup
