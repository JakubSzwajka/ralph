---
status: accepted
date: 2026-02-26
author: "kuba"
gh-issue: ~
---

# Preserve Cursor Position on Run Browser Refresh

## Problem

The run browser polls every 1 second and refreshes the DataTable by calling `table.clear()` then re-adding all rows. This resets the cursor to the first row. If you're browsing down through your run history, you get snapped back to the top every second, making it impossible to navigate.

## Proposed Solution

Before clearing and re-populating the table, save the currently highlighted row key (run_id). After re-adding rows, restore the cursor to the row with that same key. If the row no longer exists (run was deleted), fall back to the first row. Also skip the full clear+rebuild if the data hasn't changed (same run_ids in same order with same statuses) — only update rows that actually changed.

## Key Cases

- Browsing runs while an active run updates progress — cursor stays on the run you're viewing
- New run appears at top of list — cursor stays on current selection, doesn't jump
- Selected run disappears (edge case) — cursor falls back to first row
- No active runs — refresh is a no-op, no cursor flicker

## Out of Scope

- Pausing the refresh timer while browsing
- Partial row updates (just update changed cells) — full rebuild with cursor restore is sufficient

## References

- Refresh logic: `ralph/tui/screens.py` — `RunBrowserScreen._refresh_runs`
- Textual DataTable API: `cursor_coordinate`, `move_cursor`, row keys
