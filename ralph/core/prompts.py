from __future__ import annotations

from pathlib import Path


COMPLETION_SIGNAL = "<promise>COMPLETE</promise>"


def build_prompt_from_files(context_files: list[Path], iterations: int) -> str:
    refs = "\n".join(f"@{path}" for path in context_files)
    return f"""\
You are an autonomous coding agent in a stateless session.
Implement exactly ONE highest-priority unfinished task from tasks.md whose dependencies are satisfied.

SESSION MEMORY
- Read order: notebook.md -> tasks.md -> relevant PRD/task sections.
- notebook.md is your shared scratchpad — read it first, append findings at the end.
- Never delete or rewrite existing notes. Only append.

EXECUTION RULES
- Think privately; output concise progress only.
- Discovery budget before first edit: at most 10 reads and 8 grep/glob calls.
- If still unclear, make the best PRD-consistent assumption and proceed.
- Prefer backward compatibility unless task explicitly breaks it.
- Do not commit.
- Use repo-root-relative paths.
- Use uv run pytest for tests.
- Run targeted tests for touched area.
- Run broad tests only if cross-module interfaces or DB schema changed.
- If DB schema changed, run migrations before integration/flow tests.
- If boundaries changed, run tach check before finalizing.

DONE CONTRACT
- Update task checkbox/status in tasks.md.
- Append findings to notebook.md (constraints, decisions, gotchas — keep it short).
- If all tasks done, output <promise>COMPLETE</promise>; otherwise summarize task done + next task.

Referenced files:
{refs}"""
