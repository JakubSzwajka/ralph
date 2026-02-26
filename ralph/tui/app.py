from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Markdown, Static

from ralph.browser import scan_docs
from ralph.browser.scanner import parse_frontmatter
from ralph.core import RalphConfig
from ralph.worker import serialize_config
from ralph.core.run_meta import RunMeta, RunStatus, default_runs_dir

from .screens import ConfirmQuitScreen, ConfirmRunScreen, RunBrowserScreen
from .widgets import DocTree, FileHighlighted, SelectionChanged

TCSS = """
#main {
    width: 1fr;
    height: 1fr;
    margin: 1 1;
}

#collection-card {
    width: 40;
    border: round $primary-background-lighten-2;
    border-title-color: $text-muted;
    border-title-align: center;
    padding: 0 1;
}

#doc-tree {
    width: 1fr;
}

#detail-card {
    width: 1fr;
    border: round $primary-background-lighten-2;
    border-title-color: $text-muted;
    border-title-align: center;
    margin-left: 1;
    padding: 0;
    overflow-y: auto;
}

#content {
    width: 1fr;
    padding: 1 2;
    color: $text;
}

#meta-header {
    width: 1fr;
    padding: 1 2;
    background: $primary-background-lighten-1;
    color: $text-muted;
    height: auto;
    max-height: 5;
}

#md-content {
    width: 1fr;
    padding: 1 2;
}

#run-bar {
    height: 5;
    border: round $primary-background-lighten-2;
    border-title-color: $text-muted;
    border-title-align: center;
    margin: 0 1;
    padding: 0 2;
}

#run-bar-inner {
    height: 1fr;
    align: left middle;
}

#selection-count {
    width: auto;
    padding: 0 2;
    color: $text-muted;
}

#iterations-label {
    width: auto;
    padding: 0 1;
    color: $text-muted;
}

#iterations-input {
    width: 8;
}

#run-hint {
    width: auto;
    padding: 0 2;
    color: $text-muted;
}
"""


class RalphApp(App[None]):
    TITLE = "ralph"
    SUB_TITLE = ""
    CSS = TCSS
    BINDINGS = [
        Binding("q", "confirm_quit", "Quit", priority=True),
        Binding("r", "start_run", "Run", priority=True),
        Binding("h", "show_runs", "History"),
    ]

    def __init__(
        self,
        config: RalphConfig | None = None,
        prd_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config or RalphConfig()
        self._prd_dir = prd_dir
        self._root = Path.cwd()

    def compose(self) -> ComposeResult:
        yield Header()
        doc_root = scan_docs(self._root, self._prd_dir)
        with Horizontal(id="main"):
            with Vertical(id="collection-card"):
                yield DocTree(doc_root, id="doc-tree")
            with Vertical(id="detail-card"):
                yield Static("", id="meta-header")
                yield Static("Select a file to view its contents", id="content")
                yield Markdown("", id="md-content")
        with Horizontal(id="run-bar"):
            with Horizontal(id="run-bar-inner"):
                yield Static("0 files selected", id="selection-count")
                yield Static(
                    f"Iterations: {self._config.iterations}", id="iterations-label"
                )
                yield Static("[bold]r[/bold] to run", id="run-hint")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#collection-card").border_title = "Files"
        self.query_one("#detail-card").border_title = "Details"
        self.query_one("#run-bar").border_title = "Run"
        self.query_one("#meta-header").display = False
        self.query_one("#md-content").display = False
        self._cleanup_orphaned_runs()

    def _cleanup_orphaned_runs(self) -> None:
        for run in RunMeta.list_runs(default_runs_dir()):
            if run.status != RunStatus.RUNNING:
                continue
            alive = False
            if run.pid is not None:
                try:
                    os.kill(run.pid, 0)
                    alive = True
                except OSError:
                    pass
            if not alive:
                run.update(default_runs_dir(), status=RunStatus.ERROR)

    def _format_meta_header(self, meta: dict[str, str]) -> str:
        if not meta:
            return ""
        lines = []
        for key, value in meta.items():
            label = key.replace("-", " ").replace("_", " ").title()
            lines.append(f"[bold]{label}:[/bold] {value or '[dim]—[/dim]'}")
        return "  ".join(lines)

    @on(SelectionChanged)
    def _on_selection_changed(self, event: SelectionChanged) -> None:
        count = len(event.selected)
        label = f"{count} file{'s' if count != 1 else ''} selected"
        self.query_one("#selection-count", Static).update(label)

    @on(FileHighlighted)
    def _on_file_highlighted(self, event: FileHighlighted) -> None:
        content_widget = self.query_one("#content", Static)
        md_widget = self.query_one("#md-content", Markdown)
        meta_widget = self.query_one("#meta-header", Static)

        try:
            text = event.path.read_text(encoding="utf-8")
        except OSError:
            text = f"[dim]Cannot read {event.path}[/dim]"

        if event.path.suffix == ".md":
            meta, body = parse_frontmatter(text)
            header = self._format_meta_header(meta)
            meta_widget.update(header)
            meta_widget.display = bool(meta)
            content_widget.display = False
            md_widget.display = True
            md_widget.update(body)
        else:
            meta_widget.display = False
            md_widget.display = False
            content_widget.display = True
            content_widget.update(text)

    def action_confirm_quit(self) -> None:
        active = sum(
            1
            for r in RunMeta.list_runs(default_runs_dir())
            if r.status == RunStatus.RUNNING
        )
        self.push_screen(ConfirmQuitScreen(active), callback=self._on_confirm_quit)  # type: ignore[no-matching-overload]

    def _on_confirm_quit(self, confirmed: bool) -> None:
        if confirmed:
            self.exit()

    def action_show_runs(self) -> None:
        self.push_screen(RunBrowserScreen())

    def action_start_run(self) -> None:
        tree = self.query_one("#doc-tree", DocTree)
        if not tree.selected:
            self.notify(
                "No files selected. Use Space to select files.", severity="warning"
            )
            return

        config = replace(
            self._config,
            context_files=list(tree.selected),
            cwd=self._root,
        )

        self.push_screen(ConfirmRunScreen(config), callback=self._on_confirm_run)  # type: ignore[no-matching-overload]
        self._pending_config = config

    def _on_confirm_run(self, confirmed: bool) -> None:
        if not confirmed:
            return
        self._launch_worker(self._pending_config)

    def _launch_worker(self, config: RalphConfig) -> None:
        config_path = serialize_config(config)

        proc = subprocess.Popen(
            [sys.executable, "-m", "ralph.worker", config_path],
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        run_id = proc.stdout.readline().decode().strip()  # type: ignore[union-attr]
        proc.stdout.close()  # type: ignore[union-attr]

        self.notify(f"Run {run_id} started")
        self.query_one("#run-hint", Static).update(f"Launched [bold]{run_id}[/bold]")
