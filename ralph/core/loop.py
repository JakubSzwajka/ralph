from __future__ import annotations

import time
from dataclasses import dataclass
from collections.abc import AsyncIterator

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    SystemMessage,
)

from ralph.core.config import RalphConfig
from ralph.core.format_stream import format_block
from ralph.core.prompts import (
    COMPLETION_SIGNAL,
    build_prompt_from_files,
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
) -> AsyncIterator[str | IterationResult]:
    """Run a single Ralph iteration. Yields text chunks, then a final IterationResult."""
    start = time.monotonic()
    prompt = build_prompt_from_files(config.context_files, config.iterations)
    options = ClaudeAgentOptions(
        system_prompt=prompt,
        permission_mode=config.permission_mode,
        cwd=str(config.cwd),
        model=config.model,
        # max_turns=config.max_turns,
    )

    full_text: list[str] = []

    stream = query(prompt=prompt, options=options)
    try:
        async for message in stream:
            match message:
                case msg if hasattr(msg, "content") and hasattr(msg, "model"):
                    for block in msg.content:
                        if isinstance(block, str):
                            full_text.append(block)
                            yield block
                        elif isinstance(block, SystemMessage):
                            pass
                        elif isinstance(block, TextBlock):
                            full_text.append(block.text)
                            yield block.text
                        elif isinstance(block, ThinkingBlock):
                            # Suppressed — keep raw slug in full_text for
                            # COMPLETION_SIGNAL detection, but don't yield.
                            slug = f"{block.signature}::{block.thinking}"
                            full_text.append(slug)
                        elif isinstance(block, ToolUseBlock):
                            formatted = format_block(
                                block.name, block.input, cwd=config.cwd
                            )
                            if formatted is not None:
                                full_text.append(formatted)
                                yield formatted
                            else:
                                # Suppressed variant — keep raw slug in full_text.
                                full_text.append(f"{block.name}::{block.input!s}")
                        elif isinstance(block, ToolResultBlock):
                            # Suppressed — keep raw slug in full_text for
                            # COMPLETION_SIGNAL detection, but don't yield.
                            slug = f"{block.tool_use_id}::{block.content!s}"
                            full_text.append(slug)
                        elif isinstance(block, UserMessage):
                            slug = block.content
                            if isinstance(slug, list):
                                slug = "\n".join(str(item) for item in slug)
                            full_text.append(slug)
                            yield slug
                        else:
                            pass
                    combined_so_far = "\n".join(full_text)
                    if COMPLETION_SIGNAL in combined_so_far:
                        break
                case _:
                    pass
    finally:
        try:
            await stream.aclose()
        except (RuntimeError, GeneratorExit):
            pass  # anyio cancel-scope cleanup race on early break

    combined = "\n".join(full_text)
    elapsed = time.monotonic() - start

    yield IterationResult(
        iteration=iteration,
        text=combined,
        is_complete=COMPLETION_SIGNAL in combined,
        duration_s=elapsed,
    )


async def run_ralph(
    config: RalphConfig,
) -> AsyncIterator[tuple[int, str | IterationResult]]:
    """Run the full Ralph loop. Yields (iteration, text_chunk | IterationResult)."""
    results: list[IterationResult] = []
    for i in range(1, config.iterations + 1):
        async for item in run_iteration(config, i):
            yield (i, item)
            if isinstance(item, IterationResult):
                results.append(item)
                if item.is_complete:
                    return
