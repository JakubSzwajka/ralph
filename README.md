# ralph

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)

Autonomous coding agent that implements tasks from PRDs. Powered by Claude, runs in your terminal.

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
  "discord_webhook_url": "https://discord.com/api/webhooks/..."
}
```

Or set `RALPH_DISCORD_WEBHOOK` env var for Discord notifications.

## Usage

```bash
# Run with one PRD file
ralph --max-turns 10 --prd docs/prds/my-feature/PRD.md

# Run with one PRD directory (auto-picks README.md/PRD.md)
ralph --max-turns 10 --prd docs/prds/my-feature

# Run with multiple PRD files (explicit list)
ralph --max-turns 10 --prd docs/prds/a/PRD.md docs/prds/b/PRD.md

# Run with wildcard(s)
ralph --max-turns 10 --prd "docs/prds/*/PRD.md"
```

## Features

- **Autonomous agent loop** — runs N iterations, each picking and implementing the next task
- **Rich CLI output** — live streaming output with task progress and iteration details
- **Run history files** — persisted logs and metadata under `.ralph/runs`
- **Discord notifications** — webhook alerts after each iteration with status and summary
- **Early exit** — agent signals completion when all tasks are done, no wasted iterations

## CLI options

| Flag | Description |
|---|---|
| `--prd PATH [PATH ...]` | PRD file(s), PRD directory(s), or wildcard patterns |
| `--tasks PATH` | Task list markdown file |
| `--cwd PATH` | Working directory for the agent |
| `--max-turns N` | Max Ralph loop iterations |
| `--permission-mode` | `default`, `acceptEdits`, `plan`, `bypassPermissions` |
| `--model` | Claude model to use |

## Stack

Python · [Claude Agent SDK](https://github.com/anthropics/agent-sdk) · Rich · httpx

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
