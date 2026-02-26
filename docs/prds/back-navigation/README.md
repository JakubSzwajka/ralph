---
status: accepted
date: 2026-02-26
author: "kuba"
gh-issue: ~
---

# Back Navigation from Run Browser

## Problem

When you press `h` to open the run browser, the only way out is `q` which quits the entire application. There's no way to go back to the main file browser view to select files and start another run.

## Proposed Solution

Make `q` and `escape` in the RunBrowserScreen pop the screen (go back) instead of quitting the app. This is actually already the intent — `action_go_back` calls `self.app.pop_screen()` — but the app-level `q` binding (quit) takes priority over the screen-level one. Fix the binding priority so the screen's `q` wins when the run browser is active.

## Key Cases

- Press `h` to open run browser, press `q` or `escape` to return to main view
- From main view, press `q` to quit (existing behavior, now with confirmation — see quit-confirmation PRD)
- Navigation cycle: main → run browser → main → run browser works repeatedly

## Out of Scope

- Breadcrumb or navigation history
- Other screens beyond run browser

## References

- Run browser: `ralph/tui/screens.py` — `RunBrowserScreen.action_go_back`
- App bindings: `ralph/tui/app.py` — `BINDINGS` list
