---
prd: run-history
generated: 2026-02-24
last-updated: 2026-02-24
---
<!-- progress: all 7 tasks complete (ralph/recorder.py with event schema + RunRecorder + IterationWriter + write_meta_start/write_meta_end + _ensure_gitignore auto-adds .ralph/runs/ to .gitignore; ralph/core.py hooked with optional recorder param writing events to JSONL and calling meta methods; tests in tests/test_recorder.py; ralph/cli.py with _cmd_runs() listing past runs as a Rich table, main() dispatches 'runs' subcommand; _show_run_detail() prints config panel + iterations table, _print_iteration_text() prints full text output for --iteration N flag; tests in tests/test_cli_runs.py) -->

# Tasks: Run History

> Summary: Persist full agent traces to `.ralph/runs/` as JSONL files and add a CLI command to list/review past runs.

## Task List

- [x] **1. Create run recorder module** — `ralph/recorder.py` with RunRecorder class that manages a run directory
- [x] **2. Define JSONL event schema** — dataclasses for each event type serializable to JSON
- [x] **3. Hook recorder into the iteration stream** — write events during `run_iteration` without changing its interface
- [x] **4. Write meta.json at run start and end** — config snapshot on start, totals on completion
- [x] **5. Add `ralph runs` CLI subcommand** — list past runs from `.ralph/runs/`
- [x] **6. Add `ralph runs <id>` detail view** — print iteration summaries for a specific run
- [x] **7. Auto-add `.ralph/runs/` to .gitignore** — ensure run history isn't committed

---

### 1. Create run recorder module
<!-- status: done -->

Create `ralph/recorder.py` with a `RunRecorder` class. Constructor takes the project root, creates `.ralph/runs/<timestamp>/` directory (timestamp format: `YYYY-MM-DDTHH-MM-SS`). Provide `open_iteration(n: int)` returning a context manager that gives an `IterationWriter` with a `write_event(event)` method. The writer appends JSON lines to `iteration-{n:02d}.jsonl`. Keep file handles open during iteration, flush after each event.

**Files:** `ralph/recorder.py`
**Depends on:** 2
**Validates:** `RunRecorder(root).open_iteration(1)` creates the directory and JSONL file

---

### 2. Define JSONL event schema
<!-- status: done -->

Define event dataclasses in `ralph/recorder.py`: `TextEvent`, `ThinkingEvent`, `ToolUseEvent`, `ToolResultEvent`, `UserMessageEvent`. Each has a `type` discriminator field, `timestamp` (ISO), and the relevant payload. Add a `to_json_line() -> str` method that serializes to a single JSON line using `dataclasses.asdict` + `json.dumps`. Keep it simple — no custom encoders, just strings and primitives.

**Files:** `ralph/recorder.py`
**Depends on:** —
**Validates:** `TextEvent(text="hello").to_json_line()` returns valid JSON with `"type": "text"`

---

### 3. Hook recorder into the iteration stream
<!-- status: done -->

Modify `run_iteration()` in `core.py` to accept an optional `recorder: RunRecorder | None` parameter. Inside the match arms (lines 102-135), after yielding each chunk, also call `writer.write_event(...)` with the appropriate event type. The recorder is optional so existing behavior is unchanged when not provided. Update `run_ralph()` to create a `RunRecorder` and pass it through.

**Files:** `ralph/core.py`
**Depends on:** 1, 2
**Validates:** After a run, `.ralph/runs/<ts>/iteration-01.jsonl` exists with event lines

---

### 4. Write meta.json at run start and end
<!-- status: done -->

Add `write_meta_start(config: RalphConfig)` and `write_meta_end(results: list[IterationResult])` methods to `RunRecorder`. Start writes: timestamp, prd path, tasks path, iterations requested, model, permission mode. End writes: total cost, total duration, iteration count completed, completion status (complete/max-iterations/error). Use `json.dump` with indent=2 for readability.

**Files:** `ralph/recorder.py`, `ralph/core.py`
**Depends on:** 1
**Validates:** `meta.json` has both `started_at` and `completed_at` fields after a run

---

### 5. Add `ralph runs` CLI subcommand
<!-- status: done -->

Add subcommand support to `cli.py`. `ralph runs` scans `.ralph/runs/`, reads each `meta.json`, and prints a Rich table: run ID (timestamp), PRD name, iterations completed, total cost, duration, status. Sort by most recent first. If no runs found, print a message. Keep the existing `ralph <iterations>` as the default command.

**Files:** `ralph/cli.py`
**Depends on:** 4
**Validates:** `ralph runs` prints a table of past runs

---

### 6. Add `ralph runs <id>` detail view
<!-- status: done -->

When `ralph runs <timestamp>` is called, read that run's `meta.json` and all `iteration-*.jsonl` files. Print a Rich panel with config info, then a table of iterations (number, duration, cost, event count, key tool calls). Optionally print the full text output of a specific iteration with `ralph runs <id> --iteration 3`.

**Files:** `ralph/cli.py`
**Depends on:** 5
**Validates:** `ralph runs 2026-02-24T10-35-00` shows iteration breakdown

---

### 7. Auto-add `.ralph/runs/` to .gitignore
<!-- status: done -->

In `RunRecorder.__init__`, after creating the runs directory, check if `.gitignore` exists in the project root. If it does and doesn't contain `.ralph/runs/`, append it. If `.gitignore` doesn't exist, create it with just that entry. This is a one-time operation — skip if the pattern is already present.

**Files:** `ralph/recorder.py`
**Depends on:** 1
**Validates:** After first run, `.gitignore` contains `.ralph/runs/`

---
