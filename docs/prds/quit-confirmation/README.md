---
status: accepted
date: 2026-02-26
author: "kuba"
gh-issue: ~
---

# Quit Confirmation Modal

## Problem

Pressing `q` immediately exits the application with no confirmation. If you have active runs or accidentally hit `q`, you lose your TUI session instantly. There's no safety net.

## Proposed Solution

When `q` is pressed on the main screen, show a confirmation modal: "Are you sure you want to quit?" with Cancel/Quit buttons. Enter confirms quit, Escape cancels. Same pattern as the existing `ConfirmRunScreen`.

## Key Cases

- Press `q` on main view → confirmation modal appears
- Press Enter or click Quit → app exits
- Press Escape or click Cancel → modal dismissed, back to main view
- If active runs exist, modal should mention them: "You have X active run(s). Are you sure?"

## Out of Scope

- Stopping active runs on quit (they're detached, they survive)
- Auto-save or state persistence

## References

- Existing modal pattern: `ralph/tui/screens.py` — `ConfirmRunScreen`
- App quit: `ralph/tui/app.py` — `action_quit`
