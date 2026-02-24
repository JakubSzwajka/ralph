"""Tests for the ``ralph runs`` CLI subcommand."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ralph.cli import _cmd_runs, _show_run_detail, main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_meta(
    tmp_path: Path,
    run_id: str,
    *,
    prd: str = "docs/prds/my-prd/README.md",
    iterations_completed: int | None = None,
    total_cost_usd: float | None = None,
    total_duration_s: float | None = None,
    status: str | None = None,
) -> Path:
    """Write a meta.json for a fake run and return the run directory."""
    run_dir = tmp_path / ".ralph" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta: dict = {
        "run_id": run_id,
        "started_at": "2026-02-24T10:00:00+00:00",
        "prd": prd,
        "tasks": None,
        "iterations_requested": 5,
        "model": "claude-test",
        "permission_mode": "bypassPermissions",
    }
    if iterations_completed is not None:
        meta["iterations_completed"] = iterations_completed
    if total_cost_usd is not None:
        meta["total_cost_usd"] = total_cost_usd
    if total_duration_s is not None:
        meta["total_duration_s"] = total_duration_s
    if status is not None:
        meta["completed_at"] = "2026-02-24T10:05:00+00:00"
        meta["status"] = status

    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    return run_dir


# ---------------------------------------------------------------------------
# _cmd_runs — no runs directory
# ---------------------------------------------------------------------------


class TestCmdRunsNoDirectory:
    def test_returns_zero_when_no_runs_dir(self, tmp_path: Path) -> None:
        result = _cmd_runs(["--cwd", str(tmp_path)])
        assert result == 0

    def test_prints_message_when_no_runs_dir(self, tmp_path: Path, capsys) -> None:
        with patch("ralph.cli.console") as mock_console:
            _cmd_runs(["--cwd", str(tmp_path)])
        # Console.print was called at least once
        mock_console.print.assert_called_once()
        msg = mock_console.print.call_args[0][0]
        assert "No runs found" in msg


# ---------------------------------------------------------------------------
# _cmd_runs — empty runs directory
# ---------------------------------------------------------------------------


class TestCmdRunsEmptyDirectory:
    def test_returns_zero_with_empty_runs_dir(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / ".ralph" / "runs"
        runs_dir.mkdir(parents=True)
        result = _cmd_runs(["--cwd", str(tmp_path)])
        assert result == 0

    def test_prints_no_runs_message_when_empty(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / ".ralph" / "runs"
        runs_dir.mkdir(parents=True)
        with patch("ralph.cli.console") as mock_console:
            _cmd_runs(["--cwd", str(tmp_path)])
        mock_console.print.assert_called_once()
        msg = mock_console.print.call_args[0][0]
        assert "No runs found" in msg


# ---------------------------------------------------------------------------
# _cmd_runs — single complete run
# ---------------------------------------------------------------------------


class TestCmdRunsSingleRun:
    def test_returns_zero_with_one_run(self, tmp_path: Path) -> None:
        _make_meta(
            tmp_path,
            "2026-02-24T10-00-00",
            iterations_completed=3,
            total_cost_usd=0.0123,
            total_duration_s=45.0,
            status="complete",
        )
        result = _cmd_runs(["--cwd", str(tmp_path)])
        assert result == 0

    def test_prints_table_for_one_run(self, tmp_path: Path) -> None:
        _make_meta(
            tmp_path,
            "2026-02-24T10-00-00",
            prd="docs/prds/run-history/README.md",
            iterations_completed=3,
            total_cost_usd=0.0123,
            total_duration_s=45.0,
            status="complete",
        )
        with patch("ralph.cli.console") as mock_console:
            _cmd_runs(["--cwd", str(tmp_path)])
        # console.print should be called with the table
        mock_console.print.assert_called_once()


# ---------------------------------------------------------------------------
# _cmd_runs — PRD name extraction
# ---------------------------------------------------------------------------


class TestPrdNameExtraction:
    def test_extracts_parent_dir_name_from_readme_path(self, tmp_path: Path) -> None:
        """prd path like 'docs/prds/run-history/README.md' → 'run-history'."""
        _make_meta(
            tmp_path,
            "2026-02-24T10-00-00",
            prd="docs/prds/run-history/README.md",
            status="complete",
            iterations_completed=1,
            total_cost_usd=0.0,
            total_duration_s=1.0,
        )
        # Capture table rows via a spy on Table.add_row
        from rich.table import Table
        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _cmd_runs(["--cwd", str(tmp_path)])

        # First call to add_row is the data row (run ID, PRD name, ...)
        assert len(rows_added) >= 1
        assert rows_added[0][1] == "run-history"

    def test_falls_back_to_filename_for_flat_prd_path(self, tmp_path: Path) -> None:
        """prd path like 'PRD.md' (parent is '.') → uses filename 'PRD.md'."""
        _make_meta(
            tmp_path,
            "2026-02-24T10-00-00",
            prd="PRD.md",
            status="complete",
            iterations_completed=1,
            total_cost_usd=0.0,
            total_duration_s=1.0,
        )
        from rich.table import Table
        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _cmd_runs(["--cwd", str(tmp_path)])

        assert len(rows_added) >= 1
        assert rows_added[0][1] == "PRD.md"


# ---------------------------------------------------------------------------
# _cmd_runs — sorting (most recent first)
# ---------------------------------------------------------------------------


class TestCmdRunsSorting:
    def test_most_recent_run_appears_first(self, tmp_path: Path) -> None:
        """Runs are sorted by run_id descending (most recent timestamp first)."""
        _make_meta(
            tmp_path,
            "2026-02-24T08-00-00",
            status="complete",
            iterations_completed=1,
            total_cost_usd=0.01,
            total_duration_s=10.0,
        )
        _make_meta(
            tmp_path,
            "2026-02-24T12-00-00",
            status="complete",
            iterations_completed=2,
            total_cost_usd=0.02,
            total_duration_s=20.0,
        )
        _make_meta(
            tmp_path,
            "2026-02-24T10-00-00",
            status="complete",
            iterations_completed=3,
            total_cost_usd=0.03,
            total_duration_s=30.0,
        )

        from rich.table import Table
        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _cmd_runs(["--cwd", str(tmp_path)])

        # Extract run IDs from rows (first column)
        run_ids = [row[0] for row in rows_added]
        assert run_ids == [
            "2026-02-24T12-00-00",
            "2026-02-24T10-00-00",
            "2026-02-24T08-00-00",
        ]


# ---------------------------------------------------------------------------
# _cmd_runs — in-progress run (missing completed_at fields)
# ---------------------------------------------------------------------------


class TestCmdRunsInProgress:
    def test_in_progress_run_shows_dashes_for_missing_fields(self, tmp_path: Path) -> None:
        """A run without completion data shows '—' for cost/duration/iterations."""
        _make_meta(
            tmp_path,
            "2026-02-24T10-00-00",
            # No iterations_completed, total_cost_usd, total_duration_s, or status
        )
        from rich.table import Table
        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _cmd_runs(["--cwd", str(tmp_path)])

        assert len(rows_added) >= 1
        row = rows_added[0]
        # iterations, cost, duration should be "—"
        assert row[2] == "—"  # iterations
        assert row[3] == "—"  # cost
        assert row[4] == "—"  # duration


# ---------------------------------------------------------------------------
# _cmd_runs — status styling
# ---------------------------------------------------------------------------


class TestCmdRunsStatusStyling:
    def _get_status_cell(self, tmp_path: Path, run_id: str) -> str:
        from rich.table import Table
        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _cmd_runs(["--cwd", str(tmp_path)])

        return rows_added[0][5]  # status column

    def test_complete_status_has_green_markup(self, tmp_path: Path) -> None:
        _make_meta(
            tmp_path,
            "2026-02-24T10-00-00",
            status="complete",
            iterations_completed=1,
            total_cost_usd=0.0,
            total_duration_s=1.0,
        )
        status_cell = self._get_status_cell(tmp_path, "2026-02-24T10-00-00")
        assert "green" in status_cell
        assert "complete" in status_cell

    def test_max_iterations_status_has_yellow_markup(self, tmp_path: Path) -> None:
        _make_meta(
            tmp_path,
            "2026-02-24T10-00-00",
            status="max-iterations",
            iterations_completed=5,
            total_cost_usd=0.1,
            total_duration_s=100.0,
        )
        status_cell = self._get_status_cell(tmp_path, "2026-02-24T10-00-00")
        assert "yellow" in status_cell
        assert "max-iterations" in status_cell

    def test_error_status_has_red_markup(self, tmp_path: Path) -> None:
        _make_meta(
            tmp_path,
            "2026-02-24T10-00-00",
            status="error",
            iterations_completed=0,
            total_cost_usd=0.0,
            total_duration_s=0.0,
        )
        status_cell = self._get_status_cell(tmp_path, "2026-02-24T10-00-00")
        assert "red" in status_cell
        assert "error" in status_cell


# ---------------------------------------------------------------------------
# _cmd_runs — skips directories without meta.json
# ---------------------------------------------------------------------------


class TestCmdRunsCorruptData:
    def test_skips_run_dir_without_meta_json(self, tmp_path: Path) -> None:
        # Create a directory without meta.json
        (tmp_path / ".ralph" / "runs" / "2026-02-24T10-00-00").mkdir(parents=True)
        # And one valid run
        _make_meta(
            tmp_path,
            "2026-02-24T11-00-00",
            status="complete",
            iterations_completed=1,
            total_cost_usd=0.01,
            total_duration_s=5.0,
        )
        from rich.table import Table
        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _cmd_runs(["--cwd", str(tmp_path)])

        # Only one row for the valid run
        assert len(rows_added) == 1
        assert rows_added[0][0] == "2026-02-24T11-00-00"

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        # Create a run with invalid meta.json
        bad_run_dir = tmp_path / ".ralph" / "runs" / "2026-02-24T09-00-00"
        bad_run_dir.mkdir(parents=True)
        (bad_run_dir / "meta.json").write_text("not valid json {{{")
        # And one valid run
        _make_meta(
            tmp_path,
            "2026-02-24T11-00-00",
            status="complete",
            iterations_completed=1,
            total_cost_usd=0.01,
            total_duration_s=5.0,
        )
        from rich.table import Table
        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _cmd_runs(["--cwd", str(tmp_path)])

        # Only one row for the valid run
        assert len(rows_added) == 1


# ---------------------------------------------------------------------------
# main() — dispatch to _cmd_runs
# ---------------------------------------------------------------------------


class TestMainDispatchesRuns:
    def test_main_with_runs_arg_calls_cmd_runs(self, tmp_path: Path) -> None:
        """main(['runs', '--cwd', ...]) dispatches to _cmd_runs without error."""
        result = main(["runs", "--cwd", str(tmp_path)])
        assert result == 0

    def test_main_runs_does_not_require_iterations(self, tmp_path: Path) -> None:
        """'ralph runs' should not require the positional iterations argument."""
        # This should not raise a SystemExit from argparse
        result = main(["runs", "--cwd", str(tmp_path)])
        assert result == 0


# ---------------------------------------------------------------------------
# Helpers for detail-view tests
# ---------------------------------------------------------------------------


def _make_iteration_jsonl(run_dir: Path, iteration: int, events: list[dict]) -> Path:
    """Write a fake iteration JSONL file and return its path."""
    jsonl_path = run_dir / f"iteration-{iteration:02d}.jsonl"
    lines = "\n".join(json.dumps(e) for e in events)
    jsonl_path.write_text(lines + "\n", encoding="utf-8")
    return jsonl_path


# ---------------------------------------------------------------------------
# _show_run_detail — error cases
# ---------------------------------------------------------------------------


class TestShowRunDetailErrors:
    def test_returns_one_for_nonexistent_run(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / ".ralph" / "runs"
        runs_dir.mkdir(parents=True)
        with patch("ralph.cli.console") as mock_console:
            result = _show_run_detail(runs_dir, "nonexistent-id", None)
        assert result == 1
        msg = mock_console.print.call_args[0][0]
        assert "not found" in msg.lower() or "Error" in msg

    def test_returns_one_for_missing_meta_json(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / ".ralph" / "runs"
        run_dir = runs_dir / "2026-02-24T10-00-00"
        run_dir.mkdir(parents=True)
        # No meta.json created
        with patch("ralph.cli.console") as mock_console:
            result = _show_run_detail(runs_dir, "2026-02-24T10-00-00", None)
        assert result == 1

    def test_returns_one_for_corrupt_meta_json(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / ".ralph" / "runs"
        run_dir = runs_dir / "2026-02-24T10-00-00"
        run_dir.mkdir(parents=True)
        (run_dir / "meta.json").write_text("not valid json {{{")
        with patch("ralph.cli.console") as mock_console:
            result = _show_run_detail(runs_dir, "2026-02-24T10-00-00", None)
        assert result == 1


# ---------------------------------------------------------------------------
# _show_run_detail — success: config panel
# ---------------------------------------------------------------------------


class TestShowRunDetailPanel:
    def _setup_run(self, tmp_path: Path, run_id: str) -> Path:
        """Create a minimal run directory and return it."""
        run_dir = _make_meta(
            tmp_path,
            run_id,
            prd="docs/prds/my-prd/README.md",
            iterations_completed=2,
            total_cost_usd=0.05,
            total_duration_s=12.3,
            status="complete",
        )
        return run_dir

    def test_returns_zero_for_valid_run(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        self._setup_run(tmp_path, run_id)
        runs_dir = tmp_path / ".ralph" / "runs"
        result = _show_run_detail(runs_dir, run_id, None)
        assert result == 0

    def test_console_print_called_for_valid_run(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        self._setup_run(tmp_path, run_id)
        runs_dir = tmp_path / ".ralph" / "runs"
        with patch("ralph.cli.console") as mock_console:
            _show_run_detail(runs_dir, run_id, None)
        assert mock_console.print.call_count >= 1

    def test_panel_contains_run_id(self, tmp_path: Path) -> None:
        """The config panel should include the run ID string."""
        run_id = "2026-02-24T10-00-00"
        self._setup_run(tmp_path, run_id)
        runs_dir = tmp_path / ".ralph" / "runs"
        from rich.panel import Panel as RichPanel

        panels_printed: list = []
        original_print = None

        def capture_print(*args, **kwargs):
            for arg in args:
                if isinstance(arg, RichPanel):
                    panels_printed.append(arg)

        with patch("ralph.cli.console") as mock_console:
            mock_console.print.side_effect = capture_print
            _show_run_detail(runs_dir, run_id, None)

        # At least one panel should have been printed
        assert panels_printed, "Expected at least one Rich Panel to be printed"
        # The first panel's renderable should contain the run_id
        first_panel = panels_printed[0]
        assert run_id in str(first_panel.title) or run_id in str(first_panel.renderable)


# ---------------------------------------------------------------------------
# _show_run_detail — iterations table
# ---------------------------------------------------------------------------


class TestShowRunDetailIterationsTable:
    def test_no_iteration_files_prints_no_files_message(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        _make_meta(tmp_path, run_id, status="complete", iterations_completed=0,
                   total_cost_usd=0.0, total_duration_s=0.0)
        runs_dir = tmp_path / ".ralph" / "runs"
        with patch("ralph.cli.console") as mock_console:
            result = _show_run_detail(runs_dir, run_id, None)
        assert result == 0
        # Should print the panel + the "no iteration files" message
        assert mock_console.print.call_count >= 2

    def test_iteration_table_has_row_per_jsonl_file(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        run_dir = _make_meta(tmp_path, run_id, status="complete", iterations_completed=2,
                             total_cost_usd=0.05, total_duration_s=10.0)
        # Create two iteration files
        _make_iteration_jsonl(run_dir, 1, [
            {"type": "text", "text": "hello", "timestamp": "2026-02-24T10:00:00+00:00"},
            {"type": "text", "text": "world", "timestamp": "2026-02-24T10:00:05+00:00"},
        ])
        _make_iteration_jsonl(run_dir, 2, [
            {"type": "text", "text": "again", "timestamp": "2026-02-24T10:01:00+00:00"},
        ])

        runs_dir = tmp_path / ".ralph" / "runs"
        from rich.table import Table

        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _show_run_detail(runs_dir, run_id, None)

        # Two data rows (one per iteration file)
        assert len(rows_added) == 2
        # First column is iteration number
        assert rows_added[0][0] == "1"
        assert rows_added[1][0] == "2"

    def test_event_count_in_table(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        run_dir = _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                             total_cost_usd=0.01, total_duration_s=5.0)
        _make_iteration_jsonl(run_dir, 1, [
            {"type": "text", "text": "a", "timestamp": "2026-02-24T10:00:00+00:00"},
            {"type": "text", "text": "b", "timestamp": "2026-02-24T10:00:01+00:00"},
            {"type": "text", "text": "c", "timestamp": "2026-02-24T10:00:02+00:00"},
        ])

        runs_dir = tmp_path / ".ralph" / "runs"
        from rich.table import Table

        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _show_run_detail(runs_dir, run_id, None)

        assert len(rows_added) == 1
        # Third column (index 2) is event count
        assert rows_added[0][2] == "3"

    def test_tool_calls_shown_in_table(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        run_dir = _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                             total_cost_usd=0.01, total_duration_s=5.0)
        _make_iteration_jsonl(run_dir, 1, [
            {"type": "text", "text": "hi", "timestamp": "2026-02-24T10:00:00+00:00"},
            {"type": "tool_use", "name": "Bash", "input": "ls", "timestamp": "2026-02-24T10:00:01+00:00"},
            {"type": "tool_use", "name": "Bash", "input": "pwd", "timestamp": "2026-02-24T10:00:02+00:00"},
            {"type": "tool_use", "name": "Read", "input": "file.txt", "timestamp": "2026-02-24T10:00:03+00:00"},
        ])

        runs_dir = tmp_path / ".ralph" / "runs"
        from rich.table import Table

        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _show_run_detail(runs_dir, run_id, None)

        tool_col = rows_added[0][3]
        # Bash was called twice, Read once
        assert "Bash" in tool_col
        assert "Read" in tool_col
        assert "×2" in tool_col

    def test_no_tool_calls_shows_dash(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        run_dir = _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                             total_cost_usd=0.0, total_duration_s=1.0)
        _make_iteration_jsonl(run_dir, 1, [
            {"type": "text", "text": "just text", "timestamp": "2026-02-24T10:00:00+00:00"},
        ])

        runs_dir = tmp_path / ".ralph" / "runs"
        from rich.table import Table

        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _show_run_detail(runs_dir, run_id, None)

        assert rows_added[0][3] == "—"

    def test_duration_computed_from_timestamps(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        run_dir = _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                             total_cost_usd=0.0, total_duration_s=10.0)
        # 10-second gap between first and last event
        _make_iteration_jsonl(run_dir, 1, [
            {"type": "text", "text": "start", "timestamp": "2026-02-24T10:00:00+00:00"},
            {"type": "text", "text": "end", "timestamp": "2026-02-24T10:00:10+00:00"},
        ])

        runs_dir = tmp_path / ".ralph" / "runs"
        from rich.table import Table

        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _show_run_detail(runs_dir, run_id, None)

        # Duration column (index 1) should be "10.0s"
        assert rows_added[0][1] == "10.0s"

    def test_single_event_shows_dash_for_duration(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        run_dir = _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                             total_cost_usd=0.0, total_duration_s=0.0)
        _make_iteration_jsonl(run_dir, 1, [
            {"type": "text", "text": "only one event", "timestamp": "2026-02-24T10:00:00+00:00"},
        ])

        runs_dir = tmp_path / ".ralph" / "runs"
        from rich.table import Table

        rows_added: list[tuple] = []
        original_add_row = Table.add_row

        def spy_add_row(self, *args, **kwargs):
            rows_added.append(args)
            return original_add_row(self, *args, **kwargs)

        with patch.object(Table, "add_row", spy_add_row):
            _show_run_detail(runs_dir, run_id, None)

        assert rows_added[0][1] == "—"


# ---------------------------------------------------------------------------
# ralph runs <id> via _cmd_runs
# ---------------------------------------------------------------------------


class TestCmdRunsWithRunId:
    def test_cmd_runs_with_id_dispatches_to_detail(self, tmp_path: Path) -> None:
        """_cmd_runs(['<id>', '--cwd', ...]) dispatches to _show_run_detail."""
        run_id = "2026-02-24T10-00-00"
        _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                   total_cost_usd=0.01, total_duration_s=5.0)
        result = _cmd_runs([run_id, "--cwd", str(tmp_path)])
        assert result == 0

    def test_cmd_runs_with_nonexistent_id_returns_one(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / ".ralph" / "runs"
        runs_dir.mkdir(parents=True)
        result = _cmd_runs(["nonexistent-id", "--cwd", str(tmp_path)])
        assert result == 1

    def test_main_runs_with_id_dispatches(self, tmp_path: Path) -> None:
        """main(['runs', '<id>', '--cwd', ...]) works end-to-end."""
        run_id = "2026-02-24T10-00-00"
        _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                   total_cost_usd=0.01, total_duration_s=5.0)
        result = main(["runs", run_id, "--cwd", str(tmp_path)])
        assert result == 0


# ---------------------------------------------------------------------------
# ralph runs <id> --iteration N
# ---------------------------------------------------------------------------


class TestIterationTextOutput:
    def test_returns_zero_for_existing_iteration(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        run_dir = _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                             total_cost_usd=0.0, total_duration_s=1.0)
        _make_iteration_jsonl(run_dir, 1, [
            {"type": "text", "text": "hello world", "timestamp": "2026-02-24T10:00:00+00:00"},
        ])
        runs_dir = tmp_path / ".ralph" / "runs"
        result = _cmd_runs([run_id, "--cwd", str(tmp_path), "--iteration", "1"])
        assert result == 0

    def test_returns_one_for_missing_iteration(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                   total_cost_usd=0.0, total_duration_s=1.0)
        # No iteration JSONL created
        result = _cmd_runs([run_id, "--cwd", str(tmp_path), "--iteration", "99"])
        assert result == 1

    def test_prints_text_content_from_iteration(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        run_dir = _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                             total_cost_usd=0.0, total_duration_s=1.0)
        _make_iteration_jsonl(run_dir, 3, [
            {"type": "text", "text": "first chunk ", "timestamp": "2026-02-24T10:00:00+00:00"},
            {"type": "text", "text": "second chunk", "timestamp": "2026-02-24T10:00:01+00:00"},
            # Non-text events should be ignored
            {"type": "tool_use", "name": "Bash", "input": "ls", "timestamp": "2026-02-24T10:00:02+00:00"},
        ])
        from rich.panel import Panel as RichPanel

        panels_printed: list = []

        def capture_print(*args, **kwargs):
            for arg in args:
                if isinstance(arg, RichPanel):
                    panels_printed.append(arg)

        with patch("ralph.cli.console") as mock_console:
            mock_console.print.side_effect = capture_print
            _cmd_runs([run_id, "--cwd", str(tmp_path), "--iteration", "3"])

        # A panel should have been printed with the concatenated text
        assert panels_printed, "Expected a Rich Panel to be printed"
        panel_text = str(panels_printed[0].renderable)
        assert "first chunk " in panel_text
        assert "second chunk" in panel_text

    def test_prints_message_when_no_text_events(self, tmp_path: Path) -> None:
        run_id = "2026-02-24T10-00-00"
        run_dir = _make_meta(tmp_path, run_id, status="complete", iterations_completed=1,
                             total_cost_usd=0.0, total_duration_s=1.0)
        # Only tool_use events, no text
        _make_iteration_jsonl(run_dir, 1, [
            {"type": "tool_use", "name": "Bash", "input": "ls", "timestamp": "2026-02-24T10:00:00+00:00"},
        ])
        with patch("ralph.cli.console") as mock_console:
            result = _cmd_runs([run_id, "--cwd", str(tmp_path), "--iteration", "1"])
        assert result == 0
        msg = mock_console.print.call_args[0][0]
        assert "No text output" in msg
