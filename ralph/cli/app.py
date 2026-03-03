"""CLI entry point — validates inputs and runs the agent loop.

There is intentionally no TUI or interactive-browser branch. All
invocations land in the same execution path regardless of whether the
terminal is a TTY or a pipe.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from ralph.core import RalphConfig
from .args import parse_args
from .headless import _run_cli, console


def _run_sync(config: RalphConfig) -> int:
    """Run the agent loop synchronously, cleaning up the event loop on exit."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run_cli(config))
    finally:
        try:
            _cancel_remaining(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            asyncio.set_event_loop(None)
            loop.close()


def _cancel_remaining(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel remaining tasks, suppressing anyio cancel-scope RuntimeErrors."""
    tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))


def _collect_missing_prd_files(config: RalphConfig) -> list[Path]:
    prd_files = config.context_files if config.context_files else [config.prd]
    return [p for p in prd_files if not p.exists() or not p.is_file()]


def main(argv: list[str] | None = None) -> int:
    config, prd_explicit = parse_args(argv)

    if not prd_explicit:
        console.print(
            "[red]Error:[/red] --prd is required.\n"
            "Usage: ralph --prd <file-or-directory-or-glob> [--max-turns N]"
        )
        return 1

    missing = _collect_missing_prd_files(config)
    if missing:
        if len(missing) == 1:
            console.print(f"[red]Error:[/red] PRD file not found: {missing[0]}")
        else:
            console.print("[red]Error:[/red] Some PRD files were not found:")
            for path in missing:
                console.print(f"  - {path}")
        return 1

    try:
        return _run_sync(config)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Stopping ralph.[/yellow]")
        return 130
