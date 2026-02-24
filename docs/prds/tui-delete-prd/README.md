---
status: done
date: 2026-02-24
author: "kuba"
gh-issue: ~
---

# Delete PRD from BrowserScreen

## Problem

Completed or abandoned PRDs pile up in the TUI browser with no way to clean them up. There's no deletion capability, so the PRD list becomes cluttered over time and harder to navigate.

## Proposed Solution

Add a keybinding (`d`) on a selected PRD in BrowserScreen that opens a confirmation dialog. The dialog shows the PRD title and status, warns if the PRD is in-progress, and on confirm removes the entire PRD directory from disk. If the PRD's `gh-issue` frontmatter links to a GitHub issue, that issue is closed via `gh issue close` (no comment posted). Cancellation via `Escape` or `n` aborts without deleting.

## Key Cases

- Delete a PRD with status `done` — confirm, remove dir, close GH issue if linked (no comment)
- Delete a PRD with status `in-progress` — confirmation warns that work may be lost
- If `gh` CLI is unavailable or the close fails, deletion still proceeds with a warning toast
- PrdTree refreshes after deletion to reflect the change
- Pressing `Escape` or `n` cancels without deleting

## Out of Scope

- Bulk delete operations
- Undo/trash (deletion is permanent with confirmation)
- Two-way sync (pushing PRD status changes back to GH issues beyond close-on-delete)

## Implementation

- `PrdInfo` dataclass gained `gh_issue: str | None = None` field in `ralph/browser.py`; `scan_prds()` populates it from `gh-issue` frontmatter (YAML `~` normalised to `None`)
- `PrdTree` gained `refresh_prds(prds)` method in `ralph/tui.py` — clears and redraws the tree with a fresh PRD list
- `DeleteConfirmScreen(ModalScreen[bool])` added to `ralph/tui.py` — shows title, colour-coded status, in-progress warning; `y`/Enter confirms, `n`/Escape cancels
- `BrowserScreen` gained `("d", "delete_prd", "Delete")` binding, `action_delete_prd()`, and `_on_delete_confirmed()` callback
- `_on_delete_confirmed()`: closes GH issue via `subprocess.Popen` (fire-and-forget, warns on `FileNotFoundError`), removes directory with `shutil.rmtree`, refreshes tree and resets UI state
- CSS added to `RalphApp.CSS` for `DeleteConfirmScreen` with error-coloured border
- 13 tests added to `tests/test_tui.py` (5 unit + 8 async integration); all 368 tests pass

## Files

- `ralph/tui.py` — BrowserScreen, PrdTree, new DeleteConfirmScreen
- `ralph/browser.py` — PrdInfo (add `gh_issue` field), scan_prds

## References

- TUI code: `ralph/tui.py` (BrowserScreen, PrdTree)
- PRD scanning: `ralph/browser.py` (scan_prds, PrdInfo)
