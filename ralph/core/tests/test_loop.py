"""Tests for the core agent loop — run_iteration() and run_ralph()."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ralph.core import IterationResult, RalphConfig, run_iteration, run_ralph
from ralph.recorder import RunRecorder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_assistant_message(blocks: list) -> MagicMock:
    """Build a mock AssistantMessage (has .content list and .model attr)."""
    msg = MagicMock()
    msg.content = blocks
    msg.model = "claude-test"
    return msg


def _mock_text_block(text: str) -> MagicMock:
    from claude_agent_sdk import TextBlock

    block = MagicMock(spec=TextBlock)
    block.text = text
    return block


def _mock_tool_use_block(name: str, input_: dict) -> MagicMock:
    from claude_agent_sdk import ToolUseBlock

    block = MagicMock(spec=ToolUseBlock)
    block.name = name
    block.input = input_
    return block


def _mock_tool_result_block(tool_use_id: str, content: str) -> MagicMock:
    from claude_agent_sdk import ToolResultBlock

    block = MagicMock(spec=ToolResultBlock)
    block.tool_use_id = tool_use_id
    block.content = content
    return block


async def _async_gen(*items):
    """Tiny helper: async generator from positional items."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# run_iteration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_iteration_creates_jsonl_with_events(tmp_path: Path) -> None:
    """run_iteration() with a recorder writes events to iteration-01.jsonl."""
    config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
    recorder = RunRecorder(tmp_path)

    text_block = _mock_text_block("hello from agent")
    assistant_msg = _make_assistant_message([text_block])

    with patch("ralph.core.loop.query", return_value=_async_gen(assistant_msg)):
        items = []
        async for item in run_iteration(config, 1, recorder):
            items.append(item)

    jsonl_path = recorder.run_dir / "iteration-01.jsonl"
    assert jsonl_path.exists(), "iteration-01.jsonl should be created"

    lines = jsonl_path.read_text().splitlines()
    assert len(lines) >= 1
    first = json.loads(lines[0])
    assert first["type"] == "text"
    assert first["text"] == "hello from agent"


@pytest.mark.asyncio
async def test_run_iteration_records_tool_use_and_result(tmp_path: Path) -> None:
    """ToolUseBlock and ToolResultBlock are recorded with correct event types."""
    config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
    recorder = RunRecorder(tmp_path)

    tool_use = _mock_tool_use_block("Bash", {"command": "ls"})
    tool_result = _mock_tool_result_block("id-123", "file1\nfile2")
    assistant_msg = _make_assistant_message([tool_use, tool_result])

    with patch("ralph.core.loop.query", return_value=_async_gen(assistant_msg)):
        async for _ in run_iteration(config, 1, recorder):
            pass

    lines = (recorder.run_dir / "iteration-01.jsonl").read_text().splitlines()
    types = [json.loads(l)["type"] for l in lines]
    assert "tool_use" in types
    assert "tool_result" in types


@pytest.mark.asyncio
async def test_run_iteration_without_recorder_works(tmp_path: Path) -> None:
    """run_iteration() without a recorder (recorder=None) still yields results."""
    config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
    text_block = _mock_text_block("no recorder")
    assistant_msg = _make_assistant_message([text_block])

    items = []
    with patch("ralph.core.loop.query", return_value=_async_gen(assistant_msg)):
        async for item in run_iteration(config, 1, recorder=None):
            items.append(item)

    assert any(isinstance(item, str) for item in items)


@pytest.mark.asyncio
async def test_run_iteration_yields_iteration_result(tmp_path: Path) -> None:
    """run_iteration() yields an IterationResult as final item."""
    config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
    text_block = _mock_text_block("work done")
    assistant_msg = _make_assistant_message([text_block])

    items = []
    with patch("ralph.core.loop.query", return_value=_async_gen(assistant_msg)):
        async for item in run_iteration(config, 1, recorder=None):
            items.append(item)

    result = items[-1]
    assert isinstance(result, IterationResult)
    assert result.iteration == 1
    assert not result.is_complete


@pytest.mark.asyncio
async def test_run_iteration_detects_completion(tmp_path: Path) -> None:
    """run_iteration() sets is_complete when COMPLETION_SIGNAL is in output."""
    config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
    text_block = _mock_text_block("<promise>COMPLETE</promise>")
    assistant_msg = _make_assistant_message([text_block])

    items = []
    with patch("ralph.core.loop.query", return_value=_async_gen(assistant_msg)):
        async for item in run_iteration(config, 1, recorder=None):
            items.append(item)

    result = items[-1]
    assert isinstance(result, IterationResult)
    assert result.is_complete


# ---------------------------------------------------------------------------
# run_ralph tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ralph_writes_meta_json(tmp_path: Path) -> None:
    """run_ralph() writes meta.json with both started_at and completed_at."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1, cwd=tmp_path)

    text_block = _mock_text_block("<promise>COMPLETE</promise>")
    assistant_msg = _make_assistant_message([text_block])

    with patch("ralph.core.loop.query", return_value=_async_gen(assistant_msg)):
        async for _ in run_ralph(config):
            pass

    runs_dir = tmp_path / ".ralph" / "runs"
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1

    meta = json.loads((run_dirs[0] / "meta.json").read_text())
    assert "started_at" in meta
    assert "completed_at" in meta
    assert meta["status"] == "complete"


@pytest.mark.asyncio
async def test_run_ralph_stops_on_completion(tmp_path: Path) -> None:
    """run_ralph() stops iterating when agent signals COMPLETE."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=5, cwd=tmp_path)

    text_block = _mock_text_block("<promise>COMPLETE</promise>")
    assistant_msg = _make_assistant_message([text_block])

    iterations_seen = set()
    with patch("ralph.core.loop.query", return_value=_async_gen(assistant_msg)):
        async for iteration, item in run_ralph(config):
            iterations_seen.add(iteration)

    assert iterations_seen == {1}, "Should stop after first iteration"
