"""Unified run executor — shared logic for headless and TUI modes.

Both consumers provide thin callbacks for output; all RunMeta lifecycle,
log-file management, separator formatting, and error handling lives here.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ralph.core.config import RalphConfig
from ralph.core.loop import IterationResult, run_ralph
from ralph.core.run_meta import (
    RunMeta,
    RunStatus,
    default_runs_dir,
    generate_run_id,
)

ITERATION_SEPARATOR = (
    "\n{bar}\n  Iteration {iteration} complete ({duration:.1f}s)\n{bar}\n"
)


def format_separator(result: IterationResult) -> str:
    bar = "─" * 60
    return ITERATION_SEPARATOR.format(
        bar=bar, iteration=result.iteration, duration=result.duration_s
    )


class RunResult:
    __slots__ = ("status", "iterations_completed", "elapsed_s", "error")

    def __init__(
        self,
        status: RunStatus,
        iterations_completed: int,
        elapsed_s: float,
        error: str | None = None,
    ) -> None:
        self.status = status
        self.iterations_completed = iterations_completed
        self.elapsed_s = elapsed_s
        self.error = error


OnText = Callable[[str], None]
OnIteration = Callable[[IterationResult], None]


async def execute_run(
    config: RalphConfig,
    *,
    on_text: OnText,
    on_iteration: OnIteration | None = None,
    cancel_event: asyncio.Event | None = None,
) -> RunResult:
    """Run the full agent loop with unified meta/log management.

    Parameters
    ----------
    config:
        Fully resolved run configuration.
    on_text:
        Called for each text chunk from the agent stream.
    on_iteration:
        Called after each iteration completes (with separator already written).
    cancel_event:
        If set, the loop will check this event and treat it as cancellation.
    """
    run_id = generate_run_id()
    runs_dir = default_runs_dir()

    log_path = runs_dir / run_id / "output.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w")

    context_files = list(config.context_files) if config.context_files else []

    # Auto-create and inject notebook.md as a sibling of the PRD.
    notebook = config.prd.parent / "notebook.md"
    if not notebook.exists():
        notebook.write_text(
            "# Notebook\n\n"
            "Shared scratchpad for agents working on this PRD. "
            "Read before starting a task. Append notes as you go.\n\n---\n"
        )
    if notebook not in context_files:
        context_files.insert(0, notebook)

    meta = RunMeta.create_new(
        run_id, config, config.iterations, context_files
    )
    meta.write(runs_dir)

    start = time.monotonic()

    def _elapsed() -> float:
        return time.monotonic() - start

    def _finalize(status: RunStatus, error: str | None = None) -> RunResult:
        elapsed = _elapsed()
        meta.update(
            runs_dir,
            status=status,
            completed_at=datetime.now(UTC).isoformat(),
            total_duration_s=round(elapsed, 2),
        )
        return RunResult(
            status=status,
            iterations_completed=meta.iterations_completed,
            elapsed_s=elapsed,
            error=error,
        )

    try:
        async for _i, item in run_ralph(config):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError

            if isinstance(item, str):
                on_text(item)
                log_file.write(item + "\n")
                log_file.flush()
            elif isinstance(item, IterationResult):
                sep = format_separator(item)
                on_text(sep)
                log_file.write(sep)
                log_file.flush()

                meta.update(
                    runs_dir,
                    iterations_completed=item.iteration,
                    total_duration_s=round(_elapsed(), 2),
                )
                if on_iteration:
                    on_iteration(item)
                if item.is_complete:
                    break

        return _finalize(RunStatus.DONE)

    except (asyncio.CancelledError, KeyboardInterrupt):
        return _finalize(RunStatus.KILLED)

    except Exception:
        tb = traceback.format_exc()
        log_file.write(tb)
        return _finalize(RunStatus.ERROR, error=tb)

    finally:
        log_file.close()
