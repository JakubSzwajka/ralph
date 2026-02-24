"""Tests for RalphConfig."""
from pathlib import Path

from ralph.core import RalphConfig


class TestRalphConfig:
    def test_defaults(self) -> None:
        config = RalphConfig()
        assert config.prd == Path("PRD.md")
        assert config.tasks is None
        assert config.iterations == 10
        assert config.permission_mode == "bypassPermissions"
        assert config.model is None

    def test_discord_auto_enabled(self) -> None:
        config = RalphConfig(discord_webhook_url="https://example.com/hook")
        assert config.discord_notify is True

    def test_discord_not_enabled_without_url(self) -> None:
        config = RalphConfig()
        assert config.discord_notify is False
