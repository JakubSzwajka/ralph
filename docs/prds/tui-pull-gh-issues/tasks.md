---
prd: tui-pull-gh-issues
generated: 2026-02-24
last-updated: 2026-02-24
---

# Tasks: Pull GitHub Issues into PRDs

> Summary: Add a keybinding to fetch open GitHub issues and import selected ones as local PRD directories.

## Task List

- [x] **1. Add `g` keybinding to BrowserScreen** — pressing `g` triggers the GitHub issue fetch flow
- [x] **2. Fetch open issues via `gh` CLI** — run `gh issue list --json number,title,body,url --limit 50` as subprocess
- [x] **3. Filter out already-linked issues** — match fetched issue URLs against `gh-issue` frontmatter of existing PRDs
- [x] **4. Implement issue selection modal** — interactive SelectionList with checkboxes showing title + issue number
- [x] **5. Implement slug derivation utility** — kebab-case from title, truncated to ~50 chars, no trailing hyphens, numeric suffix on collision
- [x] **6. Generate PRD README from selected issues** — create `docs/prds/<slug>/README.md` with frontmatter and mapped content
- [x] **7. Handle `gh` CLI unavailable** — show message and return to browser gracefully
- [x] **8. Handle no pullable issues** — show "No new issues to pull" message
- [x] **9. Refresh PrdTree after import** — tree updates to show newly created PRDs
- [x] **10. Add tests** — unit tests for slug derivation, integration tests for the full pull flow
