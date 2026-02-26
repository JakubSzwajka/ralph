# ralph/cli

CLI entry point and headless runner. Parses arguments, resolves config, and dispatches to TUI or headless mode.

## Public API

- `main(argv?)` — entry point: parses args, runs TUI or headless depending on flags/TTY
- `parse_args(argv?)` — returns `(RalphConfig, prd_explicit, prd_dir, no_tui)`
- `_run_headless(config)` — runs the agent loop in-process, streaming to stdout with meta/log persistence

## Responsibility Boundary

Owns argument parsing, config resolution (CLI > config file > defaults), and headless execution. Delegates TUI mode to `ralph.tui` and the agent loop to `ralph.core`.

## PRD Argument Behavior

- `--prd` accepts one or more file paths.
- `--prd` also accepts wildcard patterns (for example `"docs/prds/*/PRD.md"`).
- When `--prd` resolves to multiple files, they are passed as context files to the agent run.

## Read Next

- [Core](../core/README.md)
- [TUI](../tui/README.md)
