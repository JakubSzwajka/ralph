from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App

from ralph.core import RalphConfig
from ralph.tui.css import TCSS
from ralph.tui.screens.browser_screen import BrowserScreen


class RalphApp(App[None]):
    TITLE = "ralph"
    SUB_TITLE = ""
    CSS = TCSS

    def __init__(
        self,
        config: RalphConfig | None = None,
        prd_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config or RalphConfig()
        self._prd_dir = prd_dir

    def on_mount(self) -> None:
        self.push_screen(BrowserScreen(self._config, self._prd_dir))
