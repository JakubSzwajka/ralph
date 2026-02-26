from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Sends notifications to a Discord channel via webhook after each agent loop iteration."""

    def __init__(self, webhook_url: str, min_interval: float = 5.0) -> None:
        """
        Args:
            webhook_url: Discord webhook URL to POST messages to.
            min_interval: Minimum seconds between sends to avoid rate limiting.
        """
        self.webhook_url = webhook_url
        self.min_interval = min_interval
        self._last_sent: float = 0.0

    def format_message(
        self,
        iteration: int,
        summary: str,
        duration_s: float,
        is_complete: bool,
    ) -> str:
        """Format the notification message as plain Discord text."""
        status = "✅ COMPLETE" if is_complete else "🔄 in progress"
        # Truncate summary to avoid overly long Discord messages
        truncated = summary[:200] + "..." if len(summary) > 200 else summary
        lines = [
            f"**ralph** — iteration {iteration}",
            f"status: {status}  |  duration: {duration_s:.1f}s",
        ]
        if truncated:
            lines.append(f"```\n{truncated}\n```")
        return "\n".join(lines)

    async def send(
        self,
        iteration: int,
        summary: str,
        duration_s: float,
        is_complete: bool,
    ) -> None:
        """Send a notification to Discord. Never raises; logs warnings on failure."""
        now = time.monotonic()
        elapsed = now - self._last_sent
        if elapsed < self.min_interval:
            logger.debug(
                "Skipping Discord notification: only %.1fs elapsed (min %.1fs)",
                elapsed,
                self.min_interval,
            )
            return

        content = self.format_message(iteration, summary, duration_s, is_complete)
        payload: dict[str, Any] = {"content": content}

        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                response.raise_for_status()
            self._last_sent = time.monotonic()
        except Exception as exc:
            logger.warning("Discord notification failed: %s", exc)
