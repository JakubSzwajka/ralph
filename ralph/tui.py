"""Minimal Textual TUI for ralph — PRD browser with two-pane layout."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Footer, Header, Static, Tree

from ralph.browser import PrdInfo, scan_prds
from ralph.core import RalphConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _status_style(status: str) -> str:
    return {
        "accepted": "green",
        "in-progress": "green",
        "draft": "yellow",
        "done": "dim",
    }.get(status, "")


def _status_icon(status: str) -> str:
    return {
        "accepted": "●",
        "in-progress": "◐",
        "draft": "○",
        "done": "✓",
    }.get(status, "?")


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


class PrdTree(Tree[PrdInfo]):
    """Tree widget listing discovered PRDs with status indicators."""

    class PrdSelected(Message):
        def __init__(self, prd: PrdInfo) -> None:
            super().__init__()
            self.prd = prd

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, prds: list[PrdInfo], **kwargs: Any) -> None:
        super().__init__("PRDs", **kwargs)
        self._prds = prds

    def on_mount(self) -> None:
        self.root.expand()
        for prd in self._prds:
            style = _status_style(prd.status)
            icon = _status_icon(prd.status)
            if style:
                label = f"[{style}]{icon}[/{style}] {prd.title}"
            else:
                label = f"{icon} {prd.title}"

            prd_node = self.root.add(label, data=prd)
            for tf in prd.task_files:
                prd_node.add_leaf(f"  {tf.name}", data=prd)

    @on(Tree.NodeSelected)
    def _on_selected(self, event: Tree.NodeSelected[PrdInfo]) -> None:
        if event.node.data is not None:
            self.post_message(self.PrdSelected(event.node.data))


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


TCSS = """
#main {
    width: 1fr;
    height: 1fr;
}

#prd-tree {
    width: 40;
    border-right: solid $primary-background-lighten-2;
}

#content {
    width: 1fr;
    height: 1fr;
    padding: 1 2;
    color: $text-muted;
}
"""


class RalphApp(App[None]):
    """Two-pane TUI: PRD tree on the left, content area on the right."""

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
        prds = scan_prds(self._root, self._prd_dir)
        with Horizontal(id="main"):
            yield PrdTree(prds, id="prd-tree")
            yield Static(
                "Select a PRD to get started",
                id="content",
            )
        yield Footer()

    @on(PrdTree.PrdSelected)
    def _on_prd_selected(self, event: PrdTree.PrdSelected) -> None:
        prd = event.prd
        placeholder = self.query_one("#content", Static)
        lines = [
            f"[bold]{prd.title}[/bold]",
            f"Status: {prd.status}",
            f"Path: {prd.path}",
        ]
        if prd.task_files:
            lines.append(f"Tasks: {', '.join(f.name for f in prd.task_files)}")
        if prd.gh_issue:
            lines.append(f"Issue: {prd.gh_issue}")
        placeholder.update("\n".join(lines))
