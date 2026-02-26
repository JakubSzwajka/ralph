# ralph/core

The autonomous agent loop. Everything else (TUI, CLI, Discord) consumes this module.

## Public API

- `RalphConfig` — all settings for a run (PRD path, iterations, model, permissions, discord)
- `run_ralph(config)` — async generator yielding `(iteration, str | IterationResult)`
- `run_iteration(config, iteration)` — single iteration, yields text chunks then `IterationResult`
- `build_prompt(config)` — PRD-mode prompt with `@file` references
- `build_prompt_from_files(context_files, iterations)` — TUI-mode prompt from selected files
- `COMPLETION_SIGNAL` / `SYSTEM_PROMPT` — prompt constants

## How It Works

1. PRD + optional tasks file → sent to Claude via `claude-agent-sdk`
2. Each iteration: Claude picks next undone task, implements it, runs tests, updates task list
3. Exits on `<promise>COMPLETE</promise>` or max iterations reached
4. Agent is stateless between iterations — re-reads files each time

## Responsibility Boundary

Owns the agent loop and prompt construction. Does not own UI rendering or notifications — callers consume the async generator.

## Read Next

- [Browser](../browser/README.md)
