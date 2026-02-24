from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
        summary.add_column("Cost", width=10)
        summary.add_column("Status", width=12)

        total_cost = 0.0
        for r in results:
            status_str = (
                "[green]COMPLETE[/green]" if r.is_complete else "[blue]done[/blue]"
            )
            summary.add_row(
                str(r.iteration),
                f"{r.duration_s:.1f}s",
                f"${r.cost_usd:.4f}",
                status_str,
            )
            total_cost += r.cost_usd

        grid.add_row(summary)
        grid.add_row(Text(f"\n  Total cost: ${total_cost:.4f}", style="bold"))

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


def parse_args(argv: list[str] | None = None) -> RalphConfig:
    parser = argparse.ArgumentParser(
        prog="ralph",
        description="Autonomous coding agent loop powered by Claude",
    )
    parser.add_argument("iterations", type=int, help="Number of iterations to run")
    parser.add_argument(
        "--prd", type=Path, default=Path("PRD.md"), help="Path to PRD file"
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

    args = parser.parse_args(argv)

    # Resolve webhook URL: CLI flag takes priority over env var
    discord_webhook_url = (
        args.discord_webhook or os.environ.get("RALPH_DISCORD_WEBHOOK") or None
    )

    return RalphConfig(
        prd=args.prd,
        tasks=args.tasks,
        iterations=args.iterations,
        cwd=args.cwd,
        permission_mode=args.permission_mode,
        model=args.model,
        max_turns=args.max_turns,
        discord_webhook_url=discord_webhook_url,
        discord_min_interval=args.discord_interval,
    )


async def _run(config: RalphConfig) -> int:
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
                        cost_usd=item.cost_usd,
                        duration_s=item.duration_s,
                        is_complete=item.is_complete,
                    )

                if item.is_complete:
                    break

    # Final summary
    total_cost = sum(r.cost_usd for r in results)
    total_time = sum(r.duration_s for r in results)
    completed = any(r.is_complete for r in results)

    console.print()
    if completed:
        console.print(
            Panel(
                f"[bold green]PRD COMPLETE[/bold green] after {len(results)} iteration(s)\n"
                f"Total cost: ${total_cost:.4f}  Total time: {total_time:.1f}s",
                border_style="green",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                f"[bold yellow]Reached max iterations ({config.iterations})[/bold yellow]\n"
                f"Total cost: ${total_cost:.4f}  Total time: {total_time:.1f}s",
                border_style="yellow",
            )
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)

    if not config.prd.exists():
        console.print(f"[red]Error:[/red] PRD file not found: {config.prd}")
        return 1

    try:
        return asyncio.run(_run(config))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Stopping ralph.[/yellow]")
        return 130
