from __future__ import annotations

import asyncio
import sys

from .args import parse_args
from .headless import _run_headless, console


def main(argv: list[str] | None = None) -> int:
    config, prd_explicit, prd_dir, no_tui_flag = parse_args(argv)

    # Auto-enable headless mode when stdout is not a TTY (piped output, CI, etc.)
    no_tui: bool = no_tui_flag or not sys.stdout.isatty()

    if no_tui:
        # -- Headless mode --
        if not prd_explicit:
            console.print(
                "[red]Error:[/red] --prd is required in headless mode (--no-tui or piped output)"
            )
            return 1

        if not config.prd.exists():
            console.print(f"[red]Error:[/red] PRD file not found: {config.prd}")
            return 1

        try:
            return asyncio.run(_run_headless(config))
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Stopping ralph.[/yellow]")
            return 130

    else:
        # -- TUI mode (default) --
        from ralph.tui import RalphApp

        if prd_explicit and not config.prd.exists():
            console.print(f"[red]Error:[/red] PRD file not found: {config.prd}")
            return 1

        RalphApp(config, prd_dir=prd_dir).run()
        return 0
