# ralph/core

The autonomous agent loop. Everything else (CLI, notifications) consumes this module.

## Public API

- `RalphConfig` — all settings for a run (PRD path, iterations, model, permissions, discord)
- `run_ralph(config, session_id)` — async generator yielding `(iteration, str | IterationResult)`
- `run_iteration(config, iteration, session_id)` — single iteration, yields text chunks then `IterationResult`
- `build_prompt(config)` / `build_prompt_from_files(context_files, iterations)` — prompt builders
- `COMPLETION_SIGNAL` / `SYSTEM_PROMPT` — prompt constants
- `RunMeta` / `RunStatus` — run metadata and persistence
- `generate_run_id()` / `default_runs_dir()` — run directory helpers

## How It Works

1. PRD + optional context files → prompt sent to Claude via `claude_agent_sdk.query()`
2. Each iteration: Claude picks next undone task, implements it, updates task list
3. Exits on `<promise>COMPLETE</promise>` or max iterations reached
4. Runs in-process — no subprocess spawning

## Responsibility Boundary

Owns the agent loop, prompt construction, and run metadata. Does not own UI rendering or notifications — callers consume the async generator.

## Read Next

- [CLI](../cli/README.md)
