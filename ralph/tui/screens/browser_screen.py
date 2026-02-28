from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Markdown, Static

from ralph.browser import scan_docs
from ralph.browser.scanner import parse_frontmatter
from ralph.core import RalphConfig
from ralph.core.run_meta import RunMeta, RunStatus, cleanup_stale_runs, default_runs_dir

from ralph.tui.screens.confirm_quit import ConfirmQuitScreen
from ralph.tui.screens.confirm_run import ConfirmRunScreen
from ralph.tui.screens.run_browser import RunBrowserScreen
from ralph.tui.screens.run_screen import RunScreen
from ralph.tui.widgets import DocTree, FileHighlighted, SelectionChanged


class BrowserScreen(Screen[None]):
    BINDINGS = [
        Binding("q", "confirm_quit", "Quit", priority=True),
        Binding("r", "start_run", "Run", priority=True),
        Binding("h", "show_runs", "History"),
    ]

    def __init__(self, config: RalphConfig, prd_dir: Path | None = None) -> None:
        super().__init__()
        self._config = config
        self._prd_dir = prd_dir
        self._root = Path.cwd()
        self._run_active = False

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
        cleanup_stale_runs(default_runs_dir())

    def _update_run_hint(self) -> None:
        hint_widget = self.query_one("#run-hint", Static)
        if self._run_active:
            hint_widget.update("[dim][bold]r[/bold] to run (run active)[/dim]")
        else:
            hint_widget.update("[bold]r[/bold] to run")

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
            header = _format_meta_header(meta)
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
            self.app.exit()

    def action_show_runs(self) -> None:
        self.push_screen(RunBrowserScreen())

    def action_start_run(self) -> None:
        if self._run_active:
            self.notify("A run is already active", severity="warning")
            return

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
        screen = RunScreen(
            config=config,
            context_files=list(config.context_files),
            iterations=config.iterations,
        )
        self._run_active = True
        self._update_run_hint()
        self.push_screen(screen, callback=self._on_run_screen_popped)  # type: ignore[no-matching-overload]

    def _on_run_screen_popped(self) -> None:
        self._run_active = False
        self._update_run_hint()


def _format_meta_header(meta: dict[str, str]) -> str:
    if not meta:
        return ""
    parts: list[str] = []
    for key, value in meta.items():
        label = key.replace("-", " ").replace("_", " ").title()
        parts.append(f"[bold]{label}:[/bold] {value or '[dim]—[/dim]'}")
    return "  ".join(parts)
