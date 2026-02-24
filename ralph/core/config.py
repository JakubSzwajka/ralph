"""RalphConfig — all settings for a single agent run."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import PermissionMode


@dataclass
class RalphConfig:
    prd: Path = Path("PRD.md")
    tasks: Path | None = None
    iterations: int = 10
    cwd: Path = field(default_factory=Path.cwd)
    permission_mode: PermissionMode = "bypassPermissions"
    model: str | None = None
    max_turns: int | None = None
    discord_webhook_url: str | None = None
    discord_notify: bool = False
    discord_min_interval: float = 5.0

    def __post_init__(self) -> None:
        if self.discord_webhook_url is not None and not self.discord_notify:
            self.discord_notify = True
