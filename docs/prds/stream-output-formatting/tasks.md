---
prd: stream-output-formatting
generated: 2026-02-26
last-updated: 2026-02-26
---

# Tasks: Stream Output Formatting

> Summary: Add a formatter that transforms raw tool-call slugs into concise labeled lines, suppress thinking/result blocks, and wire it into both TUI and headless output paths so `output.log` and display match.

## Task List

- [x] **1. Create `format_stream.py` with `format_block` function** — pure formatter for ToolUseBlock, ThinkingBlock, ToolResultBlock
- [x] **2. Wire formatter into `loop.py`** — replace raw slug construction with formatted output
- [x] **3. Add path-shortening helper** — make absolute paths relative to cwd `[blocked by: 1]`
- [x] **4. Verify headless + TUI parity** — both consumers get identical formatted strings `[blocked by: 2]`

---

### 1. Create `format_stream.py` with `format_block` function
<!-- status: done -->

Create `ralph/core/format_stream.py` with a `format_block(name: str, raw_input: dict | str, cwd: Path | None = None) -> str | None` function. Returns `None` for blocks that should be suppressed (ThinkingBlock, ToolResultBlock). For ToolUseBlock, returns a labeled one-liner based on tool name:

- `Bash` → `[Bash] description` (fallback: truncated command, ~120 chars)
- `Read` → `[Read] relative/path.py` (append `:offset-limit` if present)
- `Edit` / `Write` → `[Edit] relative/path.py` / `[Write] relative/path.py`
- `Task` → `[Task:subagent_type] description`
- `Grep` → `[Grep] "pattern" in path`
- `Glob` → `[Glob] pattern`
- `TodoWrite` → `[Todo] N items`
- Fallback → `[Name] first 100 chars of input`

The input may be a dict (from `block.input`) or a string (from `str(block.input)`). Handle both. When `raw_input` is a string that looks like a Python dict repr, parse it with `ast.literal_eval` as a fallback — but don't fail on parse errors, just use the fallback format.

**Files:** `ralph/core/format_stream.py` (new)
**Depends on:** —
**Validates:** Can import and call `format_block("Bash", {"command": "ls", "description": "List files"})` and get `[Bash] List files`

---

### 2. Wire formatter into `loop.py`
<!-- status: done -->

Replace the three slug-construction branches in `run_iteration()` (lines 71-82 of `ralph/core/loop.py`) with calls to `format_block`. Pass `config.cwd` through so paths can be shortened.

- `ThinkingBlock` (line 71-74): call `format_block("_thinking", block.signature)` → returns `None` → skip yield
- `ToolUseBlock` (line 75-78): call `format_block(block.name, block.input, cwd=...)` → yield if not None
- `ToolResultBlock` (line 79-82): call `format_block("_result", block.content)` → returns `None` → skip yield

For suppressed blocks (returns `None`): still append to `full_text` (needed for `COMPLETION_SIGNAL` check) but don't yield them. Use a sentinel like empty string or the raw slug for `full_text` so completion detection isn't broken.

**Files:** `ralph/core/loop.py`, `ralph/core/format_stream.py`
**Depends on:** 1
**Validates:** Run ralph on a real PRD. TUI output shows `[Bash]`, `[Read]`, etc. instead of raw dicts. No `ThinkingBlock` signatures or `ToolResultBlock` content visible. `COMPLETION_SIGNAL` detection still works.

---

### 3. Add path-shortening helper
<!-- status: done -->

In `format_stream.py`, add a `_shorten_path(path_str: str, cwd: Path | None) -> str` helper. If `cwd` is set, try `Path(path_str).relative_to(cwd)` and return the relative version. On failure (path is outside cwd), return the original. This keeps `[Read]` and `[Edit]` lines compact.

This could be done inside task 1, but splitting it out keeps the core formatter testable without filesystem concerns.

**Files:** `ralph/core/format_stream.py`
**Depends on:** 1
**Validates:** `_shorten_path("/Users/me/project/src/foo.py", Path("/Users/me/project"))` returns `"src/foo.py"`

---

### 4. Verify headless + TUI parity
<!-- status: done -->

Both `ralph/tui/screens.py` (line 512-515) and `ralph/cli/headless.py` (line 57-60) write the same `item` string to log file and display. Since the formatting now happens upstream in `loop.py`, both paths should automatically get formatted output. Verify this by running a headless run and comparing `output.log` content with what was printed to stdout. No code changes expected — this is a verification task.

If parity is broken (e.g., one path still shows raw slugs), fix the divergence.

**Files:** `ralph/tui/screens.py`, `ralph/cli/headless.py`
**Depends on:** 2
**Validates:** Run headless (`ralph run --headless`), then `cat .ralph/runs/<latest>/output.log`. Log content matches console output — both show `[Bash]`, `[Read]` labels, no raw dicts or thinking signatures.
