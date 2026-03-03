"""Tests for ralph.cli.runs — run-history CLI subcommand."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ralph.cli.runs import runs_main, _find_run, _fmt_duration
from ralph.core.run_meta import RunMeta


# ── Fixtures ────────────────────────────────────────────────────────────


def _write_run(
    runs_dir: Path,
    run_id: str,
    *,
    status: str = "done",
    prd: str = "test.md",
    pid: int | None = None,
    iterations_completed: int = 1,
    iterations_requested: int = 5,
    total_duration_s: float = 42.0,
    model: str | None = "sonnet",
) -> Path:
    """Write a minimal meta.json fixture and return the run directory."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": run_id,
        "pid": pid,
        "started_at": "2026-01-01T00:00:00+00:00",
        "completed_at": "2026-01-01T00:01:00+00:00",
        "status": status,
        "prd": prd,
        "tasks": None,
        "iterations_requested": iterations_requested,
        "iterations_completed": iterations_completed,
        "total_duration_s": total_duration_s,
        "model": model,
        "permission_mode": "bypassPermissions",
        "context_files": [],
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return run_dir


@pytest.fixture()
def runs_dir(tmp_path: Path) -> Path:
    """Return a temporary .ralph/runs directory."""
    d = tmp_path / ".ralph" / "runs"
    d.mkdir(parents=True)
    return d


# ── List view ───────────────────────────────────────────────────────────


class TestRunsList:
    """``ralph runs`` with no args lists runs."""

    def test_empty_runs_dir(self, runs_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(runs_dir.parent.parent)
        rc = runs_main([])
        assert rc == 0

    def test_lists_existing_runs(
        self,
        runs_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(runs_dir, "run-abc")
        _write_run(runs_dir, "run-xyz", status="error")
        monkeypatch.chdir(runs_dir.parent.parent)
        rc = runs_main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert "run-abc" in out
        assert "run-xyz" in out


# ── Detail view ─────────────────────────────────────────────────────────


class TestRunDetail:
    """``ralph runs <run_id>`` shows detail panel."""

    def test_detail_success(
        self,
        runs_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(runs_dir, "run-detail")
        monkeypatch.chdir(runs_dir.parent.parent)
        rc = runs_main(["run-detail"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "run-detail" in out

    def test_detail_unknown_run_id(
        self,
        runs_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(runs_dir.parent.parent)
        rc = runs_main(["no-such-run"])
        assert rc == 1


# ── Prefix matching ─────────────────────────────────────────────────────


class TestFindRun:
    """_find_run handles exact, prefix, and ambiguous matches."""

    def _make_runs(self) -> list[RunMeta]:
        return [
            RunMeta(run_id="2026-01-01T00-00-00"),
            RunMeta(run_id="2026-01-01T00-01-00"),
            RunMeta(run_id="2026-01-02T00-00-00"),
        ]

    def test_exact_match(self) -> None:
        runs = self._make_runs()
        result = _find_run("2026-01-02T00-00-00", runs)
        assert result is not None
        assert result.run_id == "2026-01-02T00-00-00"

    def test_unique_prefix_match(self) -> None:
        runs = self._make_runs()
        result = _find_run("2026-01-02", runs)
        assert result is not None
        assert result.run_id == "2026-01-02T00-00-00"

    def test_ambiguous_prefix_returns_none(self) -> None:
        runs = self._make_runs()
        result = _find_run("2026-01-01", runs)
        assert result is None

    def test_no_match_returns_none(self) -> None:
        runs = self._make_runs()
        result = _find_run("nope", runs)
        assert result is None


# ── Log view ────────────────────────────────────────────────────────────


class TestRunLog:
    """``ralph runs --log <id>`` prints log content."""

    def test_log_success(
        self,
        runs_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        run_dir = _write_run(runs_dir, "run-log")
        (run_dir / "output.log").write_text("hello from agent\n")
        monkeypatch.chdir(runs_dir.parent.parent)
        rc = runs_main(["--log", "run-log"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "hello from agent" in out

    def test_log_missing_file(
        self,
        runs_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(runs_dir, "run-nolog")
        monkeypatch.chdir(runs_dir.parent.parent)
        rc = runs_main(["--log", "run-nolog"])
        assert rc == 0  # graceful — prints "no log" message
        out = capsys.readouterr().out
        assert "No output log" in out

    def test_log_unknown_run(
        self,
        runs_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(runs_dir.parent.parent)
        rc = runs_main(["--log", "ghost"])
        assert rc == 1


# ── Kill action ─────────────────────────────────────────────────────────


class TestRunKill:
    """``ralph runs --kill <id>`` sends SIGTERM to active runs."""

    def test_kill_not_running(
        self,
        runs_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _write_run(runs_dir, "run-done", status="done")
        monkeypatch.chdir(runs_dir.parent.parent)
        rc = runs_main(["--kill", "run-done"])
        assert rc == 1

    def test_kill_unknown_run(
        self,
        runs_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(runs_dir.parent.parent)
        rc = runs_main(["--kill", "ghost"])
        assert rc == 1


# ── Helper functions ────────────────────────────────────────────────────


class TestFmtDuration:
    """_fmt_duration formats seconds into human-readable strings."""

    def test_seconds_only(self) -> None:
        assert _fmt_duration(45) == "45s"

    def test_minutes_and_seconds(self) -> None:
        assert _fmt_duration(125) == "2m 5s"

    def test_zero(self) -> None:
        assert _fmt_duration(0) == "0s"
