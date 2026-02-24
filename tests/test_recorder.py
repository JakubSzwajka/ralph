"""Tests for ralph/recorder.py — event schema, IterationWriter, RunRecorder —
and integration with run_iteration() in ralph/core.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ralph.recorder import (
    IterationWriter,
    RunRecorder,
    TextEvent,
    ThinkingEvent,
    ToolResultEvent,
    ToolUseEvent,
    UserMessageEvent,
)


# ---------------------------------------------------------------------------
# Event schema tests
# ---------------------------------------------------------------------------


class TestTextEvent:
    def test_to_json_line_has_type_text(self) -> None:
        line = TextEvent(text="hello").to_json_line()
        obj = json.loads(line)
        assert obj["type"] == "text"

    def test_to_json_line_preserves_text(self) -> None:
        line = TextEvent(text="world").to_json_line()
        obj = json.loads(line)
        assert obj["text"] == "world"

    def test_to_json_line_has_timestamp(self) -> None:
        obj = json.loads(TextEvent(text="x").to_json_line())
        assert "timestamp" in obj
        assert obj["timestamp"]  # non-empty string

    def test_to_json_line_is_single_line(self) -> None:
        line = TextEvent(text="single line").to_json_line()
        assert "\n" not in line


class TestThinkingEvent:
    def test_type_is_thinking(self) -> None:
        obj = json.loads(ThinkingEvent(thinking="thoughts", signature="sig").to_json_line())
        assert obj["type"] == "thinking"

    def test_fields_preserved(self) -> None:
        obj = json.loads(ThinkingEvent(thinking="deep thought", signature="abc123").to_json_line())
        assert obj["thinking"] == "deep thought"
        assert obj["signature"] == "abc123"


class TestToolUseEvent:
    def test_type_is_tool_use(self) -> None:
        obj = json.loads(ToolUseEvent(name="Bash", input="ls").to_json_line())
        assert obj["type"] == "tool_use"

    def test_fields_preserved(self) -> None:
        obj = json.loads(ToolUseEvent(name="Read", input="{'file': 'x'}").to_json_line())
        assert obj["name"] == "Read"
        assert obj["input"] == "{'file': 'x'}"


class TestToolResultEvent:
    def test_type_is_tool_result(self) -> None:
        obj = json.loads(ToolResultEvent(tool_use_id="id1", content="output").to_json_line())
        assert obj["type"] == "tool_result"

    def test_fields_preserved(self) -> None:
        obj = json.loads(ToolResultEvent(tool_use_id="abc", content="result text").to_json_line())
        assert obj["tool_use_id"] == "abc"
        assert obj["content"] == "result text"


class TestUserMessageEvent:
    def test_type_is_user_message(self) -> None:
        obj = json.loads(UserMessageEvent(content="hi").to_json_line())
        assert obj["type"] == "user_message"

    def test_content_preserved(self) -> None:
        obj = json.loads(UserMessageEvent(content="hello world").to_json_line())
        assert obj["content"] == "hello world"


# ---------------------------------------------------------------------------
# IterationWriter tests
# ---------------------------------------------------------------------------


class TestIterationWriter:
    def test_write_event_appends_json_line(self, tmp_path: Path) -> None:
        path = tmp_path / "iteration-01.jsonl"
        writer = IterationWriter(path)
        writer.write_event(TextEvent(text="hello"))
        writer.close()

        lines = path.read_text().splitlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["type"] == "text"
        assert obj["text"] == "hello"

    def test_write_multiple_events(self, tmp_path: Path) -> None:
        path = tmp_path / "iteration-01.jsonl"
        writer = IterationWriter(path)
        writer.write_event(TextEvent(text="a"))
        writer.write_event(TextEvent(text="b"))
        writer.write_event(ToolUseEvent(name="Bash", input="ls"))
        writer.close()

        lines = path.read_text().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[2])["type"] == "tool_use"

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "iteration-01.jsonl"
        writer = IterationWriter(path)
        for i in range(5):
            writer.write_event(TextEvent(text=f"chunk {i}"))
        writer.close()

        for line in path.read_text().splitlines():
            json.loads(line)  # must not raise


# ---------------------------------------------------------------------------
# RunRecorder tests
# ---------------------------------------------------------------------------


class TestRunRecorder:
    def test_creates_run_directory(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        assert recorder.run_dir.exists()
        assert recorder.run_dir.is_dir()

    def test_run_dir_is_under_ralph_runs(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        assert recorder.run_dir.parent == tmp_path / ".ralph" / "runs"

    def test_run_id_matches_dir_name(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        assert recorder.run_dir.name == recorder.run_id

    def test_open_iteration_creates_jsonl_file(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        with recorder.open_iteration(1) as writer:
            writer.write_event(TextEvent(text="test"))
        jsonl = recorder.run_dir / "iteration-01.jsonl"
        assert jsonl.exists()

    def test_open_iteration_numbering(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        with recorder.open_iteration(3) as writer:
            writer.write_event(TextEvent(text="x"))
        assert (recorder.run_dir / "iteration-03.jsonl").exists()

    def test_open_iteration_context_manager_closes_file(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        with recorder.open_iteration(1) as writer:
            writer.write_event(TextEvent(text="data"))
        # After context exit the file handle should be closed; reading must work.
        content = (recorder.run_dir / "iteration-01.jsonl").read_text()
        assert content.strip()  # non-empty


# ---------------------------------------------------------------------------
# Integration: run_iteration() writes events to JSONL
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


@pytest.mark.asyncio
async def test_run_iteration_creates_jsonl_with_events(tmp_path: Path) -> None:
    """run_iteration() with a recorder writes events to iteration-01.jsonl."""
    from ralph.core import RalphConfig, run_iteration
    from ralph.recorder import RunRecorder

    config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
    recorder = RunRecorder(tmp_path)

    text_block = _mock_text_block("hello from agent")
    assistant_msg = _make_assistant_message([text_block])

    with patch("ralph.core.query", return_value=_async_gen(assistant_msg)):
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
    from ralph.core import RalphConfig, run_iteration
    from ralph.recorder import RunRecorder

    config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
    recorder = RunRecorder(tmp_path)

    tool_use = _mock_tool_use_block("Bash", {"command": "ls"})
    tool_result = _mock_tool_result_block("id-123", "file1\nfile2")
    assistant_msg = _make_assistant_message([tool_use, tool_result])

    with patch("ralph.core.query", return_value=_async_gen(assistant_msg)):
        async for _ in run_iteration(config, 1, recorder):
            pass

    lines = (recorder.run_dir / "iteration-01.jsonl").read_text().splitlines()
    types = [json.loads(l)["type"] for l in lines]
    assert "tool_use" in types
    assert "tool_result" in types


@pytest.mark.asyncio
async def test_run_iteration_without_recorder_works(tmp_path: Path) -> None:
    """run_iteration() without a recorder (recorder=None) still yields results."""
    from ralph.core import RalphConfig, run_iteration

    config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
    text_block = _mock_text_block("no recorder")
    assistant_msg = _make_assistant_message([text_block])

    items = []
    with patch("ralph.core.query", return_value=_async_gen(assistant_msg)):
        async for item in run_iteration(config, 1, recorder=None):
            items.append(item)

    # Should yield the text chunk and then the IterationResult
    assert any(isinstance(item, str) for item in items)


# ---------------------------------------------------------------------------
# Task 4: meta.json written at run start and end
# ---------------------------------------------------------------------------


class TestRunRecorderMeta:
    def test_write_meta_start_creates_meta_json(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        from ralph.recorder import RunRecorder

        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)

        meta_path = recorder.run_dir / "meta.json"
        assert meta_path.exists()

    def test_write_meta_start_contains_started_at(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        from ralph.recorder import RunRecorder

        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert "started_at" in meta
        assert meta["started_at"]  # non-empty

    def test_write_meta_start_contains_config_fields(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        from ralph.recorder import RunRecorder

        config = RalphConfig(
            prd=Path("docs/prds/my-feature/README.md"),
            tasks=Path("docs/prds/my-feature/tasks.md"),
            iterations=5,
            model="claude-opus-4-5",
            permission_mode="bypassPermissions",
            cwd=tmp_path,
        )
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["prd"] == "docs/prds/my-feature/README.md"
        assert meta["tasks"] == "docs/prds/my-feature/tasks.md"
        assert meta["iterations_requested"] == 5
        assert meta["model"] == "claude-opus-4-5"
        assert meta["permission_mode"] == "bypassPermissions"

    def test_write_meta_start_tasks_none(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        from ralph.recorder import RunRecorder

        config = RalphConfig(prd=Path("PRD.md"), tasks=None, cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["tasks"] is None

    def test_write_meta_end_adds_completed_at(self, tmp_path: Path) -> None:
        from ralph.core import IterationResult, RalphConfig
        from ralph.recorder import RunRecorder

        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        results = [
            IterationResult(iteration=1, text="done", is_complete=True, duration_s=2.0)
        ]
        recorder.write_meta_end(results)

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert "started_at" in meta
        assert "completed_at" in meta
        assert meta["completed_at"]  # non-empty

    def test_write_meta_end_status_complete(self, tmp_path: Path) -> None:
        from ralph.core import IterationResult, RalphConfig
        from ralph.recorder import RunRecorder

        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        results = [
            IterationResult(iteration=1, text="done", is_complete=True, duration_s=1.0)
        ]
        recorder.write_meta_end(results)

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["status"] == "complete"

    def test_write_meta_end_status_max_iterations(self, tmp_path: Path) -> None:
        from ralph.core import IterationResult, RalphConfig
        from ralph.recorder import RunRecorder

        config = RalphConfig(prd=Path("PRD.md"), iterations=2, cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        results = [
            IterationResult(iteration=1, text="work", is_complete=False, duration_s=1.0),
            IterationResult(iteration=2, text="more", is_complete=False, duration_s=1.0),
        ]
        recorder.write_meta_end(results)

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["status"] == "max-iterations"

    def test_write_meta_end_status_error_on_no_results(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        from ralph.recorder import RunRecorder

        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        recorder.write_meta_end([])

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["status"] == "error"

    def test_write_meta_end_totals(self, tmp_path: Path) -> None:
        from ralph.core import IterationResult, RalphConfig
        from ralph.recorder import RunRecorder

        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        results = [
            IterationResult(iteration=1, text="a", is_complete=False, duration_s=3.0),
            IterationResult(iteration=2, text="b", is_complete=True, duration_s=7.0),
        ]
        recorder.write_meta_end(results)

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["iterations_completed"] == 2
        assert abs(meta["total_duration_s"] - 10.0) < 1e-9

    def test_meta_json_is_readable_without_start(self, tmp_path: Path) -> None:
        """write_meta_end works even if write_meta_start was never called."""
        from ralph.core import IterationResult
        from ralph.recorder import RunRecorder

        recorder = RunRecorder(tmp_path)
        results = [
            IterationResult(iteration=1, text="x", is_complete=True, duration_s=0.0)
        ]
        # Should not raise
        recorder.write_meta_end(results)
        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["status"] == "complete"


# ---------------------------------------------------------------------------
# Task 7: Auto-add .ralph/runs/ to .gitignore
# ---------------------------------------------------------------------------


class TestRunRecorderGitignore:
    def test_creates_gitignore_when_missing(self, tmp_path: Path) -> None:
        """RunRecorder creates .gitignore with .ralph/runs/ when file is absent."""
        RunRecorder(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".ralph/runs/" in gitignore.read_text().splitlines()

    def test_appends_to_existing_gitignore(self, tmp_path: Path) -> None:
        """RunRecorder appends the pattern to an existing .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")

        RunRecorder(tmp_path)

        lines = gitignore.read_text().splitlines()
        assert "*.pyc" in lines
        assert "__pycache__/" in lines
        assert ".ralph/runs/" in lines

    def test_does_not_duplicate_pattern(self, tmp_path: Path) -> None:
        """RunRecorder does not add the pattern twice when already present."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".ralph/runs/\n", encoding="utf-8")

        RunRecorder(tmp_path)
        RunRecorder(tmp_path)

        count = gitignore.read_text().splitlines().count(".ralph/runs/")
        assert count == 1

    def test_appends_on_new_line_when_no_trailing_newline(self, tmp_path: Path) -> None:
        """Pattern is placed on its own line even when existing file lacks a trailing newline."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log", encoding="utf-8")  # no trailing \n

        RunRecorder(tmp_path)

        lines = gitignore.read_text().splitlines()
        assert ".ralph/runs/" in lines
        assert "*.log" in lines  # original entry preserved

    def test_creates_gitignore_with_only_pattern_when_root_empty(self, tmp_path: Path) -> None:
        """Newly created .gitignore contains exactly the expected pattern line."""
        RunRecorder(tmp_path)
        content = (tmp_path / ".gitignore").read_text()
        assert content.strip() == ".ralph/runs/"


@pytest.mark.asyncio
async def test_run_ralph_writes_meta_json(tmp_path: Path) -> None:
    """run_ralph() writes meta.json with both started_at and completed_at."""
    from ralph.core import RalphConfig, run_ralph

    config = RalphConfig(prd=Path("PRD.md"), iterations=1, cwd=tmp_path)

    text_block = _mock_text_block("<promise>COMPLETE</promise>")
    assistant_msg = _make_assistant_message([text_block])

    with patch("ralph.core.query", return_value=_async_gen(assistant_msg)):
        async for _ in run_ralph(config):
            pass

    # Find the run directory (there should be exactly one)
    runs_dir = tmp_path / ".ralph" / "runs"
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1

    meta = json.loads((run_dirs[0] / "meta.json").read_text())
    assert "started_at" in meta
    assert "completed_at" in meta
    assert meta["status"] == "complete"
