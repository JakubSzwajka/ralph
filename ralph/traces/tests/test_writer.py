"""Tests for IterationWriter and RunRecorder."""
from __future__ import annotations

import json
from pathlib import Path

from ralph.traces import IterationWriter, RunRecorder, TextEvent, ToolUseEvent


class TestIterationWriter:
    def test_write_event_appends_json_line(self, tmp_path: Path) -> None:
        path = tmp_path / "iteration-01.jsonl"
        writer = IterationWriter(path)
        writer.write_event(TextEvent(text="hello"))
        writer.close()
        obj = json.loads(path.read_text().splitlines()[0])
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

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "iteration-01.jsonl"
        writer = IterationWriter(path)
        for i in range(5):
            writer.write_event(TextEvent(text=f"chunk {i}"))
        writer.close()
        for line in path.read_text().splitlines():
            json.loads(line)


class TestRunRecorder:
    def test_creates_run_directory(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        assert recorder.run_dir.exists()

    def test_run_dir_is_under_ralph_runs(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        assert recorder.run_dir.parent == tmp_path / ".ralph" / "runs"

    def test_open_iteration_creates_jsonl_file(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        with recorder.open_iteration(1) as writer:
            writer.write_event(TextEvent(text="test"))
        assert (recorder.run_dir / "iteration-01.jsonl").exists()

    def test_open_iteration_numbering(self, tmp_path: Path) -> None:
        recorder = RunRecorder(tmp_path)
        with recorder.open_iteration(3) as writer:
            writer.write_event(TextEvent(text="x"))
        assert (recorder.run_dir / "iteration-03.jsonl").exists()


class TestRunRecorderMeta:
    def test_write_meta_start_creates_meta_json(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        config = RalphConfig(
            prd=Path("PRD.md"),
            cwd=tmp_path,
            context_files=[Path("src/main.py"), Path("docs/README.md")],
        )
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        meta_path = recorder.run_dir / "meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["context_files"] == ["src/main.py", "docs/README.md"]

    def test_write_meta_end_status_complete(self, tmp_path: Path) -> None:
        from ralph.core import IterationResult, RalphConfig
        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        recorder.write_meta_end([IterationResult(iteration=1, text="done", is_complete=True, duration_s=1.0)])
        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["status"] == "complete"

    def test_write_meta_end_status_max_iterations(self, tmp_path: Path) -> None:
        from ralph.core import IterationResult, RalphConfig
        config = RalphConfig(prd=Path("PRD.md"), iterations=2, cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        recorder.write_meta_end([
            IterationResult(iteration=1, text="work", is_complete=False, duration_s=1.0),
            IterationResult(iteration=2, text="more", is_complete=False, duration_s=1.0),
        ])
        assert json.loads((recorder.run_dir / "meta.json").read_text())["status"] == "max-iterations"

    def test_write_meta_end_status_error(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        recorder.write_meta_end([])
        assert json.loads((recorder.run_dir / "meta.json").read_text())["status"] == "error"


class TestRunRecorderMetaProgress:
    def test_write_meta_progress_sets_running_status(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        recorder.write_meta_progress(1)
        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["status"] == "running"
        assert meta["iterations_completed"] == 1

    def test_write_meta_progress_increments(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        config = RalphConfig(prd=Path("PRD.md"), iterations=3, cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        for i in range(1, 4):
            recorder.write_meta_progress(i)
            meta = json.loads((recorder.run_dir / "meta.json").read_text())
            assert meta["iterations_completed"] == i
            assert meta["status"] == "running"

    def test_write_meta_progress_preserves_start_fields(self, tmp_path: Path) -> None:
        from ralph.core import RalphConfig
        config = RalphConfig(prd=Path("PRD.md"), cwd=tmp_path)
        recorder = RunRecorder(tmp_path)
        recorder.write_meta_start(config)
        recorder.write_meta_progress(1)
        meta = json.loads((recorder.run_dir / "meta.json").read_text())
        assert meta["run_id"] == recorder.run_id
        assert meta["prd"] == "PRD.md"


class TestRunRecorderGitignore:
    def test_creates_gitignore_when_missing(self, tmp_path: Path) -> None:
        RunRecorder(tmp_path)
        assert ".ralph/runs/" in (tmp_path / ".gitignore").read_text().splitlines()

    def test_does_not_duplicate_pattern(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text(".ralph/runs/\n", encoding="utf-8")
        RunRecorder(tmp_path)
        RunRecorder(tmp_path)
        assert (tmp_path / ".gitignore").read_text().splitlines().count(".ralph/runs/") == 1
