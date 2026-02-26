from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Markdown, RichLog, Static

from ralph.browser import scan_docs
from ralph.browser.scanner import parse_frontmatter
from ralph.core import IterationResult, RalphConfig, run_ralph

from .screens import ConfirmRunScreen
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

#run-log {
    width: 1fr;
    padding: 1 2;
}
"""


class RalphApp(App[None]):
    TITLE = "ralph"
    SUB_TITLE = ""
    CSS = TCSS
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "start_run", "Run", priority=True),
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
                yield RichLog(id="run-log", wrap=True, markup=True)
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
        self.query_one("#run-log").display = False

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
        run_log = self.query_one("#run-log", RichLog)

        run_log.display = False

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

    def _switch_to_run_log(self) -> None:
        self.query_one("#content", Static).display = False
        self.query_one("#md-content", Markdown).display = False
        self.query_one("#meta-header", Static).display = False
        run_log = self.query_one("#run-log", RichLog)
        run_log.clear()
        run_log.display = True

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
        config = self._pending_config
        self._switch_to_run_log()
        self.query_one("#detail-card").border_title = "Run Output"
        self._execute_run(config)

    @work(exclusive=True)
    async def _execute_run(self, config: RalphConfig) -> None:
        run_log = self.query_one("#run-log", RichLog)
        run_log.write(
            f"[bold magenta]Starting ralph[/bold magenta] — {len(config.context_files)} files, {config.iterations} iterations"
        )
        run_log.write("")

        try:
            async for iteration, item in run_ralph(config):
                if isinstance(item, str):
                    for line in item.splitlines():
                        stripped = line.strip()
                        if stripped:
                            run_log.write(stripped)
                elif isinstance(item, IterationResult):
                    self.query_one("#run-hint", Static).update(
                        f"Running: {item.iteration}/{config.iterations} iterations"
                    )
                    status = (
                        "[green]COMPLETE[/green]"
                        if item.is_complete
                        else "[blue]done[/blue]"
                    )
                    run_log.write(
                        f"\n[bold]Iteration {item.iteration}[/bold] — {item.duration_s:.1f}s — {status}"
                    )
                    run_log.write("")
                    if item.is_complete:
                        break
        except Exception as exc:
            run_log.write(f"\n[red]Error: {exc}[/red]")
        finally:
            run_log.write("\n[dim]Run finished.[/dim]")
            self.query_one("#detail-card").border_title = "Details"
            self.query_one("#run-hint", Static).update("[bold]r[/bold] to run")
