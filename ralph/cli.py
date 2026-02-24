from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
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


def _parse_jsonl_events(jsonl_path: Path) -> list[dict]:
    """Read a JSONL file and return a list of parsed event dicts.

    Lines that cannot be decoded as JSON are silently skipped.
    """
    events: list[dict] = []
    try:
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return events


def _print_iteration_text(run_dir: Path, iteration: int) -> int:
    """Print the full concatenated text output of a specific iteration.

    Returns 0 on success, 1 if the iteration file is missing.
    """
    jsonl_path = run_dir / f"iteration-{iteration:02d}.jsonl"
    if not jsonl_path.exists():
        console.print(
            f"[red]Error:[/red] Iteration {iteration} not found in run directory."
        )
        return 1

    events = _parse_jsonl_events(jsonl_path)
    text_parts = [e.get("text", "") for e in events if e.get("type") == "text"]

    if not text_parts:
        console.print("[dim]No text output found for this iteration.[/dim]")
        return 0

    console.print(
        Panel(
            "".join(text_parts),
            title=f"[dim]Iteration {iteration} output[/dim]",
            border_style="dim",
        )
    )
    return 0


def _show_run_detail(runs_dir: Path, run_id: str, show_iteration: int | None) -> int:
    """Show the detail view for a specific run identified by *run_id*.

    Prints a Rich panel with config / meta info, then a table of all
    iterations with event counts and key tool calls.  When *show_iteration*
    is set, prints the full text output for that iteration instead.
    """
    run_dir = runs_dir / run_id
    if not run_dir.exists():
        console.print(f"[red]Error:[/red] Run not found: {run_id}")
        return 1

    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        console.print(f"[red]Error:[/red] meta.json not found for run: {run_id}")
        return 1

    try:
        with meta_path.open("r", encoding="utf-8") as fh:
            meta: dict = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        console.print(f"[red]Error:[/red] Could not read meta.json: {exc}")
        return 1

    # ------------------------------------------------------------------
    # --iteration N: print text output for a single iteration and exit.
    # ------------------------------------------------------------------
    if show_iteration is not None:
        return _print_iteration_text(run_dir, show_iteration)

    # ------------------------------------------------------------------
    # Config / meta panel
    # ------------------------------------------------------------------
    prd_path_str = meta.get("prd", "?")
    prd_name = Path(prd_path_str).parent.name or Path(prd_path_str).name or "?"

    dur_val = meta.get("total_duration_s")
    dur_str = f"{dur_val:.1f}s" if dur_val is not None else "—"

    status = meta.get("status", "in-progress")
    status_styled = {
        "complete": "[green]complete[/green]",
        "max-iterations": "[yellow]max-iterations[/yellow]",
        "error": "[red]error[/red]",
    }.get(status, f"[dim]{status}[/dim]")

    panel_lines = [
        f"[bold]Run ID:[/bold]              {run_id}",
        f"[bold]PRD:[/bold]                 {prd_path_str}  ([dim]{prd_name}[/dim])",
        f"[bold]Tasks:[/bold]               {meta.get('tasks') or '—'}",
        f"[bold]Model:[/bold]               {meta.get('model') or '—'}",
        f"[bold]Permission mode:[/bold]     {meta.get('permission_mode') or '—'}",
        f"[bold]Iterations requested:[/bold] {meta.get('iterations_requested', '—')}",
        f"[bold]Iterations completed:[/bold] {meta.get('iterations_completed', '—')}",
        f"[bold]Total duration:[/bold]      {dur_str}",
        f"[bold]Status:[/bold]              {status_styled}",
        f"[bold]Started:[/bold]             {meta.get('started_at', '—')}",
        f"[bold]Completed:[/bold]           {meta.get('completed_at', '—')}",
    ]
    console.print(
        Panel(
            "\n".join(panel_lines),
            title=f"[cyan]Run detail: {run_id}[/cyan]",
            border_style="cyan",
        )
    )

    # ------------------------------------------------------------------
    # Iterations table built from JSONL files
    # ------------------------------------------------------------------
    iteration_files = sorted(run_dir.glob("iteration-*.jsonl"))
    if not iteration_files:
        console.print("[dim]No iteration files found.[/dim]")
        return 0

    table = Table(title="Iterations", show_header=True, show_lines=False)
    table.add_column("#", style="bold", width=4)
    table.add_column("Duration", justify="right", width=10)
    table.add_column("Events", justify="right", width=8)
    table.add_column("Tool calls")

    for jsonl_path in iteration_files:
        match = re.match(r"iteration-(\d+)\.jsonl", jsonl_path.name)
        if not match:
            continue
        iter_num = int(match.group(1))

        events = _parse_jsonl_events(jsonl_path)
        event_count = len(events)

        # Duration: difference between first and last event timestamps.
        timestamps = [e.get("timestamp") for e in events if e.get("timestamp")]
        if len(timestamps) >= 2:
            try:
                t0 = datetime.fromisoformat(timestamps[0])
                t1 = datetime.fromisoformat(timestamps[-1])
                duration_str = f"{(t1 - t0).total_seconds():.1f}s"
            except ValueError:
                duration_str = "—"
        else:
            duration_str = "—"

        # Key tool calls: unique names with occurrence counts.
        tool_names = [
            e.get("name", "")
            for e in events
            if e.get("type") == "tool_use" and e.get("name")
        ]
        if tool_names:
            counts = Counter(tool_names)
            tool_str = ", ".join(
                f"{name}×{cnt}" if cnt > 1 else name
                for name, cnt in counts.most_common(5)
            )
        else:
            tool_str = "—"

        table.add_row(str(iter_num), duration_str, str(event_count), tool_str)

    console.print(table)
    return 0


def _cmd_runs(argv: list[str] | None = None) -> int:
    """Handle the ``ralph runs`` subcommand — list past runs from ``.ralph/runs/``."""
    parser = argparse.ArgumentParser(
        prog="ralph runs",
        description="List past ralph runs from .ralph/runs/",
    )
    parser.add_argument(
        "run_id",
        nargs="?",
        default=None,
        help="Run ID (timestamp) to show detail for; omit to list all runs",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=Path.cwd(),
        help="Working directory to look for .ralph/runs/ (default: cwd)",
    )
    parser.add_argument(
        "--iteration",
        type=int,
        default=None,
        metavar="N",
        help="Print full text output of iteration N (requires run_id)",
    )
    args = parser.parse_args(argv)

    runs_dir = args.cwd / ".ralph" / "runs"

    # Dispatch to the detail view when a specific run ID is given.
    if args.run_id is not None:
        return _show_run_detail(runs_dir, args.run_id, args.iteration)

    if not runs_dir.exists():
        console.print("[dim]No runs found. Run ralph to create run history.[/dim]")
        return 0

    # Collect run metadata from each subdirectory.
    runs: list[dict] = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        meta_path = run_dir / "meta.json"
        if not meta_path.exists():
            continue
        try:
            with meta_path.open("r", encoding="utf-8") as fh:
                meta = json.load(fh)
            runs.append(meta)
        except (json.JSONDecodeError, OSError):
            continue

    if not runs:
        console.print("[dim]No runs found. Run ralph to create run history.[/dim]")
        return 0

    # Sort by run_id descending (most recent first — timestamps sort lexicographically).
    runs.sort(key=lambda m: m.get("run_id", ""), reverse=True)

    table = Table(title="Ralph Run History", show_header=True, show_lines=False)
    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("PRD", style="bold")
    table.add_column("Iterations", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Status")

    for meta in runs:
        run_id = meta.get("run_id", "?")

        # Derive a short PRD name: use the parent directory name for paths like
        # "docs/prds/run-history/README.md", fall back to the filename itself.
        prd_path_str = meta.get("prd", "")
        prd_path = Path(prd_path_str)
        prd_name = prd_path.parent.name or prd_path.name or "?"

        iterations = str(meta.get("iterations_completed", "—"))

        dur_val = meta.get("total_duration_s")
        duration = f"{dur_val:.1f}s" if dur_val is not None else "—"

        status = meta.get("status", "in-progress")
        status_styled = {
            "complete": "[green]complete[/green]",
            "max-iterations": "[yellow]max-iterations[/yellow]",
            "error": "[red]error[/red]",
        }.get(status, f"[dim]{status}[/dim]")

        table.add_row(run_id, prd_name, iterations, duration, status_styled)

    console.print(table)
    return 0


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
    parser.add_argument("iterations", type=int, help="Number of iterations to run")
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
            "Directory to scan for PRDs when using the interactive browser "
            "(also reads prd_directory from ~/.ralph/config.json; default: docs/prds)"
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
    # Dispatch ``ralph runs [...]`` before full argument parsing so the
    # positional ``iterations`` argument is not required for that subcommand.
    raw: list[str] = list(argv) if argv is not None else sys.argv[1:]
    if raw and raw[0] == "runs":
        return _cmd_runs(raw[1:])

    config, prd_explicit, prd_dir, no_tui_flag = parse_args(argv)

    # Auto-enable headless mode when stdout is not a TTY (piped output, CI, etc.)
    no_tui: bool = no_tui_flag or not sys.stdout.isatty()

    if no_tui:
        # ── Headless mode ─────────────────────────────────────────────────
        if not prd_explicit:
            console.print("[red]Error:[/red] --prd is required in headless mode (--no-tui or piped output)")
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
        # ── TUI mode (default) ─────────────────────────────────────────────
        # Launch the persistent Textual app.  If --prd was supplied go
        # straight to RunScreen; otherwise open the PRD browser screen.
        from ralph.tui import RalphApp

        if prd_explicit and not config.prd.exists():
            console.print(f"[red]Error:[/red] PRD file not found: {config.prd}")
            return 1

        tui_config = config if prd_explicit else None
        RalphApp(tui_config, prd_dir=prd_dir).run()
        return 0
