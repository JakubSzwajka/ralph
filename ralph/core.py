from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from claude_agent_sdk import (
    ClaudeAgentOptions,
    PermissionMode,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    SystemMessage,
    query,
)

from ralph.recorder import (
    RunRecorder,
    TextEvent,
    ThinkingEvent,
    ToolUseEvent,
    ToolResultEvent,
    UserMessageEvent,
)


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


@dataclass
class IterationResult:
    iteration: int
    text: str
    is_complete: bool
    duration_s: float = 0.0


@dataclass
class RalphConfig:
    prd: Path = Path("PRD.md")
    tasks: Path | None = None
    iterations: int = 10
    cwd: Path = field(default_factory=Path.cwd)
    permission_mode: PermissionMode = "bypassPermissions"
    model: str | None = None
    max_turns: int | None = None
    discord_webhook_url: str | None = None
    discord_notify: bool = False
    discord_min_interval: float = 5.0

    def __post_init__(self) -> None:
        # Auto-enable notifications when a webhook URL is provided
        if self.discord_webhook_url is not None and not self.discord_notify:
            self.discord_notify = True


def _build_prompt(config: RalphConfig) -> str:
    tasks_ref = f"@{config.tasks}" if config.tasks else ""
    return f"""\
Your task is to implement the stories in the tasks list.

The whole PRD is @{config.prd}. The tasks list (or directory with stories) is in {tasks_ref}.

1. Find the highest-priority/next task and implement it.
2. Run your tests and type checks.
3. Update the tasks list with what was done and the progress.
4. Review your changes and make sure they are correct.

If the PRD is complete, output {COMPLETION_SIGNAL}."""


async def run_iteration(
    config: RalphConfig,
    iteration: int,
    recorder: RunRecorder | None = None,
) -> AsyncIterator[str | IterationResult]:
    """Run a single Ralph iteration. Yields text chunks, then a final IterationResult."""
    import time

    start = time.monotonic()
    prompt = _build_prompt(config)

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode=config.permission_mode,
        cwd=str(config.cwd),
        model=config.model,
        max_turns=config.max_turns,
    )

    full_text: list[str] = []

    # Open the iteration writer if a recorder was provided.  We enter the
    # context manager manually so we can wrap the entire async loop.
    _iter_ctx = recorder.open_iteration(iteration) if recorder is not None else None
    writer = _iter_ctx.__enter__() if _iter_ctx is not None else None

    try:
        async for message in query(prompt=prompt, options=options):
            match message:
                case msg if hasattr(msg, "content") and hasattr(msg, "model"):
                    # AssistantMessage
                    for block in msg.content:  # type: ignore
                        if isinstance(block, str):
                            full_text.append(block)
                            yield block
                            if writer is not None:
                                writer.write_event(TextEvent(text=block))
                        elif isinstance(block, SystemMessage):
                            pass
                        elif isinstance(block, TextBlock):
                            full_text.append(block.text)
                            yield block.text
                            if writer is not None:
                                writer.write_event(TextEvent(text=block.text))
                        elif isinstance(block, ThinkingBlock):
                            slug = f"{block.signature}::{block.thinking}"
                            full_text.append(slug)
                            yield slug
                            if writer is not None:
                                writer.write_event(
                                    ThinkingEvent(
                                        thinking=block.thinking,
                                        signature=block.signature,
                                    )
                                )
                        elif isinstance(block, ToolUseBlock):
                            slug = f"{block.name}::{str(block.input)}"
                            full_text.append(slug)
                            yield slug
                            if writer is not None:
                                writer.write_event(
                                    ToolUseEvent(
                                        name=block.name,
                                        input=str(block.input),
                                    )
                                )
                        elif isinstance(block, ToolResultBlock):
                            slug = f"{block.tool_use_id}::{str(block.content)}"
                            full_text.append(slug)
                            yield slug
                            if writer is not None:
                                writer.write_event(
                                    ToolResultEvent(
                                        tool_use_id=block.tool_use_id,
                                        content=str(block.content),
                                    )
                                )
                        elif isinstance(block, UserMessage):
                            slug = block.content
                            if isinstance(slug, list):
                                slug = "\n".join(str(item) for item in slug)
                            full_text.append(slug)
                            yield slug
                            if writer is not None:
                                writer.write_event(UserMessageEvent(content=slug))
                        else:
                            print(f"Unknown block type: {block}")
                case _:
                    print(f"Unknown message type: {type(msg)}")
    finally:
        if _iter_ctx is not None:
            _iter_ctx.__exit__(None, None, None)

    combined = "\n".join(full_text)
    elapsed = time.monotonic() - start

    yield IterationResult(
        iteration=iteration,
        text=combined,
        is_complete=COMPLETION_SIGNAL in combined,
        duration_s=elapsed,
    )


async def run_ralph(config: RalphConfig):
    """Run the full Ralph loop. Yields (iteration, text_chunk | IterationResult)."""
    recorder = RunRecorder(config.cwd)
    recorder.write_meta_start(config)
    results: list[IterationResult] = []
    try:
        for i in range(1, config.iterations + 1):
            async for item in run_iteration(config, i, recorder):
                yield (i, item)
                if isinstance(item, IterationResult):
                    results.append(item)
                    if item.is_complete:
                        return
    finally:
        recorder.write_meta_end(results)
