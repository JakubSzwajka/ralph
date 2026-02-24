---
prd: tui-preview-prd
generated: 2026-02-24
last-updated: 2026-02-24
---

# Tasks: Preview PRD from BrowserScreen

> Summary: Add a keybinding to preview the full PRD README content in a scrollable modal before starting a run.

## Task List

- [x] **1. Add `p` keybinding to BrowserScreen** — pressing `p` on a selected PRD triggers preview action
- [x] **2. Implement PrdPreviewScreen modal** — scrollable ModalScreen rendering README.md with Rich markup
- [x] **3. Render frontmatter as header** — show status, date, author as a summary line in the modal
- [x] **4. Handle dismiss with Escape/q** — modal closes on `Escape` or `q` keypress
- [x] **5. Support PRDs with and without task files** — preview works regardless of tasks.md presence
