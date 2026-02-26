from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ralph.config import load_config
from ralph.core import IterationResult, RalphConfig, run_ralph
from ralph.notifier import DiscordNotifier


console = Console()


def _build_status_table(
    config: RalphConfig,
    current_iteration: int,
    results: list[IterationResult],
    running: bool,
    tail_lines: list[str],
) -> Table:
    grid = Table.grid(padding=(0, 2))
    grid.add_column(justify="left")

    # Header
    header = Text()
    header.append("ralph", style="bold magenta")
    header.append(f"  PRD: {config.prd}", style="dim")
    if config.tasks:
        header.append(f"  Tasks: {config.tasks}", style="dim")
    grid.add_row(header)
    grid.add_row(Text(""))

    # Progress bar
    total = config.iterations
    done = len(results)
    bar_width = 40
    filled = int(bar_width * done / total) if total else 0
    bar = f"[green]{'█' * filled}[/green][dim]{'░' * (bar_width - filled)}[/dim]"
    status = "running" if running else "done"
    progress_text = Text.from_markup(
        f"  Iteration {current_iteration}/{total}  {bar}  [{status}]"
    )
    grid.add_row(progress_text)
    grid.add_row(Text(""))

    # Completed iterations summary
    if results:
        summary = Table(show_header=True, show_edge=False, pad_edge=False)
        summary.add_column("#", style="bold", width=4)
        summary.add_column("Duration", width=10)
        summary.add_column("Status", width=12)

        for r in results:
            status_str = (
                "[green]COMPLETE[/green]" if r.is_complete else "[blue]done[/blue]"
            )
            summary.add_row(
                str(r.iteration),
                f"{r.duration_s:.1f}s",
                status_str,
            )

        grid.add_row(summary)

    # Live output tail
    if tail_lines:
        tail_text = "\n".join(tail_lines[-8:])
        grid.add_row(Text(""))
        grid.add_row(
            Panel(
                tail_text,
                title=f"[dim]Iteration {current_iteration} output[/dim]",
                border_style="dim",
                expand=True,
            )
        )

    return grid


def parse_args(
    argv: list[str] | None = None,
) -> tuple[RalphConfig, bool, Path | None, bool]:
    """Parse CLI arguments and return (RalphConfig, prd_explicit, prd_dir, no_tui).

    *prd_explicit* is ``True`` when the user passed ``--prd`` on the command
    line.  When it is ``False`` the caller should launch the interactive file
    browser to let the user choose a PRD.

    *prd_dir* is the resolved directory to scan for PRDs.  ``None`` means
    "use the browser default (cwd/docs/prds)".  A non-``None`` value means
    the directory was explicitly configured via ``--prd-dir`` or
    ``prd_directory`` in the config file.

    *no_tui* is ``True`` when ``--no-tui`` was passed.  The caller should
    also force headless mode when stdout is not a TTY.
    """
    parser = argparse.ArgumentParser(
        prog="ralph",
        description="Autonomous coding agent loop powered by Claude",
    )
    parser.add_argument(
        "iterations",
        type=int,
        nargs="?",
        default=10,
        help="Number of iterations to run (default: 10)",
    )
    parser.add_argument(
        "--prd",
        type=Path,
        default=None,
        help="Path to PRD file (omit to use the interactive file browser)",
    )
    parser.add_argument(
        "--tasks", type=Path, default=None, help="Path to tasks list or directory"
    )
    parser.add_argument(
        "--cwd", type=Path, default=Path.cwd(), help="Working directory"
    )
    parser.add_argument(
        "--permission-mode",
        default="bypassPermissions",
        choices=["default", "acceptEdits", "plan", "bypassPermissions"],
    )
    parser.add_argument("--model", default=None, help="Claude model to use")
    parser.add_argument(
        "--max-turns", type=int, default=None, help="Max turns per iteration"
    )
    parser.add_argument(
        "--discord-webhook",
        default=None,
        metavar="URL",
        help="Discord webhook URL for notifications (also reads RALPH_DISCORD_WEBHOOK env var)",
    )
    parser.add_argument(
        "--discord-interval",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Minimum interval between Discord notification messages (default: 5s)",
    )
    parser.add_argument(
        "--prd-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Directory to scan for docs when using the interactive browser "
            "(also reads prd_directory from ~/.ralph/config.json; default: docs/)"
        ),
    )
    parser.add_argument(
        "--no-tui",
        action="store_true",
        default=False,
        help=(
            "Disable the Textual TUI and use the legacy Rich output instead. "
            "Automatically enabled when stdout is not a TTY (e.g. piped output, CI)."
        ),
    )

    args = parser.parse_args(argv)

    # Track whether the user explicitly provided --prd so main() can decide
    # whether to show the interactive browser.
    prd_explicit: bool = args.prd is not None
    prd: Path = args.prd if prd_explicit else Path("PRD.md")

    # Load config file values (lowest precedence after defaults)
    file_config = load_config()

    # Resolve webhook URL: CLI flag > env var > config file
    discord_webhook_url = (
        args.discord_webhook
        or os.environ.get("RALPH_DISCORD_WEBHOOK")
        or file_config.get("discord_webhook_url")
        or None
    )

    # Resolve discord interval: CLI flag > config file > default (5.0)
    # args.discord_interval always has a value (default=5.0), so we check whether the
    # user explicitly provided it by comparing against the sentinel default.
    _interval_default = 5.0
    if args.discord_interval != _interval_default:
        # User explicitly set --discord-interval on the CLI; it wins.
        discord_min_interval: float = args.discord_interval
    else:
        # Fall back to config file, then default.
        discord_min_interval = float(
            file_config.get("discord_min_interval", _interval_default)
        )

    # Resolve PRD scan directory: CLI flag > config file > None (use browser default)
    if args.prd_dir is not None:
        # User explicitly passed --prd-dir; resolve relative paths against cwd.
        prd_dir: Path | None = (
            args.prd_dir if args.prd_dir.is_absolute() else args.cwd / args.prd_dir
        )
    elif "prd_directory" in file_config:
        prd_dir = args.cwd / file_config["prd_directory"]
    else:
        prd_dir = None

    return (
        RalphConfig(
            prd=prd,
            tasks=args.tasks,
            iterations=args.iterations,
            cwd=args.cwd,
            permission_mode=args.permission_mode,
            model=args.model,
            max_turns=args.max_turns,
            discord_webhook_url=discord_webhook_url,
            discord_min_interval=discord_min_interval,
        ),
        prd_explicit,
        prd_dir,
        args.no_tui,
    )


async def _run_headless(config: RalphConfig) -> int:
    results: list[IterationResult] = []
    current_iteration = 0
    tail_lines: list[str] = []

    console.print(
        Panel(
            f"[bold magenta]ralph[/bold magenta] — autonomous coding agent\n"
            f"PRD: [cyan]{config.prd}[/cyan]  "
            f"Tasks: [cyan]{config.tasks or 'auto'}[/cyan]  "
            f"Iterations: [cyan]{config.iterations}[/cyan]",
            border_style="magenta",
        )
    )

    # Create Discord notifier if enabled
    notifier: DiscordNotifier | None = None
    if config.discord_notify and config.discord_webhook_url:
        notifier = DiscordNotifier(
            webhook_url=config.discord_webhook_url,
            min_interval=config.discord_min_interval,
        )

    with Live(
        _build_status_table(config, 0, results, True, tail_lines),
        console=console,
        refresh_per_second=4,
    ) as live:
        async for iteration, item in run_ralph(config):
            current_iteration = iteration

            if isinstance(item, str):
                # Streaming text chunk
                for line in item.splitlines():
                    stripped = line.strip()
                    if stripped:
                        tail_lines.append(stripped)
                        if len(tail_lines) > 50:
                            tail_lines = tail_lines[-50:]
                live.update(
                    _build_status_table(
                        config, current_iteration, results, True, tail_lines
                    )
                )
            else:
                results.append(item)
                tail_lines.clear()
                live.update(
                    _build_status_table(
                        config, current_iteration, results, True, tail_lines
                    )
                )

                if notifier is not None:
                    await notifier.send(
                        iteration=item.iteration,
                        summary=item.text,
                        duration_s=item.duration_s,
                        is_complete=item.is_complete,
                    )

                if item.is_complete:
                    break

    # Final summary
    total_time = sum(r.duration_s for r in results)
    completed = any(r.is_complete for r in results)

    console.print()
    if completed:
        console.print(
            Panel(
                f"[bold green]PRD COMPLETE[/bold green] after {len(results)} iteration(s)\n"
                f"Total time: {total_time:.1f}s",
                border_style="green",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                f"[bold yellow]Reached max iterations ({config.iterations})[/bold yellow]\n"
                f"Total time: {total_time:.1f}s",
                border_style="yellow",
            )
        )
        return 1


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
