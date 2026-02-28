from __future__ import annotations

from ralph.core import RalphConfig
from ralph.tui.screens.confirm_quit import ConfirmationScreen


class ConfirmRunScreen(ConfirmationScreen):
    def __init__(self, config: RalphConfig) -> None:
        files_list = "\n".join(f"  • {f.name}" for f in config.context_files)
        body = (
            f"[bold]Files:[/bold]\n{files_list}\n\n"
            f"[bold]Iterations:[/bold] {config.iterations}\n"
            f"[bold]Working dir:[/bold] {config.cwd}"
        )
        super().__init__(
            body=body,
            title="Confirm Run",
            confirm_label="Run",
            confirm_variant="success",
        )
