---
prd: tui-delete-prd
generated: 2026-02-24
last-updated: 2026-02-24
---

# Tasks: Delete PRD from BrowserScreen

> Summary: Add a keybinding to delete PRDs from the TUI with confirmation dialog and optional GitHub issue closure.

## Task List

- [x] **1. Add `gh_issue` field to PrdInfo** — extend dataclass and scan_prds to read `gh-issue` frontmatter
- [x] **2. Add `refresh_prds()` to PrdTree** — method to clear and redraw the tree with a fresh PRD list
- [x] **3. Implement DeleteConfirmScreen** — ModalScreen showing title, status, in-progress warning; confirm with `y`/Enter, cancel with `n`/Escape
- [x] **4. Add `d` keybinding to BrowserScreen** — triggers delete confirmation flow
- [x] **5. Implement deletion logic** — remove directory with `shutil.rmtree`, close GH issue if linked
- [x] **6. Handle `gh` CLI unavailable** — deletion proceeds with warning toast if issue close fails
- [x] **7. Refresh PrdTree after deletion** — tree updates to reflect removed PRD
- [x] **8. Add CSS for DeleteConfirmScreen** — error-coloured border styling
