from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ralph.cli import parse_args


def _make_config_file(tmp_path: Path, data: dict) -> Path:
    """Write a JSON config file to tmp_path and return its path."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(data))
    return config_file


def _parse_with_config(config_file: Path, extra_argv: list[str] | None = None) -> object:
    """Run parse_args with a patched CONFIG_PATH and return the RalphConfig."""
    argv = ["1", "--prd", "/dev/null"] + (extra_argv or [])
    with patch("ralph.cli.load_config") as mock_load:
        # Read from the real file so we test integration
        mock_load.return_value = json.loads(config_file.read_text())
        config, _prd_explicit, _prd_dir, _no_tui = parse_args(argv)
        return config


def _parse_full(config_file: Path, extra_argv: list[str] | None = None) -> tuple:
    """Run parse_args with a patched CONFIG_PATH and return the full 4-tuple."""
    argv = ["1", "--prd", "/dev/null"] + (extra_argv or [])
    with patch("ralph.cli.load_config") as mock_load:
        mock_load.return_value = json.loads(config_file.read_text())
        return parse_args(argv)


class TestDiscordWebhookPrecedence:
    """Tests for discord_webhook_url precedence: CLI > env var > config file."""

    def test_config_file_webhook_is_picked_up(self, tmp_path: Path) -> None:
        """discord_webhook_url from config file is used when no CLI flag or env var set."""
        config_file = _make_config_file(tmp_path, {"discord_webhook_url": "https://config.example.com"})
        config = _parse_with_config(config_file)
        assert config.discord_webhook_url == "https://config.example.com"

    def test_cli_flag_overrides_config_file(self, tmp_path: Path) -> None:
        """--discord-webhook CLI flag overrides config file value."""
        config_file = _make_config_file(tmp_path, {"discord_webhook_url": "https://config.example.com"})
        config = _parse_with_config(config_file, ["--discord-webhook", "https://cli.example.com"])
        assert config.discord_webhook_url == "https://cli.example.com"

    def test_env_var_overrides_config_file(self, tmp_path: Path) -> None:
        """RALPH_DISCORD_WEBHOOK env var overrides config file value."""
        config_file = _make_config_file(tmp_path, {"discord_webhook_url": "https://config.example.com"})
        with patch.dict(os.environ, {"RALPH_DISCORD_WEBHOOK": "https://env.example.com"}):
            config = _parse_with_config(config_file)
        assert config.discord_webhook_url == "https://env.example.com"

    def test_cli_flag_overrides_env_var(self, tmp_path: Path) -> None:
        """CLI flag takes priority over env var."""
        config_file = _make_config_file(tmp_path, {})
        with patch.dict(os.environ, {"RALPH_DISCORD_WEBHOOK": "https://env.example.com"}):
            config = _parse_with_config(config_file, ["--discord-webhook", "https://cli.example.com"])
        assert config.discord_webhook_url == "https://cli.example.com"

    def test_no_webhook_returns_none(self, tmp_path: Path) -> None:
        """When no webhook is set anywhere, discord_webhook_url is None."""
        config_file = _make_config_file(tmp_path, {})
        env = {k: v for k, v in os.environ.items() if k != "RALPH_DISCORD_WEBHOOK"}
        with patch.dict(os.environ, env, clear=True):
            config = _parse_with_config(config_file)
        assert config.discord_webhook_url is None


class TestDiscordIntervalPrecedence:
    """Tests for discord_min_interval precedence: CLI > config file > default."""

    def test_config_file_interval_is_used(self, tmp_path: Path) -> None:
        """discord_min_interval from config file is used when no CLI flag set."""
        config_file = _make_config_file(tmp_path, {"discord_min_interval": 30})
        config = _parse_with_config(config_file)
        assert config.discord_min_interval == 30.0

    def test_cli_flag_overrides_config_file_interval(self, tmp_path: Path) -> None:
        """--discord-interval CLI flag overrides config file value."""
        config_file = _make_config_file(tmp_path, {"discord_min_interval": 30})
        config = _parse_with_config(config_file, ["--discord-interval", "60"])
        assert config.discord_min_interval == 60.0

    def test_default_interval_when_no_config(self, tmp_path: Path) -> None:
        """Default interval 5.0 is used when neither CLI flag nor config file set."""
        config_file = _make_config_file(tmp_path, {})
        config = _parse_with_config(config_file)
        assert config.discord_min_interval == 5.0


class TestPrdDirectoryPrecedence:
    """Tests for prd_directory precedence: --prd-dir CLI flag > config file > None."""

    def test_no_config_returns_none(self, tmp_path: Path) -> None:
        """When neither --prd-dir nor config file key is set, prd_dir is None."""
        config_file = _make_config_file(tmp_path, {})
        _, _, prd_dir, _ = _parse_full(config_file)
        assert prd_dir is None

    def test_config_file_prd_directory_is_resolved(self, tmp_path: Path) -> None:
        """prd_directory from config file is resolved relative to --cwd."""
        config_file = _make_config_file(tmp_path, {"prd_directory": "custom/prds"})
        _, _, prd_dir, _ = _parse_full(config_file)
        # prd_dir should be cwd / custom/prds (cwd defaults to Path.cwd())
        assert prd_dir is not None
        assert prd_dir.parts[-2:] == ("custom", "prds")

    def test_cli_prd_dir_overrides_config_file(self, tmp_path: Path) -> None:
        """--prd-dir CLI flag overrides prd_directory from config file."""
        config_file = _make_config_file(tmp_path, {"prd_directory": "custom/prds"})
        _, _, prd_dir, _ = _parse_full(
            config_file, ["--prd-dir", str(tmp_path / "cli/prds")]
        )
        assert prd_dir == tmp_path / "cli" / "prds"

    def test_cli_prd_dir_absolute_path(self, tmp_path: Path) -> None:
        """--prd-dir with an absolute path is used as-is."""
        abs_path = tmp_path / "absolute" / "prds"
        config_file = _make_config_file(tmp_path, {})
        _, _, prd_dir, _ = _parse_full(config_file, ["--prd-dir", str(abs_path)])
        assert prd_dir == abs_path
