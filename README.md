# ralph

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)

Autonomous coding agent that implements tasks from PRDs. Powered by Claude, runs in a terminal TUI.

Ralph reads a Product Requirements Document, picks the highest-priority task, implements it, and repeats — hands-free.

## How it works

1. You write a PRD describing what you want built
2. Ralph decomposes it into ordered tasks
3. The agent loop picks the next task, writes code, and commits
4. Repeat until all tasks are done or iterations run out

Each iteration uses Claude via the [Agent SDK](https://github.com/anthropics/agent-sdk) with full tool access (file editing, bash, etc.) inside your repo.

## Install

```bash
uv tool install .
```

Requires Python 3.13+ and a valid [Anthropic API key](https://console.anthropic.com/).

## Setup

Set your API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Optional config at `~/.ralph/config.json`:

```json
{
  "discord_webhook_url": "https://discord.com/api/webhooks/...",
  "prd_directory": "docs/prds"
}
```

Or set `RALPH_DISCORD_WEBHOOK` env var for Discord notifications.

## Usage

```bash
# Launch TUI — browse PRDs, pick one, and run
ralph 5

# Run a specific PRD headless
ralph 10 --prd docs/prds/my-feature --tasks docs/prds/my-feature/tasks.md

# View past runs
ralph runs
```

## Features

- **Autonomous agent loop** — runs N iterations, each picking and implementing the next task
- **Textual TUI** — PRD browser, live streaming output, task progress panel, iteration sidebar
- **PRD management** — browse, preview, delete PRDs; import GitHub issues as PRDs
- **Run history** — persisted JSONL event logs with metadata, browsable from TUI or CLI
- **Discord notifications** — webhook alerts after each iteration with status and summary
- **Early exit** — agent signals completion when all tasks are done, no wasted iterations

## CLI options

| Flag | Description |
|---|---|
| `--prd PATH` | PRD directory path |
| `--tasks PATH` | Task list markdown file |
| `--cwd PATH` | Working directory for the agent |
| `--permission-mode` | `default`, `acceptEdits`, `plan`, `bypassPermissions` |
| `--model` | Claude model to use |
| `--no-tui` | Headless mode (Rich output) |

## Stack

Python · [Claude Agent SDK](https://github.com/anthropics/agent-sdk) · Textual · Rich · httpx

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
