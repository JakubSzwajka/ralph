---
status: accepted
date: 2026-02-24
author: "kuba"
gh-issue: ~
---

# Pull GitHub Issues into PRDs

## Problem

If the team uses GitHub issues to capture ideas, there's no bridge to pull those into the local PRD format for Ralph to work on. Users must manually create PRD directories and files for each issue, which is tedious and error-prone.

## Proposed Solution

Add a keybinding (`g`) in BrowserScreen that fetches open issues via `gh issue list --json number,title,body,url --limit 50` and presents an interactive selection list with checkboxes. Issues already linked to existing PRDs (matched by `gh-issue` frontmatter URL) are filtered out. Each selected issue generates a `docs/prds/<slug>/README.md` with content mapped from the issue body, `status: draft`, and `gh-issue` set to the issue URL. The slug is auto-derived from the issue title (kebab-case, truncated to ~50 chars, no trailing hyphens). Slug collisions append a numeric suffix.

## Key Cases

- Pull open GH issues — interactive list with checkboxes, select which to import, generate PRD dirs with auto-derived slugs and `draft` status
- Pull skips issues already linked to existing PRDs (matched by `gh-issue` frontmatter URL)
- Pull with no GH CLI or no issues — graceful message, no crash
- Slug collisions append a numeric suffix (e.g. `my-feature-2`)
- Issue body mapped best-effort into Problem section; Proposed Solution left as placeholder if body is short

## Out of Scope

- Two-way sync (pushing PRD status changes back to GH issues)
- Pulling from sources other than GitHub issues
- Editing imported PRD content from within the TUI
- Showing issue labels/assignees in the selection list (nice-to-have for later)

## Open Questions

- How should issue title to slug handle collisions (e.g. existing dir with same slug)?
- Should the interactive issue list show issue labels/assignees for context?

## References

- TUI code: `ralph/tui.py` (BrowserScreen, PrdTree)
- PRD scanning: `ralph/browser.py` (scan_prds, PrdInfo)
- PRD template: `assets/templates/prd-readme.md`
