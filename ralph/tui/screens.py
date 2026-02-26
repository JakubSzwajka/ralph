from __future__ import annotations

import asyncio
import os
import signal
import time
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, RichLog, Static

from ralph.core import RalphConfig
from ralph.core.loop import IterationResult, run_ralph
from ralph.core.run_meta import (
    RunMeta,
    RunStatus,
    cleanup_stale_runs,
    default_runs_dir,
    generate_run_id,
)


class ConfirmRunScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    DEFAULT_CSS = """
    ConfirmRunScreen {
        align: center middle;
    }

    #confirm-dialog {
        width: 60;
        height: auto;
        max-height: 20;
        border: round $primary-background-lighten-2;
        border-title-color: $text-muted;
        border-title-align: center;
        background: $surface;
        padding: 1 2;
    }

    #confirm-body {
        width: 1fr;
        height: auto;
        padding: 1 0;
    }

    #confirm-buttons {
        height: 3;
        align: right middle;
    }

    #confirm-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, config: RalphConfig) -> None:
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        c = self._config
        files_list = "\n".join(f"  • {f.name}" for f in c.context_files)
        body = (
            f"[bold]Files:[/bold]\n{files_list}\n\n"
            f"[bold]Iterations:[/bold] {c.iterations}\n"
            f"[bold]Working dir:[/bold] {c.cwd}"
        )
        with Vertical(id="confirm-dialog"):
            yield Static(body, id="confirm-body")
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button("Run", id="run-btn", variant="success")

    def on_mount(self) -> None:
        self.query_one("#confirm-dialog").border_title = "Confirm Run"

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#run-btn")
    def _confirm(self) -> None:
        self.dismiss(True)


class ConfirmQuitScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    DEFAULT_CSS = """
    ConfirmQuitScreen {
        align: center middle;
    }

    #quit-dialog {
        width: 60;
        height: auto;
        border: round $primary-background-lighten-2;
        border-title-color: $text-muted;
        border-title-align: center;
        background: $surface;
        padding: 1 2;
    }

    #quit-body {
        width: 1fr;
        height: auto;
        padding: 1 0;
    }

    #quit-buttons {
        height: 3;
        align: right middle;
    }

    #quit-buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self, active_runs: int = 0) -> None:
        super().__init__()
        self._active_runs = active_runs

    def compose(self) -> ComposeResult:
        if self._active_runs > 0:
            body = (
                f"You have {self._active_runs} active run(s). "
                "Are you sure you want to quit?"
            )
        else:
            body = "Are you sure you want to quit?"
        with Vertical(id="quit-dialog"):
            yield Static(body, id="quit-body")
            with Horizontal(id="quit-buttons"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button("Quit", id="quit-btn", variant="error")

    def on_mount(self) -> None:
        self.query_one("#quit-dialog").border_title = "Confirm Quit"
        self.query_one("#quit-btn", Button).focus()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel-btn")
    def _cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#quit-btn")
    def _confirm(self) -> None:
        self.dismiss(True)


_STATUS_BADGE = {
    RunStatus.DONE: "[green]●[/green]",
    RunStatus.RUNNING: "[blue]●[/blue]",
    RunStatus.ERROR: "[red]●[/red]",
    RunStatus.KILLED: "[yellow]●[/yellow]",
}


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60}s"


class RunBrowserScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "go_back", "Back", priority=True),
        Binding("backspace", "go_back", "Back", show=False, priority=True),
        Binding("k", "kill_run", "Kill"),
    ]

    DEFAULT_CSS = """
    RunBrowserScreen {
        layout: vertical;
    }

    #run-browser-wrap {
        width: 1fr;
        height: 1fr;
        margin: 1 1;
    }

    #run-table-card {
        width: 55;
        height: 1fr;
        border: round $primary-background-lighten-2;
        border-title-color: $text-muted;
        border-title-align: center;
        padding: 0 1;
    }

    #run-right-col {
        width: 1fr;
        height: 1fr;
        margin-left: 1;
    }

    #run-detail-card {
        width: 1fr;
        height: auto;
        max-height: 18;
        border: round $primary-background-lighten-2;
        border-title-color: $text-muted;
        border-title-align: center;
        padding: 1 2;
        overflow-y: auto;
    }

    #run-detail {
        width: 1fr;
        height: auto;
        color: $text-muted;
    }

    #run-log-card {
        width: 1fr;
        height: 1fr;
        border: round $primary-background-lighten-2;
        border-title-color: $text-muted;
        border-title-align: center;
        margin-top: 1;
        padding: 1 2;
        overflow-y: auto;
    }

    #run-log {
        width: 1fr;
        height: auto;
        color: $text-muted;
    }

    #run-hints {
        height: 1;
        dock: bottom;
        padding: 0 2;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="run-browser-wrap"):
            with Vertical(id="run-table-card"):
                yield DataTable(id="run-table", cursor_type="row")
            with Vertical(id="run-right-col"):
                with Vertical(id="run-detail-card"):
                    yield Static("Select a run to view details", id="run-detail")
                with Vertical(id="run-log-card"):
                    yield Static("", id="run-log")
        yield Static("[bold]q[/bold] back  [bold]k[/bold] kill", id="run-hints")

    def on_mount(self) -> None:
        self.query_one("#run-table-card").border_title = "Run History"
        self.query_one("#run-detail-card").border_title = "Details"
        self.query_one("#run-log-card").border_title = "Output Log"
        table = self.query_one("#run-table", DataTable)
        table.add_columns("Status", "Run ID", "Progress", "Duration", "Ctx Files")
        self._runs: list[RunMeta] = []
        self._refresh_runs()
        self.set_interval(1.0, self._refresh_runs)

    def _refresh_runs(self) -> None:
        table = self.query_one("#run-table", DataTable)
        prev_key: str | None = None
        if table.row_count > 0:
            try:
                prev_key = table.coordinate_to_cell_key(
                    table.cursor_coordinate
                ).row_key.value
            except Exception:
                pass

        cleanup_stale_runs(default_runs_dir())
        self._runs = RunMeta.list_runs(default_runs_dir())
        table.clear()
        for run in self._runs:
            badge = _STATUS_BADGE.get(run.status, "?")
            progress = f"{run.iterations_completed}/{run.iterations_requested}"
            duration = _fmt_duration(run.total_duration_s)
            ctx = str(len(run.context_files))
            table.add_row(badge, run.run_id, progress, duration, ctx, key=run.run_id)

        if prev_key and table.row_count > 0:
            for idx, run in enumerate(self._runs):
                if run.run_id == prev_key:
                    table.move_cursor(row=idx)
                    break

    @on(DataTable.RowHighlighted)
    def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value:
            run = next((r for r in self._runs if r.run_id == event.row_key.value), None)
            if run:
                self._update_detail(run)

    def _update_detail(self, run: RunMeta) -> None:
        from pathlib import Path as _Path

        detail = self.query_one("#run-detail", Static)
        badge = _STATUS_BADGE.get(run.status, str(run.status))

        pid_part = f"  [bold]PID:[/bold] {run.pid}" if run.pid else ""
        lines = [
            f"[bold]Run ID:[/bold] {run.run_id}{pid_part}",
            f"[bold]Status:[/bold] {badge} {run.status}",
            f"[bold]Started:[/bold] {run.started_at or '—'}",
            f"[bold]Completed:[/bold] {run.completed_at or '—'}",
            "",
            f"[bold]Model:[/bold] {run.model or '—'}",
            f"[bold]Permission mode:[/bold] {run.permission_mode}",
            f"[bold]PRD:[/bold] {run.prd}",
            f"[bold]Tasks:[/bold] {run.tasks or '—'}",
            f"[bold]Session:[/bold] [dim]{run.session_id or '—'}[/dim]",
            "",
            f"[bold]Iterations:[/bold] {run.iterations_completed}/{run.iterations_requested}",
            f"[bold]Duration:[/bold] {_fmt_duration(run.total_duration_s)}",
        ]

        if run.context_files:
            lines.append("")
            lines.append(f"[bold]Context files:[/bold] ({len(run.context_files)})")
            for f in run.context_files:
                p = _Path(f)
                lines.append(f"  {p.name} [dim]{p.parent}[/dim]")
        else:
            lines.append("")
            lines.append("[bold]Context files:[/bold] —")

        detail.update("\n".join(lines))

        log_widget = self.query_one("#run-log", Static)
        try:
            log_path = default_runs_dir() / run.run_id / "output.log"
            if log_path.is_file():
                text = log_path.read_text(errors="replace")
                log_widget.update(
                    f"[dim]{text}[/dim]" if text.strip() else "[dim]Empty[/dim]"
                )
            else:
                log_widget.update("[dim]No output log[/dim]")
        except Exception:
            log_widget.update("[dim]Could not read log[/dim]")

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_kill_run(self) -> None:
        table = self.query_one("#run-table", DataTable)
        if not self._runs:
            self.app.notify("No runs available", severity="warning")
            return
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        run = next((r for r in self._runs if r.run_id == row_key.value), None)
        if run is None:
            return
        if run.status != RunStatus.RUNNING:
            self.app.notify("Run is not active", severity="warning")
            return
        if run.pid is None:
            self.app.notify("No PID available", severity="warning")
            return
        try:
            os.kill(run.pid, 0)
        except OSError:
            run.update(default_runs_dir(), status=RunStatus.ERROR)
            self.app.notify("Run was already dead, marked as error", severity="warning")
            self._refresh_runs()
            return
        os.kill(run.pid, signal.SIGTERM)
        self.app.notify(f"Sent SIGTERM to run {run.run_id}")
        self._refresh_runs()


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
                    log_file.write(
                        f"\n--- Iteration {item.iteration} done ({item.duration_s:.1f}s) ---\n"
                    )
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
