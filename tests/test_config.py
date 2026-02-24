from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ralph.config import load_config, CONFIG_PATH


def test_load_config_missing_file_returns_empty_dict(tmp_path: Path) -> None:
    """Calling the loader with no config file returns {}."""
    nonexistent = tmp_path / "no_such_dir" / "config.json"
    with patch("ralph.config.CONFIG_PATH", nonexistent):
        result = load_config()
    assert result == {}


def test_load_config_missing_directory_returns_empty_dict(tmp_path: Path) -> None:
    """Missing ~/.ralph/ directory is silently ignored."""
    nonexistent = tmp_path / "missing_dir" / "config.json"
    with patch("ralph.config.CONFIG_PATH", nonexistent):
        result = load_config()
    assert result == {}


def test_load_config_valid_json_returns_parsed_dict(tmp_path: Path) -> None:
    """Calling the loader with a valid JSON file returns the parsed dict."""
    config_file = tmp_path / "config.json"
    data = {"discord_webhook_url": "https://discord.example.com/webhook", "discord_min_interval": 10}
    config_file.write_text(json.dumps(data))

    with patch("ralph.config.CONFIG_PATH", config_file):
        result = load_config()

    assert result == data


def test_load_config_empty_json_object(tmp_path: Path) -> None:
    """An empty JSON object {} is valid and returns {}."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")

    with patch("ralph.config.CONFIG_PATH", config_file):
        result = load_config()

    assert result == {}


def test_config_path_constant() -> None:
    """CONFIG_PATH points to ~/.ralph/config.json."""
    expected = Path.home() / ".ralph" / "config.json"
    assert CONFIG_PATH == expected


def test_load_config_invalid_json_exits_with_error(tmp_path: Path, capsys) -> None:
    """A config file with invalid JSON prints an error and exits with code 1."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{not valid json}")

    with patch("ralph.config.CONFIG_PATH", config_file):
        with pytest.raises(SystemExit) as exc_info:
            load_config()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "invalid JSON" in captured.err
    assert str(config_file) in captured.err


def test_load_config_unknown_keys_are_ignored(tmp_path: Path) -> None:
    """A config file with unknown keys loads without error and the unknown key is dropped."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"foo": "bar", "discord_webhook_url": "https://example.com"}))

    with patch("ralph.config.CONFIG_PATH", config_file):
        result = load_config()

    assert "foo" not in result
    assert result["discord_webhook_url"] == "https://example.com"


def test_load_config_only_unknown_keys_returns_empty_dict(tmp_path: Path) -> None:
    """Config with only unknown keys returns an empty dict."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"foo": "bar", "baz": 42}))

    with patch("ralph.config.CONFIG_PATH", config_file):
        result = load_config()

    assert result == {}
