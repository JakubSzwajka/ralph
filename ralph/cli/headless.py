from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys

from rich.console import Console
from rich.panel import Panel

from ralph.core import RalphConfig
from ralph.core.run_meta import RunMeta, RunStatus, default_runs_dir
from ralph.notifier import DiscordNotifier
from ralph.worker import serialize_config

console = Console()


async def _run_headless(config: RalphConfig) -> int:
    console.print(
        Panel(
            f"[bold magenta]ralph[/bold magenta] — autonomous coding agent\n"
            f"PRD: [cyan]{config.prd}[/cyan]  "
            f"Tasks: [cyan]{config.tasks or 'auto'}[/cyan]  "
            f"Iterations: [cyan]{config.iterations}[/cyan]",
            border_style="magenta",
        )
    )

    config_path = serialize_config(config)
    proc = subprocess.Popen(
        [sys.executable, "-m", "ralph.worker", config_path],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    run_id = proc.stdout.readline().decode().strip()  # type: ignore[union-attr]
    proc.stdout.close()  # type: ignore[union-attr]

    if not run_id:
        console.print("[red]Failed to start worker — no run_id received[/red]")
        return 1

    console.print(f"[dim]run_id: {run_id}  pid: {proc.pid}[/dim]")

    runs_dir = default_runs_dir()
    meta_path = runs_dir / run_id / "meta.json"

    notifier: DiscordNotifier | None = None
    if config.discord_notify and config.discord_webhook_url:
        notifier = DiscordNotifier(
            webhook_url=config.discord_webhook_url,
            min_interval=config.discord_min_interval,
        )

    last_iterations = 0
    meta: RunMeta | None = None

    try:
        while True:
            await asyncio.sleep(1)

            if not meta_path.exists():
                continue

            try:
                meta = RunMeta.read(meta_path)
            except Exception:
                continue

            if meta.iterations_completed > last_iterations:
                console.print(
                    f"  iteration {meta.iterations_completed}/{meta.iterations_requested}  "
                    f"elapsed: {meta.total_duration_s:.1f}s"
                )

                if notifier is not None:
                    await notifier.send(
                        iteration=meta.iterations_completed,
                        summary=f"Iteration {meta.iterations_completed} complete",
                        duration_s=meta.total_duration_s,
                        is_complete=meta.status == RunStatus.DONE,
                    )

                last_iterations = meta.iterations_completed

            if meta.status != RunStatus.RUNNING:
                break

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted — sending SIGTERM to worker[/yellow]")
        try:
            m = RunMeta.read(meta_path)
            if m.pid:
                os.kill(m.pid, signal.SIGTERM)
                await asyncio.sleep(2)
        except Exception:
            pass
        return 1
    finally:
        try:
            os.unlink(config_path)
        except OSError:
            pass

    if meta is None:
        console.print("[red]Worker never wrote meta.json[/red]")
        return 1

    if meta.status == RunStatus.DONE:
        console.print(
            Panel(
                f"[bold green]DONE[/bold green] after {meta.iterations_completed} iteration(s)\n"
                f"Total time: {meta.total_duration_s:.1f}s",
                border_style="green",
            )
        )
        return 0

    label = "ERROR" if meta.status == RunStatus.ERROR else "KILLED"
    console.print(
        Panel(
            f"[bold red]{label}[/bold red] after {meta.iterations_completed} iteration(s)\n"
            f"Total time: {meta.total_duration_s:.1f}s",
            border_style="red",
        )
    )
    return 1
