from __future__ import annotations

from pathlib import Path
from typing import Any

from textual import on
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree

from ralph.browser import DocDir


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
        Binding("space", "toggle_select", "Select", show=False),
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

    def action_toggle_select(self) -> None:
        node = self.cursor_node
        if node is not None and node.data is not None:
            path = node.data
            if path in self.selected:
                self.selected.discard(path)
            else:
                self.selected.add(path)
            self._update_node_label(node)
            self.post_message(SelectionChanged(set(self.selected)))

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
