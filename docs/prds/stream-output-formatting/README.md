---
title: Stream Output Formatting
status: draft
date: 2026-02-26
author: kuba
gh-issue: ""
---

# Stream Output Formatting

## Problem

The streamed output from Claude is displayed raw in the TUI and saved raw to `output.log`. Tool calls appear as verbose Python dict dumps that are hard to scan:

```
Bash::{'command': 'grep -r "down_revision" alembic/versions/ | grep -oP ...', 'description': 'Find migration revision IDs'}
Read::{'file_path': '/Users/kuba.szwajka/DEV/sofomo/innocaption/snapcap/alembic/versions/3d3a69490da4_...py', 'limit': 20}
Edit::{'replace_all': False, 'file_path': '/Users/kuba.szwajka/DEV/sofomo/innocaption/snapcap/docs/prds/...', 'old_string': 'last-updated: ...', 'new_string': 'last-updated: ...'}
Task::{'description': 'Explore feature flags', 'prompt': 'Explore the codebase...', 'subagent_type': 'Explore'}
```

Two issues:

1. **TUI readability** — Tool call lines are noisy. The user doesn't need to see full file paths, raw dict syntax, or lengthy prompt strings inline. A labeled summary would be much easier to scan.

2. **Log/TUI parity** — `output.log` and the TUI should show the same content. Currently both get the same raw slugs, but the log should stay raw-ish (machine-parseable) while the TUI should format for humans. The simplification should happen in a formatter layer that both can share.

## Proposed Solution

Add a **stream formatter** module (`ralph/core/format_stream.py`) that transforms raw block slugs into concise labeled lines. Both TUI and log write the formatted version. The formatter is a pure function: `format_slug(block_type, raw_input) -> str`.

### Formatting rules

| Block type | Raw format | Formatted output |
|---|---|---|
| `Bash` | `Bash::{'command': '...', 'description': '...'}` | `[Bash] description` or `[Bash] command` (truncated to ~120 chars) |
| `Read` | `Read::{'file_path': '...', 'offset': N, 'limit': M}` | `[Read] relative/path.py` (with `:offset-limit` if present) |
| `Edit` | `Edit::{'file_path': '...', 'old_string': '...', 'new_string': '...'}` | `[Edit] relative/path.py` |
| `Write` | `Write::{'file_path': '...', ...}` | `[Write] relative/path.py` |
| `Task` | `Task::{'description': '...', 'subagent_type': '...', ...}` | `[Task:type] description` |
| `Grep` | `Grep::{'pattern': '...', 'path': '...'}` | `[Grep] "pattern" in path` |
| `Glob` | `Glob::{'pattern': '...', ...}` | `[Glob] pattern` |
| `TodoWrite` | `TodoWrite::{'todos': [...]}` | `[Todo] N items` |
| `ThinkingBlock` | `signature::thinking text...` | Omit entirely (or configurable) |
| `ToolResultBlock` | `tool_id::content` | Omit entirely (results are noise in the stream view) |
| Other/unknown | `Name::input` | `[Name] ...` (first 100 chars of input) |

File paths should be made relative to `cwd` when possible.

### Where it plugs in

```
loop.py: run_iteration()
    ↓ yields raw (block_type, raw_input) tuples
    ↓
format_stream.py: format_slug(name, input) → str
    ↓
screens.py / headless.py:
    log.write(formatted)      # TUI display
    log_file.write(formatted)  # output.log
```

The change is in `loop.py` — instead of yielding `f"{block.name}::{block.input!s}"`, yield the formatted version for ToolUseBlock, ThinkingBlock, and ToolResultBlock. TextBlock output stays unchanged.

### Log file

`output.log` gets the same formatted lines the TUI shows. This ensures 1:1 parity. The raw stream data is not preserved separately (it's ephemeral API data, not useful for replay).

## Key cases

- **Bash with description** — show description, not command
- **Bash without description** — show truncated command
- **Long file paths** — make relative to cwd, truncate if still long
- **Task blocks with long prompts** — show only description + subagent_type
- **ThinkingBlock** — omit from display (it's the base64-ish signature + internal reasoning)
- **ToolResultBlock** — omit from display (tool outputs are internal, user sees Claude's text summary)
- **TextBlock** — pass through unchanged (this is Claude's actual response text)
- **Unknown tool types** — generic `[ToolName] truncated_input`

## Out of scope

- Collapsible/expandable tool details in TUI (future enhancement)
- Raw stream replay/debug logging
- Filtering by block type in the TUI
- Colorized output (Rich markup) — can be added later on top of this
