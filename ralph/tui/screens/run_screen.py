from __future__ import annotations

import asyncio
import time
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import RichLog, Static

from ralph.core import RalphConfig
from ralph.core.executor import execute_run
from ralph.core.loop import IterationResult
from ralph.core.run_meta import RunStatus


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
        self._iterations = iterations
        self._status = "WAITING"
        self._iteration_current = 0
        self._elapsed = 0.0
        self._running = False
        self._run_task = None
        self._cancel_event = asyncio.Event()
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
        elapsed = f"{self._elapsed:.1f}s"
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
        log.clear()

        self._running = True
        self._status = "RUNNING"
        self._start_time = time.monotonic()
        self._update_status_bar()

        def on_text(text: str) -> None:
            log.write(text)

        def on_iteration(item: IterationResult) -> None:
            self._iteration_current = item.iteration
            self._elapsed = time.monotonic() - self._start_time  # type: ignore[operator]
            self._update_status_bar()

        result = await execute_run(
            self._config,
            on_text=on_text,
            on_iteration=on_iteration,
            cancel_event=self._cancel_event,
        )

        self._status = result.status.value.upper()
        self._elapsed = result.elapsed_s
        if result.error:
            log.write(f"[red]{result.error}[/red]")

        self._running = False
        self._update_status_bar()

    def action_go_back(self) -> None:
        if self._running:
            return
        self.app.pop_screen()

    def action_stop_run(self) -> None:
        if self._running:
            self._cancel_event.set()
