from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, UTC

from rich.console import Console
from rich.panel import Panel

from ralph.core import RalphConfig
from ralph.core.loop import IterationResult, run_ralph
from ralph.core.run_meta import RunMeta, RunStatus, default_runs_dir, generate_run_id

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

    run_id = generate_run_id()
    runs_dir = default_runs_dir()
    session_id = uuid.uuid4().hex

    log_path = runs_dir / run_id / "output.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w")

    meta = RunMeta(
        run_id=run_id,
        pid=os.getpid(),
        started_at=datetime.now(UTC).isoformat(),
        status=RunStatus.RUNNING,
        prd=str(config.prd),
        tasks=str(config.tasks) if config.tasks else None,
        iterations_requested=config.iterations,
        model=config.model,
        permission_mode=str(config.permission_mode),
        session_id=session_id,
        context_files=[str(p) for p in config.context_files],
    )
    meta.write(runs_dir)

    console.print(f"[dim]run_id: {run_id}[/dim]")

    start = time.monotonic()
    try:
        async for _iteration, item in run_ralph(config, session_id=session_id):
            if isinstance(item, str):
                print(item, end="", flush=True)
                log_file.write(item)
                log_file.flush()
            elif isinstance(item, IterationResult):
                log_file.write(
                    f"\n--- Iteration {item.iteration} done ({item.duration_s:.1f}s) ---\n"
                )
                log_file.flush()
                elapsed = time.monotonic() - start
                meta.update(
                    runs_dir,
                    iterations_completed=item.iteration,
                    total_duration_s=round(elapsed, 2),
                )
                console.print(
                    f"  iteration {item.iteration}/{config.iterations}  "
                    f"elapsed: {elapsed:.1f}s"
                )
                if item.is_complete:
                    break

        elapsed = time.monotonic() - start
        meta.update(
            runs_dir,
            status=RunStatus.DONE,
            completed_at=datetime.now(UTC).isoformat(),
            total_duration_s=round(elapsed, 2),
        )
        console.print(
            Panel(
                f"[bold green]DONE[/bold green] after {meta.iterations_completed} iteration(s)\n"
                f"Total time: {elapsed:.1f}s",
                border_style="green",
            )
        )
        return 0

    except KeyboardInterrupt:
        elapsed = time.monotonic() - start
        meta.update(
            runs_dir,
            status=RunStatus.KILLED,
            completed_at=datetime.now(UTC).isoformat(),
            total_duration_s=round(elapsed, 2),
        )
        console.print("\n[yellow]Interrupted. Stopping ralph.[/yellow]")
        return 130

    except Exception:
        import traceback

        elapsed = time.monotonic() - start
        traceback.print_exc(file=log_file)
        meta.update(
            runs_dir,
            status=RunStatus.ERROR,
            completed_at=datetime.now(UTC).isoformat(),
            total_duration_s=round(elapsed, 2),
        )
        console.print(
            Panel(
                f"[bold red]ERROR[/bold red] after {meta.iterations_completed} iteration(s)\n"
                f"Total time: {elapsed:.1f}s",
                border_style="red",
            )
        )
        return 1

    finally:
        log_file.close()
