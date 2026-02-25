---
prd: run-history-and-status
generated: 2026-02-25
last-updated: 2026-02-25
---

# Tasks: Run History & Status in TUI

> Summary: Add context_files to run traces, build a run history reader, surface run status in the run bar, and add a history list/detail view to the TUI.

## Task List

- [x] **1. Store context_files in meta.json** — extend RunRecorder to persist context file paths
- [x] **2. Update meta.json incrementally per iteration** — write iteration progress so the UI can read live status
- [x] **3. Add run history reader module** — read and parse all `.ralph/runs/*/meta.json` into typed dataclasses
- [x] **4. Show live run progress in run bar** — update the bottom bar with iteration count while a run is active `[blocked by: 2]`
- [x] **5. Add run history list widget** — browsable list of past runs with status, timestamp, and duration `[blocked by: 3]`
- [x] **6. Add run detail view** — show per-iteration summary and metadata when selecting a run from history `[blocked by: 3, 5]`
- [x] **7. Wire history toggle keybinding** — add `h` key to switch between file browser and run history `[blocked by: 5]`

---

### 1. Store context_files in meta.json
<!-- status: done -->

Extend `write_meta_start` in `RunRecorder` to include the `context_files` list from `RalphConfig`. Serialize each path as a string relative to the project root. This connects runs back to the PRDs/files that triggered them and is needed for the history detail view.

**Files:** `ralph/traces/writer.py`, `ralph/traces/tests/test_writer.py`
**Depends on:** —
**Validates:** `meta.json` contains a `context_files` array with string paths after a run starts.

---

### 2. Update meta.json incrementally per iteration
<!-- status: done -->

Currently `meta.json` is only finalized in `write_meta_end`. Add a `write_meta_progress(iteration: int)` method to `RunRecorder` that updates `iterations_completed` and `status: "running"` after each iteration completes. This lets the TUI poll the file for live progress without needing in-process communication.

**Files:** `ralph/traces/writer.py`, `ralph/core/loop.py`, `ralph/traces/tests/test_writer.py`
**Depends on:** —
**Validates:** During a multi-iteration run, `meta.json` shows `"status": "running"` and `iterations_completed` incrementing after each iteration.

---

### 3. Add run history reader module
<!-- status: done -->

Create `ralph/traces/reader.py` with a `list_runs(root: Path) -> list[RunSummary]` function. `RunSummary` is a dataclass with fields from `meta.json`: `run_id`, `started_at`, `completed_at`, `status`, `iterations_requested`, `iterations_completed`, `total_duration_s`, `context_files`, `model`. Scan `.ralph/runs/*/meta.json`, parse each, return sorted by `started_at` descending. Handle missing or corrupt files gracefully.

**Files:** `ralph/traces/reader.py` (new), `ralph/traces/__init__.py`, `ralph/traces/tests/test_reader.py` (new)
**Depends on:** —
**Validates:** `list_runs()` returns parsed `RunSummary` objects for existing run directories, sorted newest first.

---

### 4. Show live run progress in run bar
<!-- status: done -->

During an active run, update the `#run-hint` Static in the run bar to show progress like `"Running: 2/10 iterations"`. In `_execute_run`, after each `IterationResult` is yielded, update the label. When the run finishes, revert to `"[bold]r[/bold] to run"`. This gives visibility even while browsing files since the run bar is always visible.

**Files:** `ralph/tui.py`
**Depends on:** 2
**Validates:** While a run executes, the bottom run bar shows the current iteration count updating in real-time.

---

### 5. Add run history list widget
<!-- status: done -->

Create a `RunHistoryList` widget (a Textual `ListView` or `DataTable`) that displays runs from `list_runs()`. Each row shows: status badge (colored), timestamp, iteration progress (e.g., "3/10"), duration, and truncated context file names. The widget emits a `RunSelected` message when a row is highlighted. Place it in the left `#collection-card` panel, initially hidden, toggled by the `h` keybinding.

**Files:** `ralph/tui.py`
**Depends on:** 3
**Validates:** Pressing `h` shows a list of past runs in the left panel; each row displays status, time, and iteration count.

---

### 6. Add run detail view
<!-- status: done -->

When a run is selected from the history list, show its details in the right `#detail-card` panel. Display: full timestamp, status, model, total duration, context files list, and a per-iteration table (iteration number, duration, status). Read iteration files (`iteration-NN.jsonl`) only to count events — don't render full event content. Reuse the existing detail card area by hiding file preview widgets.

**Files:** `ralph/tui.py`, `ralph/traces/reader.py`
**Depends on:** 3, 5
**Validates:** Selecting a run from history shows its metadata and per-iteration breakdown in the detail panel.

---

### 7. Wire history toggle keybinding
<!-- status: done -->

Add a `Binding("h", "toggle_history", "History", priority=True)` to `RalphApp`. When pressed, toggle between showing `DocTree` and `RunHistoryList` in the left panel. Update the panel border title to "Files" or "History" accordingly. Refresh the run list each time it's shown to pick up new runs. Show the keybinding hint in the Footer.

**Files:** `ralph/tui.py`
**Depends on:** 5
**Validates:** Pressing `h` toggles the left panel between file browser and run history; pressing `h` again returns to files.
