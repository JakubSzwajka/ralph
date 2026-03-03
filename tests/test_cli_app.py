"""Tests for ralph.cli.app — entrypoint behavior and error paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ralph.cli.app import main


class TestMainMissingPrd:
    """Running without --prd returns exit 1 with actionable error."""

    def test_no_args_exits_1(self) -> None:
        rc = main([])
        assert rc == 1

    def test_no_args_prints_usage(self, capsys: pytest.CaptureFixture[str]) -> None:
        main([])
        captured = capsys.readouterr().out
        assert "--prd" in captured


class TestMainPrdNotFound:
    """Running with --prd pointing to a missing file exits 1."""

    def test_single_missing_file(self, tmp_path: Path) -> None:
        bogus = tmp_path / "nonexistent.md"
        rc = main(["--prd", str(bogus)])
        assert rc == 1

    def test_multiple_missing_files(self, tmp_path: Path) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        rc = main(["--prd", str(a), str(b)])
        assert rc == 1


class TestMainPrdExists:
    """Running with a valid --prd delegates to the runner."""

    def test_valid_prd_calls_run_sync(self, tmp_path: Path) -> None:
        prd = tmp_path / "test.md"
        prd.write_text("# Test PRD")
        with patch("ralph.cli.app._run_sync", return_value=0) as mock_run:
            rc = main(["--prd", str(prd)])
        assert rc == 0
        mock_run.assert_called_once()
        call_config = mock_run.call_args[0][0]
        assert call_config.prd == prd


class TestSubcommandDispatch:
    """``ralph runs`` dispatches to the runs subcommand."""

    def test_runs_subcommand_dispatches(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Use an empty runs dir so runs_main returns 0 quickly
        monkeypatch.chdir(tmp_path)
        rc = main(["runs"])
        assert rc == 0

    def test_unknown_first_arg_is_not_subcommand(self) -> None:
        """An unrecognised first arg should not be treated as a subcommand."""
        # 'bogus' is not in _SUBCOMMANDS, so it falls through to parse_args
        # which will fail on unrecognised arg (SystemExit).
        with pytest.raises(SystemExit):
            main(["bogus"])


class TestKeyboardInterrupt:
    """KeyboardInterrupt during the run returns 130."""

    def test_keyboard_interrupt_returns_130(self, tmp_path: Path) -> None:
        prd = tmp_path / "test.md"
        prd.write_text("# Test PRD")
        with patch("ralph.cli.app._run_sync", side_effect=KeyboardInterrupt):
            rc = main(["--prd", str(prd)])
        assert rc == 130
