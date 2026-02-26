from __future__ import annotations

import os
import signal
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ralph.core.run_meta import (
    RunMeta,
    RunStatus,
    cleanup_stale_runs,
    default_runs_dir,
)

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
                p = Path(f)
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
