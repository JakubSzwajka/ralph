---
prd: tui-control-panel
generated: 2026-02-24
last-updated: 2026-02-24 (task 14 done)
---

# Tasks: TUI Control Panel

> Summary: Replace ralph's CLI with a persistent Textual app — PRD browser, interactive run screen with task tracking, iteration controls, and run history.

## Task List

- [x] **1. Scaffold Textual app and screen routing** — RalphApp with screen stack (browser → run → summary)
- [x] **2. Build markdown task parser** — parse `- [ ]`/`- [x]` from any markdown, with richer extraction for tasks.md format
- [x] **3. Build PRD scanner widget** — tree view of `docs/prds/` with status badges, keyboard nav
- [x] **4. Build PRD browser screen** — PRD selection + tasks preview + run config (iterations, model) `[blocked by: 2, 3]`
- [x] **5. Build task progress panel widget** — left sidebar showing parsed tasks with live status `[blocked by: 2]`
- [x] **6. Build output pane widget** — scrollable RichLog with auto-scroll toggle and iteration switching
- [x] **7. Build iteration sidebar widget** — list of completed iterations with duration/cost/status
- [x] **8. Build run screen** — compose task panel + output pane + iteration sidebar into main layout `[blocked by: 5, 6, 7]`
- [x] **9. Wire run_ralph() as a Textual Worker** — async generator → custom messages → widget updates `[blocked by: 8]`
- [x] **10. Add post-iteration hook** — re-read tasks file and PRD from disk after each IterationResult `[blocked by: 5, 9]`
- [x] **11. Add run controls** — pause/resume, stop early, keybindings + footer `[blocked by: 9]`
- [x] **12. Build completion flow** — summary overlay with "run again" / "pick another" / "quit" `[blocked by: 9]`
- [x] **13. Add history tab** — list past runs from `.ralph/runs/`, view iteration traces `[blocked by: 1]`
- [x] **14. Replace cli.py entry point** — swap `_run()` for `RalphApp.run()`, add `--no-tui` fallback `[blocked by: 9, 12]`

---

### 1. Scaffold Textual app and screen routing
<!-- status: done -->

Create `ralph/tui.py` with `RalphApp(App)`. Define three screens: `BrowserScreen`, `RunScreen`, `SummaryScreen`. The app accepts `RalphConfig | None` — if config has a PRD, push `RunScreen` directly; otherwise start on `BrowserScreen`. Set up the CSS layout skeleton (inline TCSS): browser is single-pane, run screen is a 3-column grid. Add `Header` and `Footer` from Textual builtins.

**Files:** `ralph/tui.py`
**Depends on:** —
**Validates:** `RalphApp().run()` launches, shows empty BrowserScreen with header/footer

---

### 2. Build markdown task parser
<!-- status: done -->

Create `ralph/tasks.py` with `parse_tasks(path: Path) -> list[TaskItem]`. `TaskItem` is a dataclass: `title: str`, `done: bool`, `index: int`, and optional `description`, `files`, `depends_on` fields. The parser first tries the structured `tasks.md` format (frontmatter + `### N. Title` sections). Falls back to scanning for any `- [ ]` / `- [x]` lines. Returns an empty list if the file doesn't exist or has no checkboxes.

**Files:** `ralph/tasks.py`
**Depends on:** —
**Validates:** Parsing both `tasks.md` format and plain checkbox markdown returns correct `TaskItem` lists

---

### 3. Build PRD scanner widget
<!-- status: done -->

Create a `PrdTree(Tree)` widget in `ralph/tui.py`. Given a root path, scan `*/README.md`, extract frontmatter `status` and title. Render as a tree: each node shows `slug — [status]` with color coding (green=accepted/in-progress, yellow=draft, dim=done). Emit a `PrdSelected(path, slug)` message on Enter. Support arrow/vim keys for navigation.

**Files:** `ralph/tui.py`
**Depends on:** —
**Validates:** Widget renders PRDs from disk; Enter on a node emits the correct path

---

### 4. Build PRD browser screen
<!-- status: done -->

`BrowserScreen(Screen)` composes: `PrdTree` on the left, a preview panel on the right (shows selected PRD's task list parsed via `parse_tasks`), and a config bar at the bottom (iteration count input, model selector, start button). On "Start": build a `RalphConfig` from selections, push `RunScreen`. If no PRDs found, show a message with manual path input.

**Files:** `ralph/tui.py`
**Depends on:** 2, 3
**Validates:** Selecting a PRD shows its tasks in preview; clicking Start pushes RunScreen with correct config

---

### 5. Build task progress panel widget
<!-- status: done -->

Create `TaskPanel(Widget)` that takes a `list[TaskItem]` and renders them as a styled list: `[x]` in green, `[ ]` in dim, current task (first unchecked) highlighted with a marker. Expose a `refresh_tasks(path: Path)` method that re-parses the file and updates the display. This is what the post-iteration hook calls.

**Files:** `ralph/tui.py`
**Depends on:** 2
**Validates:** `refresh_tasks()` updates checkbox states after agent edits the file

---

### 6. Build output pane widget
<!-- status: done -->

Create `OutputPane(RichLog)` for the center of the run screen. `write_chunk(text)` appends and auto-scrolls. Scrolling up manually pauses auto-scroll (detect via `on_scroll` or scroll position check). Expose `show_iteration(chunks: list[str])` to swap content when viewing a past iteration, and `resume_live()` to switch back to the current stream.

**Files:** `ralph/tui.py`
**Depends on:** —
**Validates:** Writing chunks scrolls; scrolling up pauses; `show_iteration()` replaces content

---

### 7. Build iteration sidebar widget
<!-- status: done -->

Create `IterationList(ListView)` for the right side of the run screen. Each item shows: iteration number, duration, cost, status badge. `add_result(IterationResult)` appends a new item. Clicking/selecting an item emits `IterationSelected(n)` which the run screen routes to the output pane. Highlight the active/viewed iteration.

**Files:** `ralph/tui.py`
**Depends on:** —
**Validates:** Adding results populates the list; selecting an item emits the correct iteration number

---

### 8. Build run screen
<!-- status: done -->

`RunScreen(Screen)` composes: `TaskPanel` (left, ~25 cols), `OutputPane` (center, flex), `IterationList` (right, ~20 cols). Wire `IterationSelected` to swap the output pane. Store iteration output in a `dict[int, list[str]]`. CSS layout: horizontal grid with fixed side columns and fluid center.

**Files:** `ralph/tui.py`
**Depends on:** 5, 6, 7
**Validates:** Screen renders 3-pane layout; iteration switching works between panes

---

### 9. Wire run_ralph() as a Textual Worker
<!-- status: done -->

In `RunScreen`, use `self.run_worker()` to run `run_ralph(config)` as an async worker. Define custom messages: `IterationStarted(n)`, `OutputChunk(text)`, `IterationCompleted(result)`, `RunFinished(results)`. The worker posts these via `self.post_message()`. Message handlers on `RunScreen` route to the output pane, iteration list, and trigger the post-iteration hook. Pass Discord notifier through — fire notifications in the `IterationCompleted` handler.

**Files:** `ralph/tui.py`
**Depends on:** 8
**Validates:** Starting a run streams output to the pane and populates the iteration list

---

### 10. Add post-iteration hook
<!-- status: done -->

In the `IterationCompleted` message handler on `RunScreen`, call `task_panel.refresh_tasks(config.tasks)` to re-read the tasks file from disk. Also re-read PRD frontmatter — if status changed to `done`, surface it in the header. This is the core "disk re-read at iteration boundary" pattern. No file watchers.

**Files:** `ralph/tui.py`
**Depends on:** 5, 9
**Validates:** After an iteration where the agent checks off a task, the panel updates without restart

---

### 11. Add run controls
<!-- status: done -->

Add keybindings to `RunScreen`: `p`/Space to toggle pause (set a flag the worker checks between iterations — `await self.pause_event.wait()`), `s` to stop early (cancel the worker, push summary). Add `Footer` bindings that update contextually: show "Resume" when paused, "Pause" when running. `q` quits the app from any screen.

**Files:** `ralph/tui.py`
**Depends on:** 9
**Validates:** Pressing `p` pauses after current iteration; pressing again resumes

---

### 12. Build completion flow
<!-- status: done -->

`SummaryScreen(Screen)` shows: total iterations, cost, time, completion status, and the final task progress snapshot. Three action buttons/keys: `r` = run again (same config, pop to RunScreen), `b` = back to browser (pop to BrowserScreen), `q` = quit. Push this screen when `RunFinished` is received or when user stops early.

**Files:** `ralph/tui.py`
**Depends on:** 9
**Validates:** Run completing shows summary; "run again" starts fresh iterations; "back" returns to browser

---

### 13. Add history tab
<!-- status: done -->

Add a `HistoryScreen(Screen)` accessible via `h` keybinding from any screen. Scan `.ralph/runs/`, read `meta.json` from each, show a DataTable: timestamp, PRD, iterations, cost, status. Selecting a run shows its iteration breakdown. Pressing Escape returns to the previous screen. This consumes data from the `run-history` PRD's recorder.

**Files:** `ralph/tui.py`
**Depends on:** 1
**Validates:** `h` opens history; past runs are listed; selecting one shows iteration detail

---

### 14. Replace cli.py entry point
<!-- status: done -->

In `cli.py:main()`, replace `asyncio.run(_run(config))` with `RalphApp(config).run()`. Move the old `_run()` and `_build_status_table()` to a `_run_headless()` function. Add `--no-tui` flag to argparse; auto-enable when stdout is not a TTY. Remove unused Rich imports from the main path. Keep `parse_args()` and `ralph runs` subcommand as-is.

**Files:** `ralph/cli.py`
**Depends on:** 9, 12
**Validates:** `ralph 5 --prd X` launches Textual app; `ralph 5 --prd X --no-tui` uses old Rich output; piping auto-falls back

---
