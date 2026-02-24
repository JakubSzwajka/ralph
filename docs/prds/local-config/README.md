---
status: draft
date: 2026-02-24
author: kuba
gh-issue: ""
---

# Local Configuration File

## Problem

Ralph currently requires Discord webhook URLs (and future settings) to be passed via CLI flags or environment variables every time. There's no persistent local configuration — users must remember flags or maintain shell aliases. As Ralph gains more configurable options, this becomes increasingly tedious.

## Proposed Solution

Add support for a JSON configuration file at `~/.ralph/config.json`. Ralph loads this file on startup and merges values into `RalphConfig`. The standard precedence chain applies: **CLI flags > environment variables > config file > defaults**.

A simple `ralph init` (or similar) command could scaffold the config file, but is not required for v1 — users can create it manually.

## Key Cases

- Ralph loads `~/.ralph/config.json` on startup if it exists
- Missing config file is silently ignored (not an error)
- Malformed JSON produces a clear error message and exits
- `discord_webhook_url` can be set in the config file
- `discord_min_interval` can be set in the config file
- CLI `--discord-webhook` overrides config file value
- `RALPH_DISCORD_WEBHOOK` env var overrides config file value
- Unknown keys in config are ignored (forward-compatible)

## Out of Scope

- GUI or TUI for editing config
- Config file format migration (we start with JSON, that's it)
- Per-project config (only global `~/.ralph/` for now)
- `ralph init` scaffolding command (can be added later)
- Config file watch / hot-reload

## Open Questions

- Should we support `~/.ralph/config.json` only, or also check `$XDG_CONFIG_HOME/ralph/config.json`?

## References

- Current config: `ralph/core.py` — `RalphConfig` dataclass
- Current CLI parsing: `ralph/cli.py` — argument resolution and env var fallback
- Current notifier: `ralph/notifier.py` — `DiscordNotifier`
