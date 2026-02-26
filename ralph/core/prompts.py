from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ralph.core.config import RalphConfig


COMPLETION_SIGNAL = "<promise>COMPLETE</promise>"

SYSTEM_PROMPT = """\
You are an autonomous coding agent. You implement tasks from a PRD one at a time.

RULES:
- ONLY WORK ON A SINGLE TASK per iteration.
- IF YOU NEED A DECISION, MAKE ONE based on the PRD and tasks list.
- PRIORITIZE BACKWARD COMPATIBILITY when making decisions.
- THERE IS NO USER to help you or answer questions. You are on your own.
- THINK OUT LOUD about your approach.
- PLAN CAREFULLY before writing code.
- NEVER COMMIT your changes unless explicitly asked.
- When all tasks are done, output <promise>COMPLETE</promise>.
"""


def build_prompt(config: RalphConfig) -> str:
    tasks_ref = f"@{config.tasks}" if config.tasks else ""
    return f"""\
Your task is to implement the stories in the tasks list.

The whole PRD is @{config.prd}. The tasks list (or directory with stories) is in {tasks_ref}.

1. Find the highest-priority/next task and implement it.
2. Run your tests and type checks.
3. Update the tasks list with what was done and the progress.
4. Review your changes and make sure they are correct.

If the PRD is complete, output {COMPLETION_SIGNAL}."""


def build_prompt_from_files(context_files: list[Path], iterations: int) -> str:
    refs = "\n".join(f"@{path}" for path in context_files)
    return f"""\
Read the referenced files below. Find the highest-priority unfinished task, implement it, run tests, and update task status. If everything is complete, output {COMPLETION_SIGNAL}.

{refs}"""
