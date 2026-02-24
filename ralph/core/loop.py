"""The agent loop — run_iteration and run_ralph."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import AsyncIterator

from claude_agent_sdk import (
    ClaudeAgentOptions,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    SystemMessage,
    query,
)

from ralph.core.config import RalphConfig
from ralph.core.prompts import SYSTEM_PROMPT, COMPLETION_SIGNAL, build_prompt
from ralph.traces import (
    RunRecorder,
    TextEvent,
    ThinkingEvent,
    ToolUseEvent,
    ToolResultEvent,
    UserMessageEvent,
)


@dataclass
class IterationResult:
    iteration: int
    text: str
    is_complete: bool
    duration_s: float = 0.0


async def run_iteration(
    config: RalphConfig,
    iteration: int,
    recorder: RunRecorder | None = None,
) -> AsyncIterator[str | IterationResult]:
    """Run a single Ralph iteration. Yields text chunks, then a final IterationResult."""
    start = time.monotonic()
    prompt = build_prompt(config)

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode=config.permission_mode,
        cwd=str(config.cwd),
        model=config.model,
        max_turns=config.max_turns,
    )

    full_text: list[str] = []

    _iter_ctx = recorder.open_iteration(iteration) if recorder is not None else None
    writer = _iter_ctx.__enter__() if _iter_ctx is not None else None

    try:
        async for message in query(prompt=prompt, options=options):
            match message:
                case msg if hasattr(msg, "content") and hasattr(msg, "model"):
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
