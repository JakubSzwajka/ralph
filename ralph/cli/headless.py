from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from ralph.core import RalphConfig
from ralph.core.executor import RunResult, execute_run
from ralph.core.run_meta import RunStatus

console = Console()


async def _run_headless(config: RalphConfig) -> int:
    prompt_files = (
        list(config.context_files)
        if config.context_files
        else [config.prd, *([config.tasks] if config.tasks else [])]
    )
    prd_label = (
        f"{len(config.context_files)} files"
        if config.context_files
        else str(config.prd)
    )
    console.print(
        Panel(
            f"[bold magenta]ralph[/bold magenta] — autonomous coding agent\n"
            f"PRD: [cyan]{prd_label}[/cyan]  "
            f"Tasks: [cyan]{config.tasks or 'auto'}[/cyan]  "
            f"Iterations: [cyan]{config.iterations}[/cyan]",
            border_style="magenta",
        )
    )
    if prompt_files:
        console.print("[dim]prompt files:[/dim]")
        for path in prompt_files:
            console.print(f"[dim]- {path}[/dim]")

    result = await execute_run(
        config,
        on_text=lambda text: print(text, flush=True),
    )

    _print_summary(result)
    return _exit_code(result)


def _print_summary(result: RunResult) -> None:
    iters = f"{result.iterations_completed} iteration(s)"
    time_s = f"{result.elapsed_s:.1f}s"

    if result.status == RunStatus.DONE:
        console.print(
            Panel(
                f"[bold green]DONE[/bold green] after {iters}\nTotal time: {time_s}",
                border_style="green",
            )
        )
    elif result.status == RunStatus.KILLED:
        console.print("\n[yellow]Interrupted. Stopping ralph.[/yellow]")
    else:
        console.print(
            Panel(
                f"[bold red]ERROR[/bold red] after {iters}\nTotal time: {time_s}",
                border_style="red",
            )
        )


def _exit_code(result: RunResult) -> int:
    if result.status == RunStatus.DONE:
        return 0
    if result.status == RunStatus.KILLED:
        return 130
    return 1
