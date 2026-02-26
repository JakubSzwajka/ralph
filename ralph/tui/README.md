# ralph/tui

Textual-based terminal UI for interactive file selection and run monitoring.

## Public API

- `RalphApp` — main Textual app: file browser, run launcher, history viewer

## Key Screens

- **Main** — `DocTree` file browser with detail panel; `r` to run, `h` for history
- **RunScreen** — live streaming output during a run; `k` to stop, `Esc` to go back
- **RunBrowserScreen** — history of past runs with log viewer
- **ConfirmRunScreen** / **ConfirmQuitScreen** — modal confirmations

## Responsibility Boundary

Owns the interactive UI, file selection, and live run display. Delegates the agent loop to `ralph.core` (runs in-process via asyncio worker). Only one run at a time per app instance.

## Read Next

- [Core](../core/README.md)
- [Browser](../browser/README.md)
- [CLI](../cli/README.md)
