from __future__ import annotations

import asyncio
import os
import time
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import RichLog, Static

from ralph.core import RalphConfig
from ralph.core.loop import IterationResult, run_ralph
from ralph.core.run_meta import (
    RunMeta,
    RunStatus,
    default_runs_dir,
    generate_run_id,
)
from ralph.tui.screens.run_browser import _fmt_duration


class RunScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("backspace", "go_back", "Back", show=False, priority=True),
        Binding("k", "stop_run", "Stop"),
    ]

    DEFAULT_CSS = """
    RunScreen {
        layout: vertical;
    }

    #run-screen-wrap {
        width: 1fr;
        height: 1fr;
        margin: 1 1;
    }

    #run-output-card {
        width: 1fr;
        height: 1fr;
        border: round $primary-background-lighten-2;
        border-title-color: $text-muted;
        border-title-align: center;
        padding: 0 1;
    }

    #run-output-log {
        width: 1fr;
        height: 1fr;
    }

    #run-status-bar {
        height: 1;
        dock: bottom;
        padding: 0 2;
        color: $text-muted;
    }
    """

    def __init__(
        self, config: RalphConfig, context_files: list[Path], iterations: int
    ) -> None:
        super().__init__()
        self._config = config
        self._context_files = context_files
        self._iterations = iterations
        self._status = "WAITING"
        self._iteration_current = 0
        self._elapsed = 0.0
        self._running = False
        self._run_task = None
        self._start_time: float | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="run-screen-wrap"):
            with Vertical(id="run-output-card"):
                yield RichLog(id="run-output-log", highlight=True, markup=True)
        yield Static(self._status_text(), id="run-status-bar")

    def on_mount(self) -> None:
        self.query_one("#run-output-card").border_title = "Output"
        log = self.query_one("#run-output-log", RichLog)
        log.write("[dim]Waiting for run to start…[/dim]")
        self._run_task = self._run_worker()
        self.set_interval(1.0, self._tick_elapsed)

    def _tick_elapsed(self) -> None:
        if self._running and self._start_time is not None:
            self._elapsed = time.monotonic() - self._start_time
            self._update_status_bar()

    def _status_text(self) -> str:
        elapsed = _fmt_duration(self._elapsed)
        return (
            f"Iteration {self._iteration_current}/{self._iterations}  "
            f"{elapsed}  "
            f"[bold]{self._status}[/bold]  "
            f"[dim]k[/dim] stop"
        )

    def _update_status_bar(self) -> None:
        self.query_one("#run-status-bar", Static).update(self._status_text())

    @work(exclusive=True)
    async def _run_worker(self) -> None:
        log = self.query_one("#run-output-log", RichLog)
        run_id = generate_run_id()
        session_id = uuid.uuid4().hex
        runs_dir = default_runs_dir()

        log_path = runs_dir / run_id / "output.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "w")

        meta = RunMeta(
            run_id=run_id,
            pid=os.getpid(),
            started_at=datetime.now(UTC).isoformat(),
            status=RunStatus.RUNNING,
            prd=str(self._config.prd),
            tasks=str(self._config.tasks) if self._config.tasks else None,
            iterations_requested=self._iterations,
            model=self._config.model,
            permission_mode=str(self._config.permission_mode),
            session_id=session_id,
            context_files=[str(p) for p in self._context_files],
        )
        meta.write(runs_dir)

        self._running = True
        self._status = "RUNNING"
        self._start_time = time.monotonic()
        self._update_status_bar()

        log.clear()

        try:
            async for _iteration, item in run_ralph(
                self._config, session_id=session_id
            ):
                if isinstance(item, str):
                    log.write(item)
                    log_file.write(item)
                    log_file.flush()
                elif isinstance(item, IterationResult):
                    separator = f"\n{'─' * 60}\n  Iteration {item.iteration} complete ({item.duration_s:.1f}s)\n{'─' * 60}\n"
                    log.write(separator)
                    log_file.write(separator)
                    log_file.flush()
                    self._iteration_current = item.iteration
                    self._elapsed = time.monotonic() - self._start_time
                    meta.update(
                        runs_dir,
                        iterations_completed=item.iteration,
                        total_duration_s=round(self._elapsed, 2),
                    )
                    self._update_status_bar()
                    if item.is_complete:
                        break

            self._elapsed = time.monotonic() - self._start_time
            self._status = "DONE"
            meta.update(
                runs_dir,
                status=RunStatus.DONE,
                completed_at=datetime.now(UTC).isoformat(),
                total_duration_s=round(self._elapsed, 2),
            )

        except asyncio.CancelledError:
            self._elapsed = time.monotonic() - (self._start_time or time.monotonic())
            self._status = "KILLED"
            meta.update(
                runs_dir,
                status=RunStatus.KILLED,
                completed_at=datetime.now(UTC).isoformat(),
                total_duration_s=round(self._elapsed, 2),
            )
            raise

        except Exception:
            self._elapsed = time.monotonic() - (self._start_time or time.monotonic())
            self._status = "ERROR"
            tb = traceback.format_exc()
            log.write(f"[red]{tb}[/red]")
            log_file.write(tb)
            meta.update(
                runs_dir,
                status=RunStatus.ERROR,
                completed_at=datetime.now(UTC).isoformat(),
                total_duration_s=round(self._elapsed, 2),
            )

        finally:
            log_file.close()
            self._running = False
            self._update_status_bar()

    def action_go_back(self) -> None:
        if self._running:
            return
        self.app.pop_screen()

    def action_stop_run(self) -> None:
        if self._running and self._run_task is not None:
            self._run_task.cancel()
