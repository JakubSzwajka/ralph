---
prd: detached-agent-runs
generated: 2026-02-26
last-updated: 2026-02-26
---

# Tasks: Detached Agent Runs with Process Management

> Summary: Decouple agent execution from the TUI by introducing a worker process model with file-based status tracking, enabling concurrent runs that survive TUI restarts, with full lifecycle management (launch, monitor, kill).

## Task List

- [x] **1. RunMeta model and helpers** — shared dataclass for meta.json read/write/update
- [x] **2. Worker entrypoint** — standalone script that runs the agent loop as a detached process
- [x] **3. Launch worker from TUI** — spawn detached worker via Popen, replace current in-process execution
- [x] **4. Run browser screen** — new TUI screen listing all runs with live status polling
- [x] **5. Run detail view** — show full run info when selecting a run in the browser
- [x] **6. Kill a run from TUI** — send SIGTERM to worker, update status, handle orphans `[blocked by: 3, 4]`
- [x] **7. Launch worker from CLI headless** — wire up headless mode to also use detached workers `[blocked by: 2]`

---

### 1. RunMeta model and helpers
<!-- status: done -->

Create a `ralph/core/run_meta.py` module with a `RunMeta` dataclass mirroring the existing `.ralph/runs/*/meta.json` structure: `run_id`, `pid`, `started_at`, `completed_at`, `status` (running/done/error/killed), `iterations_requested`, `iterations_completed`, `total_duration_s`, `context_files`, `model`, `permission_mode`. Add helpers: `write(path)`, `read(path) -> RunMeta`, `update(path, **fields)`, and `list_runs(runs_dir) -> list[RunMeta]` sorted by most recent. Status should be an enum. The `pid` field is new — needed for process management.

**Files:** `ralph/core/run_meta.py` (new), `ralph/core/__init__.py`
**Depends on:** —
**Validates:** Can create, write, read back, and list RunMeta objects. Round-trip to JSON preserves all fields.

---

### 2. Worker entrypoint
<!-- status: pending -->

Create `ralph/worker.py` — a module runnable via `python -m ralph.worker` that accepts a config (JSON on stdin or a config file path) and executes the agent loop. On start: generate run_id, create `.ralph/runs/<id>/meta.json` with pid and status=running. Each iteration: update meta.json with progress. On completion: write final status. Handle SIGTERM gracefully — catch the signal, set status=killed, disconnect the SDK client, and exit cleanly. Use `run_ralph()` from `ralph/core/loop.py` as the execution engine.

**Files:** `ralph/worker.py` (new)
**Depends on:** 1
**Validates:** `python -m ralph.worker` with a config runs the agent, writes meta.json, updates it per iteration, and exits with final status. Sending SIGTERM writes status=killed.

---

### 3. Launch worker from TUI
<!-- status: pending -->

Replace `_execute_run` in `ralph/tui/app.py` to spawn the worker as a detached process using `subprocess.Popen` with `start_new_session=True`. Pass config as JSON via a temp file or stdin. After spawning, the TUI should show a notification and update the run bar. Remove the `@work` decorator and the in-process `run_ralph()` call — the TUI no longer executes agent code directly.

**Files:** `ralph/tui/app.py`
**Depends on:** 2
**Validates:** Pressing `r` in TUI spawns a worker process. Closing and reopening the TUI shows the run still active in `.ralph/runs/`.

---

### 4. Run browser screen
<!-- status: pending -->

Add a new TUI screen or panel that lists all runs from `.ralph/runs/`. Each row shows: run_id (timestamp), status badge (color-coded), iteration progress (e.g., "3/10"), duration, and number of context files. Poll the runs directory every ~1s using a Textual `Timer` to refresh active run statuses. Add a keybinding (e.g., `h` for history) to toggle the run browser. Use `list_runs()` from task 1.

**Files:** `ralph/tui/screens.py` (or new `ralph/tui/run_browser.py`), `ralph/tui/app.py`
**Depends on:** 1
**Validates:** Pressing `h` shows all past and active runs. Active runs update their progress in real-time (~1s).

---

### 5. Run detail view
<!-- status: pending -->

When a run is selected in the browser (task 4), show its full details: all meta.json fields formatted nicely, list of context files, per-iteration timing if available. If the worker writes output to a log file alongside meta.json, show the tail of it. This can be a panel within the existing detail card area or a pushed screen.

**Files:** `ralph/tui/screens.py`, `ralph/tui/app.py`
**Depends on:** 4
**Validates:** Selecting a run in the browser shows its full configuration and status details.

---

### 6. Kill a run from TUI
<!-- status: pending -->

Add a keybinding (e.g., `k` or `ctrl+c` scoped to selection) in the run browser that kills the selected active run. Read pid from meta.json, send `os.kill(pid, signal.SIGTERM)`. Validate the pid is still alive first (`os.kill(pid, 0)`). On TUI startup, scan for runs with status=running and check if their pid is still alive — if not, update status to "error" (orphan cleanup).

**Files:** `ralph/tui/app.py` (or run browser module from task 4), `ralph/core/run_meta.py`
**Depends on:** 3, 4
**Validates:** Killing a run from the browser sends SIGTERM, worker exits, meta.json shows status=killed. Orphaned runs detected on TUI startup.

---

### 7. Launch worker from CLI headless
<!-- status: pending -->

Update `ralph/cli/headless.py` to also use the detached worker model instead of running the loop in-process. In headless mode, spawn the worker, then poll meta.json to display progress (similar to current Rich Live display). This unifies both execution paths through the same worker process.

**Files:** `ralph/cli/headless.py`, `ralph/cli/app.py`
**Depends on:** 2
**Validates:** `ralph --no-tui` spawns a detached worker and shows progress by polling meta.json. The run survives if the CLI process is killed.
