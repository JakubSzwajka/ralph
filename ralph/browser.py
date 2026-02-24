"""Interactive file browser for ralph — uses Textual for keyboard-navigable TUI."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from rich.panel import Panel

from textual import on
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, Static, Tree


@dataclass
class PrdInfo:
    """Information about a discovered PRD directory."""

    slug: str
    """Directory name used as the PRD identifier."""
    title: str
    """H1 heading from the README, or slug if no heading is found."""
    status: str
    """Frontmatter ``status`` field, or ``'unknown'`` if missing/unparseable."""
    path: Path
    """Absolute path to the PRD's README.md."""
    task_files: list[Path] = field(default_factory=list)
    """All ``.md`` files in the PRD directory that are *not* README.md."""
    gh_issue: str | None = None
    """URL of the linked GitHub issue from ``gh-issue`` frontmatter, or ``None``.

    The YAML value ``~`` (null) is normalised to ``None``.  An empty or absent
    ``gh-issue`` key also produces ``None``.
    """


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse simple YAML frontmatter delimited by ``---`` lines.

    Only handles flat ``key: value`` pairs.  Returns an empty dict when
    frontmatter is absent or when the closing delimiter is not found.
    Values are returned as plain strings; surrounding quotes are stripped.
    """
    if not text.startswith("---"):
        return {}

    lines = text.split("\n")
    end_line: int | None = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_line = i
            break

    if end_line is None:
        return {}

    result: dict[str, str] = {}
    for line in lines[1:end_line]:
        line = line.strip()
        if ": " in line:
            key, _, value = line.partition(": ")
            result[key.strip()] = value.strip().strip("\"'")
        elif line.endswith(":"):
            result[line[:-1].strip()] = ""

    return result


def _extract_title(text: str) -> str | None:
    """Return the text of the first H1 heading (``# …``) in *text*, or ``None``."""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def scan_prds(root: Path, prds_dir: Path | None = None) -> list[PrdInfo]:
    """Scan for PRD directories.

    Each sub-directory that contains a ``README.md`` is treated as one PRD.
    YAML frontmatter is read from the README to extract the ``status`` field.
    Missing or malformed frontmatter results in ``status='unknown'``.

    Args:
        root: Project root directory (the directory that contains ``docs/``).
              Used to derive the default scan directory when *prds_dir* is
              ``None``.
        prds_dir: Explicit directory to scan for PRDs.  When ``None`` (the
                  default) the function scans ``root/docs/prds/``.

    Returns:
        A list of :class:`PrdInfo` objects sorted alphabetically by slug.
    """
    if prds_dir is None:
        prds_dir = root / "docs" / "prds"
    if not prds_dir.exists():
        return []

    results: list[PrdInfo] = []
    for readme in sorted(prds_dir.glob("*/README.md")):
        prd_dir = readme.parent
        slug = prd_dir.name

        try:
            text = readme.read_text(encoding="utf-8")
        except OSError:
            continue

        frontmatter = _parse_frontmatter(text)
        title = _extract_title(text) or slug
        status = frontmatter.get("status", "unknown")

        # Normalise gh-issue: treat missing, empty, and YAML null ("~") as None.
        gh_issue_raw = frontmatter.get("gh-issue", "")
        gh_issue: str | None = (
            None if not gh_issue_raw or gh_issue_raw in ("~", "null") else gh_issue_raw
        )

        task_files: list[Path] = sorted(
            f for f in prd_dir.glob("*.md") if f.name.lower() != "readme.md"
        )

        results.append(
            PrdInfo(
                slug=slug,
                title=title,
                status=status,
                path=readme,
                task_files=task_files,
                gh_issue=gh_issue,
            )
        )

    return results


def _status_style(status: str) -> str:
    """Return a Rich markup style name for a PRD status string.

    Returns an empty string for unrecognised statuses so that callers can
    skip wrapping the label in markup tags when no styling is needed.
    """
    return {
        "accepted": "green",
        "in-progress": "yellow",
        "draft": "dim",
    }.get(status, "")


@dataclass
class BrowserResult:
    """Result returned by the RalphBrowser once the user confirms their selection."""

    prd: Path
    tasks: Path | None = None


class PrdSelectionScreen(Screen[PrdInfo | None]):
    """Textual screen for browsing and selecting a PRD.

    Presents a :class:`~textual.widgets.Tree` widget that lists all
    discovered PRDs with colour-coded status badges.  Navigation is
    possible with arrow keys **and** vim-style ``j``/``k`` bindings.
    Pressing Enter (or clicking) on a leaf node dismisses the screen with
    the corresponding :class:`PrdInfo`; pressing Escape dismisses with
    ``None``.
    """

    BINDINGS = [
        ("j", "cursor_down", "Next"),
        ("k", "cursor_up", "Previous"),
        ("escape", "quit_screen", "Quit"),
    ]

    def __init__(self, prds: list[PrdInfo], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._prds = prds

    def compose(self) -> ComposeResult:
        yield Header()
        tree: Tree[PrdInfo] = Tree("Select a PRD", id="prd-tree")
        tree.root.expand()
        for prd in self._prds:
            style = _status_style(prd.status)
            # Show [?] for unknown/malformed frontmatter instead of [unknown]
            display_status = prd.status if prd.status != "unknown" else "?"
            if style:
                badge = f"[{style}][{display_status}][/{style}]"
            else:
                badge = f"[{display_status}]"
            tree.root.add_leaf(f"{prd.title}  {badge}", data=prd)
        yield tree
        yield Footer()

    def action_cursor_down(self) -> None:
        """Move the tree cursor down (vim ``j`` binding)."""
        self.query_one(Tree).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move the tree cursor up (vim ``k`` binding)."""
        self.query_one(Tree).action_cursor_up()

    def action_quit_screen(self) -> None:
        """Dismiss the screen without selecting a PRD."""
        self.dismiss(None)

    @on(Tree.NodeSelected)
    def _on_node_selected(self, event: Tree.NodeSelected[PrdInfo]) -> None:
        """Confirm the highlighted PRD when the user presses Enter or clicks."""
        prd = event.node.data
        if prd is not None:
            self.dismiss(prd)


class ManualPathScreen(Screen[Path | None]):
    """Simple screen with a text input for manually entering a file path.

    Dismisses with the entered :class:`~pathlib.Path` when the user submits,
    or ``None`` when they press Escape or submit an empty string.
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Enter path to tasks file:")
        yield Input(placeholder="e.g. tasks.md", id="path-input")
        yield Footer()

    def on_mount(self) -> None:  # pragma: no cover
        self.query_one(Input).focus()

    def action_cancel(self) -> None:
        """Dismiss without a result."""
        self.dismiss(None)

    @on(Input.Submitted)
    def _on_submitted(self, event: Input.Submitted) -> None:
        """Return the entered path, or ``None`` if the input was blank."""
        value = event.value.strip()
        self.dismiss(Path(value) if value else None)


class NoPrdsFoundScreen(Screen[Path | None]):
    """Screen shown when no PRDs are found in the configured scan directory.

    Displays a "No PRDs found in {dir}" message and offers a text input so
    the user can manually type the path to a PRD README.md file.

    Dismisses with:

    * A :class:`~pathlib.Path` when the user submits a non-empty path.
    * ``None`` when the user presses Escape (signals browser exit).

    Blank submissions are ignored so the user can correct the path without
    accidentally quitting.
    """

    BINDINGS = [("escape", "cancel", "Quit")]

    def __init__(self, prds_dir: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._prds_dir = prds_dir

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"No PRDs found in: {self._prds_dir}", id="no-prds-label")
        yield Label(
            "Enter path to a PRD README.md, or press Escape to quit:",
            id="no-prds-hint",
        )
        yield Input(placeholder="e.g. docs/prds/my-feature/README.md", id="prd-path-input")
        yield Footer()

    def on_mount(self) -> None:  # pragma: no cover
        self.query_one(Input).focus()

    def action_cancel(self) -> None:
        """Dismiss without a result — signals the browser should exit."""
        self.dismiss(None)

    @on(Input.Submitted)
    def _on_submitted(self, event: Input.Submitted) -> None:
        """Return the entered path; ignore blank submissions so user can retry."""
        value = event.value.strip()
        if value:
            self.dismiss(Path(value))
        # Blank submission: stay on screen so the user can correct the path.


class TasksSelectionScreen(Screen[Path | None]):
    """Textual screen for selecting a tasks file for the chosen PRD.

    Lists all task files discovered in the PRD directory and a
    *Browse other…* option that opens :class:`ManualPathScreen`.
    Pressing Escape dismisses with ``None`` to signal "go back".

    Navigation is possible with arrow keys **and** vim-style ``j``/``k``
    bindings.  The first item is pre-selected on mount.
    """

    BINDINGS = [
        ("j", "cursor_down", "Next"),
        ("k", "cursor_up", "Previous"),
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, prd: PrdInfo, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._prd = prd

    def compose(self) -> ComposeResult:
        yield Header()
        tree: Tree[object] = Tree(f"Tasks for: {self._prd.title}", id="tasks-tree")
        tree.root.expand()
        for task_file in self._prd.task_files:
            tree.root.add_leaf(task_file.name, data=task_file)
        tree.root.add_leaf("Browse other…", data="browse")
        yield tree
        yield Footer()

    def on_mount(self) -> None:
        """Pre-select the first item in the tasks tree."""
        tree = self.query_one(Tree)
        children = list(tree.root.children)
        if children:
            tree.move_cursor(children[0])

    def action_cursor_down(self) -> None:
        """Move the tree cursor down (vim ``j`` binding)."""
        self.query_one(Tree).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move the tree cursor up (vim ``k`` binding)."""
        self.query_one(Tree).action_cursor_up()

    def action_go_back(self) -> None:
        """Dismiss the screen without selecting a file (signals go back)."""
        self.dismiss(None)

    @on(Tree.NodeSelected)
    def _on_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle selection of a task file or the *Browse other…* sentinel."""
        data = event.node.data
        if isinstance(data, Path):
            self.dismiss(data)
        elif data == "browse":
            self.app.push_screen(ManualPathScreen(), self._on_manual_path)

    def _on_manual_path(self, path: Path | None) -> None:
        """Callback from :class:`ManualPathScreen`.

        If the user entered a valid path, dismiss this screen with it.
        If they cancelled, stay on this screen so they can pick again.
        """
        if path is not None:
            self.dismiss(path)


class ConfirmationScreen(Screen[bool]):
    """Final confirmation screen before launching the agent loop.

    Displays the selected PRD path, tasks path (or ``"none"``), and an
    optional iteration count in a styled panel.  Two keyboard actions are
    available:

    * **Enter** — confirm the selection (dismisses with ``True``).
    * **Escape** — go back to PRD selection (dismisses with ``False``).
    """

    BINDINGS = [
        ("enter", "confirm", "Start"),
        ("escape", "go_back", "Back"),
    ]

    def __init__(
        self,
        prd: Path,
        tasks: Path | None,
        iterations: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._prd = prd
        self._tasks = tasks
        self._iterations = iterations

    def compose(self) -> ComposeResult:
        yield Header()
        tasks_str = str(self._tasks) if self._tasks else "none"
        lines = [
            f"  PRD:    [bold]{self._prd}[/bold]",
            f"  Tasks:  [bold]{tasks_str}[/bold]",
        ]
        if self._iterations is not None:
            lines.append(f"  Iterations: [bold]{self._iterations}[/bold]")
        panel_content = "\n".join(lines)
        yield Static(
            Panel(panel_content, title="Your Selection", border_style="bright_blue"),
            id="confirm-panel",
        )
        yield Static(
            "\n  Press [bold green]Enter[/bold green] to start"
            " · [bold yellow]Escape[/bold yellow] to go back",
            id="confirm-hint",
        )
        yield Footer()

    def action_confirm(self) -> None:
        """Confirm the selection and proceed."""
        self.dismiss(True)

    def action_go_back(self) -> None:
        """Dismiss without confirming — signals return to PRD selection."""
        self.dismiss(False)


class RalphBrowser(App[BrowserResult | None]):
    """Textual TUI app for interactively selecting PRD and tasks files.

    Returns a :class:`BrowserResult` when the user confirms, or ``None`` when
    the user quits without making a selection.

    Args:
        root: Project root directory used as the base for :func:`scan_prds`.
              Defaults to the current working directory.
    """

    TITLE = "ralph — file browser"
    SUB_TITLE = "Select a PRD and tasks file to begin"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(
        self,
        root: Path | None = None,
        iterations: int | None = None,
        prd_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._root = root or Path.cwd()
        self._iterations = iterations
        self._prd_dir = prd_dir  # None → scan_prds() uses root/docs/prds default
        self._selected_prd: PrdInfo | None = None
        self._selected_tasks: Path | None = None

    def compose(self) -> ComposeResult:  # pragma: no cover
        yield Header()
        yield Label("Loading PRDs…", id="placeholder")
        yield Footer()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _effective_prds_dir(self) -> Path:
        """Return the directory that :func:`scan_prds` will scan.

        Mirrors the fallback logic inside :func:`scan_prds` so that
        :class:`NoPrdsFoundScreen` can display the correct path.
        """
        return self._prd_dir if self._prd_dir is not None else (self._root / "docs" / "prds")

    def _push_prd_screen(self, prds: list[PrdInfo]) -> None:
        """Push the appropriate screen for PRD selection.

        When *prds* is non-empty, pushes :class:`PrdSelectionScreen`.
        When *prds* is empty, pushes :class:`NoPrdsFoundScreen` so the user
        gets a helpful message and an option to enter a path manually instead
        of seeing a blank tree.
        """
        if prds:
            self.push_screen(PrdSelectionScreen(prds), self._on_prd_selected)
        else:
            self.push_screen(
                NoPrdsFoundScreen(self._effective_prds_dir),
                self._on_no_prds_result,
            )

    def _on_no_prds_result(self, path: Path | None) -> None:
        """Callback invoked when :class:`NoPrdsFoundScreen` is dismissed.

        ``None`` means the user pressed Escape — exit the browser.  A
        :class:`~pathlib.Path` means the user supplied a manual PRD path:
        validate that it exists, show an error and re-prompt on failure, or
        proceed to task-file selection on success.
        """
        if path is None:
            self.exit(None)
            return

        if not path.exists():
            self.notify(
                f"File not found: {path}",
                severity="error",
                title="File not found",
            )
            # Re-show the no-PRDs screen so the user can correct the path.
            self.push_screen(
                NoPrdsFoundScreen(self._effective_prds_dir),
                self._on_no_prds_result,
            )
            return

        # Build a minimal PrdInfo for the manually-entered path.
        prd = PrdInfo(
            slug=path.parent.name,
            title=path.parent.name,
            status="unknown",
            path=path,
            task_files=[],
        )
        self._selected_prd = prd
        self.push_screen(TasksSelectionScreen(prd), self._on_tasks_selected)

    # ------------------------------------------------------------------
    # Screen lifecycle callbacks
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        prds = scan_prds(self._root, self._prd_dir)
        self._push_prd_screen(prds)

    def _on_prd_selected(self, prd: PrdInfo | None) -> None:
        """Callback invoked when :class:`PrdSelectionScreen` is dismissed.

        A ``None`` result means the user quit without selecting; we exit the
        app with ``None``.  A valid :class:`PrdInfo` triggers
        :class:`TasksSelectionScreen` for picking the tasks file.

        A race-condition guard checks that the PRD file still exists on disk
        before proceeding.  If it has been deleted since the scan, an error
        notification is shown and the PRD list is refreshed.
        """
        if prd is None:
            self.exit(None)
            return

        # Race-condition guard: the README might have been deleted between the
        # directory scan and the user pressing Enter.
        if not prd.path.exists():
            self.notify(
                f"PRD file no longer exists:\n{prd.path}",
                severity="error",
                title="File not found",
            )
            prds = scan_prds(self._root, self._prd_dir)
            self._push_prd_screen(prds)
            return

        self._selected_prd = prd
        self.push_screen(TasksSelectionScreen(prd), self._on_tasks_selected)

    def _on_tasks_selected(self, tasks: Path | None) -> None:
        """Callback invoked when :class:`TasksSelectionScreen` is dismissed.

        ``None`` means the user pressed Escape to go back to PRD selection.
        A valid :class:`~pathlib.Path` triggers :class:`ConfirmationScreen`.
        """
        if tasks is None:
            # User went back — re-show the PRD selection screen.
            prds = scan_prds(self._root, self._prd_dir)
            self._push_prd_screen(prds)
        else:
            assert self._selected_prd is not None
            self._selected_tasks = tasks
            self.push_screen(
                ConfirmationScreen(
                    prd=self._selected_prd.path,
                    tasks=tasks,
                    iterations=self._iterations,
                ),
                self._on_confirmed,
            )

    def _on_confirmed(self, confirmed: bool) -> None:
        """Callback invoked when :class:`ConfirmationScreen` is dismissed.

        ``True`` means the user pressed Enter to confirm; exit the app with a
        :class:`BrowserResult`.  ``False`` means Escape was pressed; go back
        to the PRD selection screen.
        """
        if confirmed:
            assert self._selected_prd is not None
            self.exit(BrowserResult(prd=self._selected_prd.path, tasks=self._selected_tasks))
        else:
            # Go back to PRD selection.
            prds = scan_prds(self._root, self._prd_dir)
            self._push_prd_screen(prds)

    def action_quit(self) -> None:
        self.exit(None)
