# ralph/core

The autonomous agent loop. This is the only module that matters — everything else is UI and side-effects.

## How it works

```
PRD + Tasks → [iteration 1] → [iteration 2] → ... → [iteration N or COMPLETE]
```

1. **Input**: a PRD file and an optional tasks file (markdown with checkboxes)
2. **Loop**: run up to N iterations, each sending the PRD + tasks to Claude via `claude-agent-sdk`
3. **Per iteration**: Claude reads the PRD, picks the next undone task, implements it, runs tests, updates the task list
4. **Exit conditions**: all tasks done (agent outputs `<promise>COMPLETE</promise>`) or max iterations reached

That's it. The agent is stateless between iterations — it re-reads the PRD and tasks each time, seeing its own prior file changes.

## Module layout

| File | Purpose |
|---|---|
| `config.py` | `RalphConfig` dataclass — all settings for a run |
| `prompts.py` | System prompt, completion signal, prompt builder |
| `loop.py` | `run_iteration()` and `run_ralph()` — the actual loop |

## RalphConfig

```python
RalphConfig(
    prd=Path("docs/prds/my-feature"),
    tasks=Path("docs/prds/my-feature/tasks.md"),
    iterations=10,
    cwd=Path.cwd(),
    permission_mode="bypassPermissions",
    model=None,          # uses SDK default
    max_turns=None,      # uses SDK default
)
```

## Standalone usage

```python
import asyncio
from ralph.core import RalphConfig, run_ralph, IterationResult

async def main():
    config = RalphConfig(prd=Path("PRD.md"), iterations=5)
    async for iteration, item in run_ralph(config):
        if isinstance(item, IterationResult):
            print(f"Iteration {item.iteration}: complete={item.is_complete}")
        else:
            print(item, end="")

asyncio.run(main())
```

## Prompt design

The system prompt constrains the agent to:
- Work on **one task per iteration**
- Make its own decisions (no user in the loop)
- Never commit unless told to
- Signal completion when done

The user prompt points at the PRD and tasks files using `@file` references so the SDK resolves them as context.
