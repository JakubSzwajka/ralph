from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmQuitScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    DEFAULT_CSS = """
    ConfirmQuitScreen {
        align: center middle;
    }

    #quit-dialog {
        width: 60;
        height: auto;
        border: round $primary-background-lighten-2;
        border-title-color: $text-muted;
        border-title-align: center;
        background: $surface;
        padding: 1 2;
    }

    #quit-body {
        width: 1fr;
        height: auto;
        padding: 1 0;
    }

    #quit-buttons {
        height: 3;
        align: right middle;
    }

    #quit-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, active_runs: int = 0) -> None:
        super().__init__()
        self._active_runs = active_runs

    def compose(self) -> ComposeResult:
        if self._active_runs > 0:
            body = (
                f"You have {self._active_runs} active run(s). "
                "Are you sure you want to quit?"
            )
        else:
            body = "Are you sure you want to quit?"
        with Vertical(id="quit-dialog"):
            yield Static(body, id="quit-body")
            with Horizontal(id="quit-buttons"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button("Quit", id="quit-btn", variant="error")

    def on_mount(self) -> None:
        self.query_one("#quit-dialog").border_title = "Confirm Quit"
        self.query_one("#quit-btn", Button).focus()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#quit-btn")
    def _confirm(self) -> None:
        self.dismiss(True)
