from __future__ import annotations

from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Footer, Header, Markdown, Static, Tree

from ralph.browser import DocDir, DocFile, scan_docs
from ralph.browser.scanner import parse_frontmatter
from ralph.core import RalphConfig


class DocTree(Tree[Path]):
    class FileHighlighted(Message):
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, doc_root: DocDir, **kwargs: Any) -> None:
        super().__init__(doc_root.name, **kwargs)
        self._doc_root = doc_root

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
                tree_node.add_leaf(child.path.name, data=child.path)

    @on(Tree.NodeHighlighted)
    def _on_highlighted(self, event: Tree.NodeHighlighted[Path]) -> None:
        if event.node.data is not None:
            self.post_message(self.FileHighlighted(event.node.data))


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
"""


class RalphApp(App[None]):
    TITLE = "ralph"
    SUB_TITLE = ""
    CSS = TCSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        config: RalphConfig | None = None,
        prd_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config
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
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#collection-card").border_title = "Files"
        self.query_one("#detail-card").border_title = "Details"
        self.query_one("#meta-header").display = False
        self.query_one("#md-content").display = False

    def _format_meta_header(self, meta: dict[str, str]) -> str:
        if not meta:
            return ""
        lines = []
        for key, value in meta.items():
            label = key.replace("-", " ").replace("_", " ").title()
            lines.append(f"[bold]{label}:[/bold] {value or '[dim]—[/dim]'}")
        return "  ".join(lines)

    @on(DocTree.FileHighlighted)
    def _on_file_highlighted(self, event: DocTree.FileHighlighted) -> None:
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
