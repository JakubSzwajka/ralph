"""Tests for ralph/recorder.py — event schema, IterationWriter, RunRecorder."""
from __future__ import annotations

import json
from pathlib import Path

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
# RunRecorder meta tests
# ---------------------------------------------------------------------------


class TestRunRecorderMeta:
    def test_write_meta_start_creates_meta_json(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig

        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)

        meta_path = recorder.run_dir / "meta.json"
        assert meta_path.exists()

    def test_write_meta_start_contains_started_at(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig

        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert "started_at" in meta
        assert meta["started_at"]

    def test_write_meta_start_contains_config_fields(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig

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

        config = RalphConfig(prd=Path("PRD.md"), tasks=None, cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["tasks"] is None

    def test_write_meta_end_adds_completed_at(self, tmp_path: Path) -> None:
        from ralph.core import IterationResult, RalphConfig

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

    def test_write_meta_end_status_complete(self, tmp_path: Path) -> None:
        from ralph.core import IterationResult, RalphConfig

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

        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        recorder.write_meta_end([])

        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["status"] == "error"

    def test_write_meta_end_totals(self, tmp_path: Path) -> None:
        from ralph.core import IterationResult, RalphConfig

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
        from ralph.core import IterationResult

        recorder = RunRecorder(tmp_path)
        results = [
            IterationResult(iteration=1, text="x", is_complete=True, duration_s=0.0)
        ]
        recorder.write_meta_end(results)
        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["status"] == "complete"


# ---------------------------------------------------------------------------
# Gitignore auto-management
# ---------------------------------------------------------------------------


class TestRunRecorderGitignore:
    def test_creates_gitignore_when_missing(self, tmp_path: Path) -> None:
        RunRecorder(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".ralph/runs/" in gitignore.read_text().splitlines()

    def test_appends_to_existing_gitignore(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")

        RunRecorder(tmp_path)

        lines = gitignore.read_text().splitlines()
        assert "*.pyc" in lines
        assert "__pycache__/" in lines
        assert ".ralph/runs/" in lines

    def test_does_not_duplicate_pattern(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".ralph/runs/\n", encoding="utf-8")

        RunRecorder(tmp_path)
        RunRecorder(tmp_path)

        count = gitignore.read_text().splitlines().count(".ralph/runs/")
        assert count == 1

    def test_appends_on_new_line_when_no_trailing_newline(self, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log", encoding="utf-8")

        RunRecorder(tmp_path)

        lines = gitignore.read_text().splitlines()
        assert ".ralph/runs/" in lines
        assert "*.log" in lines

    def test_creates_gitignore_with_only_pattern_when_root_empty(self, tmp_path: Path) -> None:
        RunRecorder(tmp_path)
        content = (tmp_path / ".gitignore").read_text()
        assert content.strip() == ".ralph/runs/"
