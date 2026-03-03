# ralph/cli

CLI entry point and runner. Parses arguments, resolves config, and runs the agent loop.

## Public API

- `main(argv?)` — entry point: parses args, validates inputs, and runs the agent loop
- `parse_args(argv?)` — returns `(RalphConfig, prd_explicit)`
- `_run_cli(config)` — runs the agent loop in-process, streaming to stdout with meta/log persistence

## Responsibility Boundary

Owns argument parsing, config resolution (CLI > config file > defaults), and execution. Delegates the agent loop to `ralph.core`.

## PRD Argument Behavior

- `--prd` is required and accepts one or more values.
- Each value can be a file, directory, or wildcard pattern (for example `"docs/prds/*/PRD.md"`).
- Directory inputs prefer `README.md` / `PRD.md` and then fall back to recursive PRD discovery.
- When `--prd` resolves to multiple files, they are passed as context files to the agent run.
- Omitting `--prd` produces an actionable error with usage guidance.

## Read Next

- [Core](../core/README.md)
