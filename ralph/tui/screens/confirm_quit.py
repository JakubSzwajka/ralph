from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmationScreen(ModalScreen[bool]):
    """Base confirmation dialog with title, body text, and confirm/cancel buttons."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    DEFAULT_CSS = """
    ConfirmationScreen, ConfirmRunScreen, ConfirmQuitScreen {
        align: center middle;
    }

    #confirm-dialog {
        width: 60;
        height: auto;
        max-height: 20;
        border: round $primary-background-lighten-2;
        border-title-color: $text-muted;
        border-title-align: center;
        background: $surface;
        padding: 1 2;
    }

    #confirm-body {
        width: 1fr;
        height: auto;
        padding: 1 0;
    }

    #confirm-buttons {
        height: 3;
        align: right middle;
    }

    #confirm-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(
        self,
        body: str,
        title: str = "Confirm",
        confirm_label: str = "OK",
        confirm_variant: str = "success",
        focus_confirm: bool = False,
    ) -> None:
        super().__init__()
        self._body = body
        self._title = title
        self._confirm_label = confirm_label
        self._confirm_variant = confirm_variant
        self._focus_confirm = focus_confirm

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self._body, id="confirm-body")
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button(
                    self._confirm_label,
                    id="ok-btn",
                    variant=self._confirm_variant,
                )

    def on_mount(self) -> None:
        self.query_one("#confirm-dialog").border_title = self._title
        if self._focus_confirm:
            self.query_one("#ok-btn", Button).focus()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#ok-btn")
    def _confirm(self) -> None:
        self.dismiss(True)


class ConfirmQuitScreen(ConfirmationScreen):
    def __init__(self, active_runs: int = 0) -> None:
        if active_runs > 0:
            body = (
                f"You have {active_runs} active run(s). "
                "Are you sure you want to quit?"
            )
        else:
            body = "Are you sure you want to quit?"
        super().__init__(
            body=body,
            title="Confirm Quit",
            confirm_label="Quit",
            confirm_variant="error",
            focus_confirm=True,
        )
