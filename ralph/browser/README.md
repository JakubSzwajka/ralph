# ralph/browser

Document discovery and filesystem scanning for the TUI file browser.

## Public API

- `DocDir` — directory node with `name`, `path`, `children`
- `DocFile` — file node with `path`, `relative_path`
- `scan_docs(root, docs_dir?)` — build a `DocDir` tree from a docs directory
- `scan_docs_flat(root, docs_dir?)` — flatten the tree into a list of `DocFile`
- `parse_frontmatter(text)` — extract YAML frontmatter from markdown

## Responsibility Boundary

Owns filesystem scanning and frontmatter parsing. Does not render UI — the TUI consumes `DocDir`/`DocFile` directly.

## Read Next

- [Core](../core/README.md)
- [TUI](../tui/README.md)
