"""Tests for ralph.cli.args — CLI argument parsing contract."""

from __future__ import annotations

from pathlib import Path

from ralph.cli.args import parse_args


# ── PRD argument validation ─────────────────────────────────────────────


class TestPrdArgument:
    """--prd flag parsing — success and failure paths."""

    def test_prd_explicit_returns_true(self, tmp_path: Path) -> None:
        prd = tmp_path / "test.md"
        prd.write_text("# Test PRD")
        config, prd_explicit = parse_args(["--prd", str(prd)])
        assert prd_explicit is True
        assert config.prd == prd

    def test_no_prd_returns_false(self) -> None:
        _config, prd_explicit = parse_args([])
        assert prd_explicit is False

    def test_multiple_prd_files(self, tmp_path: Path) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")
        config, prd_explicit = parse_args(["--prd", str(a), str(b)])
        assert prd_explicit is True
        # First file becomes config.prd, all become context_files
        assert config.prd == a
        assert config.context_files == [a, b]

    def test_glob_prd_pattern(self, tmp_path: Path) -> None:
        (tmp_path / "one.md").write_text("# 1")
        (tmp_path / "two.md").write_text("# 2")
        (tmp_path / "skip.txt").write_text("skip")
        config, prd_explicit = parse_args(
            ["--prd", str(tmp_path / "*.md")]
        )
        assert prd_explicit is True
        # Should match only .md files
        assert all(str(p).endswith(".md") for p in config.context_files or [config.prd])

    def test_nonexistent_prd_path_preserved(self, tmp_path: Path) -> None:
        """Parser accepts a path that doesn't exist — caller handles the error."""
        bogus = tmp_path / "nope.md"
        config, prd_explicit = parse_args(["--prd", str(bogus)])
        assert prd_explicit is True
        assert config.prd == bogus


# ── Config defaults and overrides ───────────────────────────────────────


class TestConfigOverrides:
    """CLI flags override config-file defaults."""

    def test_default_iterations(self) -> None:
        config, _ = parse_args([])
        assert config.iterations == 20

    def test_max_turns_overrides_iterations(self, tmp_path: Path) -> None:
        prd = tmp_path / "p.md"
        prd.write_text("# P")
        config, _ = parse_args(["--prd", str(prd), "--max-turns", "5"])
        assert config.iterations == 5

    def test_permission_mode_default(self) -> None:
        config, _ = parse_args([])
        assert config.permission_mode == "bypassPermissions"

    def test_permission_mode_override(self, tmp_path: Path) -> None:
        prd = tmp_path / "p.md"
        prd.write_text("# P")
        config, _ = parse_args(
            ["--prd", str(prd), "--permission-mode", "plan"]
        )
        assert config.permission_mode == "plan"

    def test_model_none_by_default(self) -> None:
        config, _ = parse_args([])
        assert config.model is None

    def test_model_override(self, tmp_path: Path) -> None:
        prd = tmp_path / "p.md"
        prd.write_text("# P")
        config, _ = parse_args(["--prd", str(prd), "--model", "opus"])
        assert config.model == "opus"
