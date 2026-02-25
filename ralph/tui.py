from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Markdown,
    RichLog,
    Static,
    Tree,
)

from ralph.browser import DocDir, DocFile, scan_docs
from ralph.browser.scanner import parse_frontmatter
from ralph.core import IterationResult, RalphConfig, run_ralph


class SelectionChanged(Message):
    def __init__(self, selected: set[Path]) -> None:
        super().__init__()
        self.selected = selected


class FileHighlighted(Message):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path


class DocTree(Tree[Path]):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, doc_root: DocDir, **kwargs: Any) -> None:
        super().__init__(doc_root.name, **kwargs)
        self._doc_root = doc_root
        self.selected: set[Path] = set()

    def on_mount(self) -> None:
        self.root.expand()
        self._build_tree(self.root, self._doc_root)

    def _build_tree(self, tree_node: Any, doc_node: DocDir) -> None:
        for child in doc_node.children:
            if isinstance(child, DocDir):
                branch = tree_node.add(f"[bold]{child.name}/[/bold]", data=None)
                self._build_tree(branch, child)
                branch.expand()
            else:
                label = f"\\[ ] {child.path.name}"
                tree_node.add_leaf(label, data=child.path)

    def _update_node_label(self, node: Any) -> None:
        if node.data is None:
            return
        path = node.data
        check = "\\[x]" if path in self.selected else "\\[ ]"
        node.set_label(f"{check} {path.name}")

    @on(Tree.NodeHighlighted)
    def _on_highlighted(self, event: Tree.NodeHighlighted[Path]) -> None:
        if event.node.data is not None:
            self.post_message(FileHighlighted(event.node.data))

    @on(Tree.NodeSelected)
    def _on_selected(self, event: Tree.NodeSelected[Path]) -> None:
        if event.node.data is not None:
            path = event.node.data
            if path in self.selected:
                self.selected.discard(path)
            else:
                self.selected.add(path)
            self._update_node_label(event.node)
            self.post_message(SelectionChanged(set(self.selected)))


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

    def __init__(self, config: "RalphConfig") -> None:
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
        Binding("q", "quit", "Quit"),
        Binding("r", "start_run", "Run"),
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
        self._running = False

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
        if self._running:
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

        self.push_screen(ConfirmRunScreen(config), callback=self._on_confirm_run)
        self._pending_config = config

    def _on_confirm_run(self, confirmed: bool) -> None:
        if not confirmed:
            return
        config = self._pending_config
        self._running = True
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
            self._running = False
            run_log.write("\n[dim]Run finished.[/dim]")
            self.query_one("#detail-card").border_title = "Details"
