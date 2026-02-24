---
status: done
date: 2026-02-24
author: "kuba"
gh-issue: ~
---

# Preview PRD from BrowserScreen

## Problem

The TUI lets you browse PRDs and start runs, but there's no way to read the full PRD content before launching a run. You only see the task list, so you can't understand the problem and scope without opening the file externally.

## Proposed Solution

Add a keybinding (`p`) on a selected PRD in BrowserScreen that opens a scrollable modal showing the full README.md content. The modal renders markdown with Rich markup (headings, bullets, bold), displays frontmatter metadata as a header summary, and is dismissible with `Escape` or `q`.

## Key Cases

- Preview any PRD — render README.md content in a scrollable modal
- Frontmatter (status, date, author) shown as a header bar or summary line
- Works on PRDs with and without task files
- Modal is dismissible with `Escape` or `q`

## Out of Scope

- Editing PRD content from within the TUI
- Rendering tasks.md alongside the README
- Inline run launching from the preview modal

## Implementation

- `PrdPreviewScreen` ModalScreen implemented in `ralph/tui.py` (lines 448-540)
- `BrowserScreen` gained `("p", "preview_prd", "Preview")` binding and `action_preview_prd()` method
- CSS added to `RalphApp.CSS` for `PrdPreviewScreen #prd-preview-modal`, `#prd-preview-header`, `#prd-preview-content`
- 11 tests added to `tests/test_tui.py` (7 unit + 4 async integration); all 354 tests pass

## Files

- `ralph/tui.py` — BrowserScreen, PrdTree keybindings, PrdPreviewScreen
- `ralph/browser.py` — PrdInfo dataclass (read path)

## References

- TUI code: `ralph/tui.py` (BrowserScreen, PrdTree)
- PRD scanning: `ralph/browser.py` (scan_prds, PrdInfo)
