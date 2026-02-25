import json
from pathlib import Path

from ralph.traces.reader import RunSummary, list_runs


def _write_meta(runs_dir: Path, run_id: str, **overrides) -> None:
    d = runs_dir / run_id
    d.mkdir(parents=True)
    meta = {
        "run_id": run_id,
        "started_at": f"2026-01-01T{run_id}:00:00+00:00",
        "completed_at": f"2026-01-01T{run_id}:05:00+00:00",
        "status": "completed",
        "iterations_requested": 5,
        "iterations_completed": 5,
        "total_duration_s": 300.0,
        "model": None,
        **overrides,
    }
    (d / "meta.json").write_text(json.dumps(meta))


def test_list_runs_returns_sorted_descending(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".ralph" / "runs"
    _write_meta(runs_dir, "10-00-00", started_at="2026-01-01T10:00:00+00:00")
    _write_meta(runs_dir, "12-00-00", started_at="2026-01-01T12:00:00+00:00")
    _write_meta(runs_dir, "11-00-00", started_at="2026-01-01T11:00:00+00:00")

    result = list_runs(tmp_path)

    assert len(result) == 3
    assert result[0].run_id == "12-00-00"
    assert result[1].run_id == "11-00-00"
    assert result[2].run_id == "10-00-00"


def test_list_runs_skips_corrupt_json(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".ralph" / "runs"
    _write_meta(runs_dir, "good", started_at="2026-01-01T10:00:00+00:00")
    bad_dir = runs_dir / "bad"
    bad_dir.mkdir()
    (bad_dir / "meta.json").write_text("not json")

    result = list_runs(tmp_path)
    assert len(result) == 1
    assert result[0].run_id == "good"


def test_list_runs_skips_missing_meta(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".ralph" / "runs"
    _write_meta(runs_dir, "good", started_at="2026-01-01T10:00:00+00:00")
    (runs_dir / "empty").mkdir()

    result = list_runs(tmp_path)
    assert len(result) == 1


def test_list_runs_empty_dir(tmp_path: Path) -> None:
    (tmp_path / ".ralph" / "runs").mkdir(parents=True)
    assert list_runs(tmp_path) == []


def test_list_runs_no_runs_dir(tmp_path: Path) -> None:
    assert list_runs(tmp_path) == []


def test_list_runs_parses_all_fields(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".ralph" / "runs"
    _write_meta(
        runs_dir,
        "full",
        started_at="2026-01-01T10:00:00+00:00",
        completed_at="2026-01-01T10:05:00+00:00",
        status="max-iterations",
        iterations_requested=10,
        iterations_completed=3,
        total_duration_s=120.5,
        context_files=["a.md", "b.md"],
        model="opus",
    )

    result = list_runs(tmp_path)
    assert len(result) == 1
    s = result[0]
    assert isinstance(s, RunSummary)
    assert s.status == "max-iterations"
    assert s.iterations_requested == 10
    assert s.iterations_completed == 3
    assert s.total_duration_s == 120.5
    assert s.context_files == ["a.md", "b.md"]
    assert s.model == "opus"


def test_list_runs_skips_missing_run_id(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".ralph" / "runs"
    bad_dir = runs_dir / "no-id"
    bad_dir.mkdir(parents=True)
    (bad_dir / "meta.json").write_text(json.dumps({"started_at": "2026-01-01T10:00:00+00:00"}))

    assert list_runs(tmp_path) == []
