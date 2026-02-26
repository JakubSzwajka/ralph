---
status: accepted
date: 2026-02-26
author: "kuba"
gh-issue: ""
---

# Single-Process Runs — Remove Worker Subprocess

## Problem

Ralph spawns Claude Code sessions as detached worker subprocesses. This causes two issues:

1. **Stuck iterations**: The `receive_messages()` async iterator from `claude_agent_sdk` never closes when the agent finishes a turn (with `max_turns=None`), so the outer iteration loop hangs after the first task completes and never advances to iteration 2.

2. **Orphaned processes**: Workers run in detached subprocesses (`start_new_session=True`). Users can spawn multiple workers and lose track of them. The `cleanup_stale_runs` mechanism is a workaround, not a solution.

The subprocess architecture adds complexity (config serialization, file-based IPC, PID monitoring) without clear benefit since only one run at a time is the intended workflow.

## Proposed Solution

Remove the worker subprocess. Run Claude Code directly in the main application process via an asyncio task. The TUI switches to a live Run Screen when a run starts, streaming output in real-time. Only one run is active at a time per app instance. To run multiple concurrent sessions, the user opens multiple terminal instances.

The iteration loop calls `claude_agent_sdk` directly — each iteration creates a fresh `ClaudeSDKClient`, sends the prompt, streams responses, disconnects, then loops. The `receive_messages()` hang is resolved by running in-process where we control the lifecycle.

## Key Cases

- **Start a run**: User selects files → presses `r` → confirms → app switches to Run Screen showing live streaming output, iteration progress, elapsed time
- **Run completes naturally**: All iterations done or `COMPLETION_SIGNAL` detected → status shows `DONE` → user presses `Esc`/`Backspace` to return to file browser
- **Stop a run mid-way**: User presses `Ctrl+C` or `k` → asyncio task is cancelled, client disconnected → run marked `KILLED` → app returns to file browser
- **Run errors**: Exception during run → logged, run marked `ERROR` → user sees error and can return to file browser
- **Start blocked while running**: `r` key is disabled while a run is active
- **History browsing**: `h` still opens RunBrowserScreen, reads `meta.json`/`output.log` from `.ralph/runs/` — works for current and past sessions
- **Headless mode**: `--no-tui` path also runs in-process (no subprocess), streaming to stdout
- **Default iterations**: 20 (was 10)

## Out of Scope

- Multiple concurrent runs in one app instance
- Background/detached runs that survive app exit
- Reworking the prompt strategy or completion signal logic
- Changes to the RunBrowserScreen history UI (beyond removing stale-run cleanup that's no longer needed)

## Open Questions

- Should we keep `worker.py` around for any backwards compatibility or delete it entirely?
- Should the Run Screen show raw streaming output or parsed/formatted output (tool calls, thinking blocks, text separately)?

## References

- `ralph/worker.py` — current subprocess worker (to be removed)
- `ralph/core/loop.py` — iteration loop with `receive_messages()` hang
- `ralph/tui/app.py` — TUI entry point, `_launch_worker()` to be replaced
- `ralph/tui/screens.py` — `RunBrowserScreen` for history
