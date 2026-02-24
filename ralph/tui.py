"""Textual TUI app for ralph — persistent interactive session.

Architecture:
    RalphApp          — root App; routes between screens based on config
    BrowserScreen     — PRD browser: PrdTree + task preview + config bar (task 4)
    RunScreen         — 3-pane run screen (task 8 fills in the content)
    SummaryScreen     — completion overlay (task 12 fills in the content)

Widgets:
    PrdTree           — tree view of discovered PRDs with status badges (task 3)
    TaskPanel         — left sidebar showing parsed tasks with live status (task 5)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from rich.markup import escape
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, ListItem, ListView, RichLog, Static, Tree

from ralph.browser import PrdInfo, _parse_frontmatter, scan_prds
from ralph.core import IterationResult, RalphConfig, run_ralph
from ralph.notifier import DiscordNotifier
from ralph.tasks import TaskItem, parse_tasks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prd_status_style(status: str) -> str:
    """Return a Rich markup style name for a PRD status string.

    Colour coding per the TUI control-panel PRD spec:

    * ``accepted`` / ``in-progress`` → ``"green"``  (active / landed)
    * ``draft``                       → ``"yellow"`` (in-planning)
    * ``done``                        → ``"dim"``    (completed)
    * anything else                   → ``""``       (no extra style)
    """
    return {
        "accepted": "green",
        "in-progress": "green",
        "draft": "yellow",
        "done": "dim",
    }.get(status, "")


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


class PrdTree(Tree[PrdInfo]):
    """Tree widget listing all discovered PRDs with color-coded status badges.

    Navigation is possible with arrow keys **and** vim-style ``j``/``k``
    bindings.  Pressing Enter (or clicking) on a PRD node emits a
    :class:`PrdSelected` message so the parent screen can react.

    Args:
        prds: Pre-scanned list of :class:`~ralph.browser.PrdInfo` objects
              to display.  Callers are responsible for scanning the disk
              (e.g. via :func:`~ralph.browser.scan_prds`) before passing
              the list in.
    """

    # ------------------------------------------------------------------
    # Custom message
    # ------------------------------------------------------------------

    class PrdSelected(Message):
        """Posted when the user presses Enter (or clicks) on a PRD leaf node.

        Attributes:
            path: Absolute path to the PRD's ``README.md``.
            slug: Directory name of the PRD (e.g. ``"tui-control-panel"``).
        """

        def __init__(self, path: Path, slug: str) -> None:
            super().__init__()
            self.path = path
            self.slug = slug

    # ------------------------------------------------------------------
    # Keybindings
    # ------------------------------------------------------------------

    BINDINGS = [
        ("j", "cursor_down", "Next"),
        ("k", "cursor_up", "Previous"),
    ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, prds: list[PrdInfo], **kwargs: Any) -> None:
        super().__init__("PRDs", **kwargs)
        self._prds = prds

    def on_mount(self) -> None:
        """Populate the tree with one leaf node per PRD and expand the root."""
        self.root.expand()
        for prd in self._prds:
            style = _prd_status_style(prd.status)
            display_status = prd.status if prd.status != "unknown" else "?"
            # Use a Rich Text object so that the literal "[status]" brackets are
            # rendered as text, not parsed as Rich markup style tags.
            label = Text()
            label.append(f"{prd.slug}  ")
            label.append(f"[{display_status}]", style=style)
            self.root.add_leaf(label, data=prd)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(Tree.NodeSelected)
    def _on_node_selected(self, event: Tree.NodeSelected[PrdInfo]) -> None:  # type: ignore[override]
        """Emit :class:`PrdSelected` when the user activates a PRD leaf node."""
        prd = event.node.data
        if prd is not None:
            self.post_message(self.PrdSelected(path=prd.path, slug=prd.slug))


# ---------------------------------------------------------------------------
# TaskPanel widget (Task 5)
# ---------------------------------------------------------------------------


class TaskPanel(Static):
    """Left sidebar widget showing parsed task progress with live status.

    Renders each task as a styled checkbox line:

    * Completed tasks are shown in **green** with a checkmark (``✓``).
    * The first unchecked task (the *current* task) is highlighted in bold
      with an arrow marker (``▶``).
    * Remaining unchecked tasks are shown dim.

    The :meth:`refresh_tasks` method is the primary public API: call it from
    the post-iteration hook to re-read the tasks file from disk and repaint
    the widget.  No file watchers are involved — updates happen at the natural
    iteration boundary.

    Args:
        tasks: Initial list of :class:`~ralph.tasks.TaskItem` objects.
    """

    DEFAULT_CSS = """
    TaskPanel {
        overflow-y: auto;
        padding: 0 1;
    }
    """

    def __init__(self, tasks: list[TaskItem], **kwargs: Any) -> None:
        self._tasks = tasks
        # Pass rendered content as the initial renderable so Static starts
        # with content rather than being updated in on_mount.
        super().__init__(self._render_tasks(), **kwargs)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_tasks(self) -> str:
        """Return a Rich markup string for the current task list.

        The string is safe to pass to :class:`~textual.widgets.Static` —
        task titles are escaped to prevent them being interpreted as markup.
        """
        if not self._tasks:
            return "[dim]No tasks found[/dim]"

        # Index of the first unchecked task — this is the "current" task.
        first_undone = next(
            (i for i, t in enumerate(self._tasks) if not t.done),
            None,
        )

        lines: list[str] = []
        for i, task in enumerate(self._tasks):
            safe_title = escape(task.title)
            if task.done:
                lines.append(f"[green]✓ {safe_title}[/green]")
            elif i == first_undone:
                lines.append(f"[bold yellow]▶ {safe_title}[/bold yellow]")
            else:
                lines.append(f"[dim]○ {safe_title}[/dim]")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh_tasks(self, path: Path) -> None:
        """Re-parse *path* from disk and repaint the task list.

        Called by the post-iteration hook after each agent iteration so the
        panel reflects any checkboxes the agent may have ticked.

        Args:
            path: Path to the markdown task file (same as ``config.tasks``).
        """
        self._tasks = parse_tasks(path)
        self.update(self._render_tasks())


# ---------------------------------------------------------------------------
# OutputPane widget (Task 6)
# ---------------------------------------------------------------------------


class OutputPane(RichLog):
    """Scrollable output pane for the centre column of the run screen.

    Streams agent output chunk-by-chunk via :meth:`write_chunk`.  Auto-scroll
    stays enabled while the user reads along at the bottom; scrolling up
    manually disables it so the user can read historical output without being
    yanked back to the bottom on each new write.

    The pane supports switching to a *historical* iteration view via
    :meth:`show_iteration` — this replaces the current content with the
    recorded chunks for a past iteration.  :meth:`resume_live` restores the
    live stream.

    Attributes:
        _is_live: ``True`` while showing the current live stream;
                  ``False`` when showing a past iteration's content.
    """

    def __init__(self, **kwargs: Any) -> None:
        # Enable word-wrap and Rich markup so agent output renders nicely.
        kwargs.setdefault("wrap", True)
        kwargs.setdefault("markup", True)
        super().__init__(**kwargs)
        self._is_live: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_chunk(self, text: str) -> None:
        """Append *text* to the log.

        :attr:`~textual.widgets.RichLog.auto_scroll` determines whether the
        view jumps to the bottom after each write.  Auto-scroll is on by
        default and is paused when the user scrolls up (see
        :meth:`on_mouse_scroll_up`).

        Args:
            text: Raw text (may contain Rich markup if the widget was created
                  with ``markup=True``).
        """
        self.write(text)

    def show_iteration(self, chunks: list[str]) -> None:
        """Replace the current content with a *historical* iteration's output.

        Clears the log, disables auto-scroll so the user can read from the
        top, then writes all recorded chunks in order.

        Args:
            chunks: Ordered list of text chunks from the historical iteration.
        """
        self._is_live = False
        self.auto_scroll = False
        self.clear()
        for chunk in chunks:
            self.write(chunk)
        if self.is_mounted:
            self.scroll_home(animate=False)

    def resume_live(self) -> None:
        """Return to the live stream and re-enable auto-scroll.

        Call this when the user wants to follow the current iteration again
        after having browsed a past iteration via :meth:`show_iteration`.
        Also scrolls to the bottom immediately.
        """
        self._is_live = True
        self.auto_scroll = True
        if self.is_mounted:
            self.scroll_end(animate=False)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_mouse_scroll_up(self) -> None:  # noqa: D102
        """Pause auto-scroll when the user manually scrolls up."""
        self.auto_scroll = False


# ---------------------------------------------------------------------------
# IterationList widget (Task 7)
# ---------------------------------------------------------------------------


class IterationList(ListView):
    """Right sidebar listing completed iterations with duration/cost/status.

    Each item shows the iteration number, a status badge (✓ for completed, ●
    for otherwise finished), the wall-clock duration, and the API cost.

    Selecting an item emits :class:`IterationSelected` which the run screen
    uses to swap the output pane to that iteration's recorded output.  The
    ListView's built-in cursor highlight indicates which iteration is being
    viewed.

    Items are appended at runtime via :meth:`add_result`; the list starts
    empty.  The internal ``_results`` list mirrors the ListView items so that
    the iteration number can be recovered from the selection index without
    storing metadata in ``ListItem`` subclasses.
    """

    DEFAULT_CSS = """
    IterationList {
        overflow-y: auto;
    }
    """

    # ------------------------------------------------------------------
    # Custom message
    # ------------------------------------------------------------------

    class IterationSelected(Message):
        """Posted when the user activates an item in the iteration list.

        Attributes:
            iteration: 1-based iteration number of the selected item.
        """

        def __init__(self, iteration: int) -> None:
            super().__init__()
            self.iteration = iteration

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._results: list[IterationResult] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_item(self, result: IterationResult) -> str:
        """Return a Rich markup string for one iteration list item.

        Format example (single line to fit a narrow sidebar)::

            #1 [green]✓[/green] [dim]5.0s $0.0100[/dim]
            #2 [yellow]●[/yellow] [dim]12.3s $0.0050[/dim]

        Args:
            result: The :class:`~ralph.core.IterationResult` to format.

        Returns:
            Rich markup string suitable for a :class:`~textual.widgets.Label`.
        """
        n = result.iteration
        badge = "[green]✓[/green]" if result.is_complete else "[yellow]●[/yellow]"
        duration = f"{result.duration_s:.1f}s"
        cost = f"${result.cost_usd:.4f}"
        return f"[bold]#{n}[/bold] {badge} [dim]{duration} {cost}[/dim]"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_result(self, result: IterationResult) -> None:
        """Append a new iteration result to the sidebar list.

        Creates a :class:`~textual.widgets.ListItem` with a formatted label
        and appends it to the :class:`~textual.widgets.ListView`.  The
        *result* is also stored in ``_results`` so that the selection index
        can be mapped back to an iteration number.

        Args:
            result: The :class:`~ralph.core.IterationResult` to append.
        """
        self._results.append(result)
        self.append(ListItem(Label(self._format_item(result), markup=True)))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(ListView.Selected)
    def _on_list_view_selected(self, event: ListView.Selected) -> None:
        """Translate ``ListView.Selected`` into :class:`IterationSelected`.

        Reads the current cursor index and looks up the corresponding
        :class:`~ralph.core.IterationResult` to extract the iteration number.
        No-ops if the index is out of range (shouldn't happen in practice).
        """
        idx = self.index
        if idx is not None and 0 <= idx < len(self._results):
            self.post_message(self.IterationSelected(self._results[idx].iteration))


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------


class BrowserScreen(Screen[None]):
    """PRD browser — entry point when no PRD is pre-configured.

    Layout (when PRDs are found on disk):

    * **Left pane** — :class:`PrdTree` listing every discovered PRD with a
      colour-coded status badge.
    * **Right pane** — task preview (a :class:`TaskPanel`) that updates when
      the user selects a PRD, plus a config bar at the bottom.
    * **Config bar** — iteration count input, model name input, and a Start
      button (disabled until a PRD is selected).

    When no PRDs are found, a fallback view is shown with a free-text path
    input so the user can point directly at a ``README.md``.

    Args:
        prd_dir: Directory to scan for PRD sub-directories.  When ``None``
                 (the default) the app scans ``cwd/docs/prds/``.
    """

    BINDINGS = [
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self, prd_dir: Path | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._prd_dir = prd_dir
        self._prds: list[PrdInfo] = []
        self._selected_prd: PrdInfo | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_tasks_file(self, prd: PrdInfo) -> Path | None:
        """Return the most relevant tasks file for *prd*.

        Prefers a file named ``tasks.md`` (case-insensitive).  Falls back
        to the first ``.md`` file in :attr:`PrdInfo.task_files` if no
        ``tasks.md`` is present.  Returns ``None`` when there are no
        task files at all.
        """
        for f in prd.task_files:
            if f.name.lower() == "tasks.md":
                return f
        return prd.task_files[0] if prd.task_files else None

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:  # noqa: C901 — intentionally expressive
        yield Header()

        # Scan for PRDs now so we know which layout branch to take.
        self._prds = scan_prds(Path.cwd(), self._prd_dir)

        if self._prds:
            # ── Two-pane browser layout ──────────────────────────────
            with Horizontal(id="browser-main"):
                yield PrdTree(self._prds, id="prd-tree")
                with Vertical(id="preview-pane"):
                    yield TaskPanel([], id="task-preview")
                    with Horizontal(id="config-bar"):
                        yield Label("Iterations: ", classes="config-label")
                        yield Input(
                            "10",
                            id="iterations-input",
                            restrict=r"\d*",
                        )
                        yield Label("  Model: ", classes="config-label")
                        yield Input(
                            "",
                            id="model-input",
                            placeholder="default",
                        )
                        yield Button(
                            "Start →",
                            id="start-button",
                            variant="primary",
                            disabled=True,
                        )
        else:
            # ── No-PRDs fallback ─────────────────────────────────────
            with Vertical(id="no-prds-view"):
                yield Label(
                    "No PRDs found. Enter the path to a PRD file manually:",
                    id="no-prds-label",
                )
                yield Input(
                    "",
                    id="manual-prd-path",
                    placeholder="docs/prds/my-prd/README.md",
                )
                yield Button("Start", id="start-button", variant="primary")

        yield Footer()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(PrdTree.PrdSelected)
    def _on_prd_selected(self, event: PrdTree.PrdSelected) -> None:
        """Update the task preview and enable Start when a PRD is chosen."""
        self._selected_prd = next(
            (p for p in self._prds if p.path == event.path), None
        )
        if self._selected_prd is None:
            return

        # Refresh the task preview panel.
        preview = self.query_one("#task-preview", TaskPanel)
        tasks_file = self._find_tasks_file(self._selected_prd)
        if tasks_file is not None and tasks_file.exists():
            preview.refresh_tasks(tasks_file)
        else:
            # No tasks file — reset to an empty / "no tasks" state.
            preview._tasks = []
            preview.update(preview._render_tasks())

        # Allow the user to kick off a run now that a PRD is chosen.
        self.query_one("#start-button", Button).disabled = False

    @on(Button.Pressed, "#start-button")
    def _on_start_pressed(self) -> None:
        """Build a :class:`~ralph.core.RalphConfig` and push :class:`RunScreen`."""
        # ── Iteration count ──────────────────────────────────────────
        try:
            raw_iters = self.query_one("#iterations-input", Input).value.strip()
            iterations = int(raw_iters) if raw_iters else 10
        except (ValueError, Exception):
            iterations = 10
        iterations = max(1, iterations)  # guard against 0 or negative

        # ── Model (empty string → None → SDK default) ────────────────
        try:
            model_raw = self.query_one("#model-input", Input).value.strip()
            model: str | None = model_raw or None
        except Exception:
            model = None

        # ── PRD and tasks paths ──────────────────────────────────────
        if self._selected_prd is not None:
            prd_path = self._selected_prd.path
            tasks_path = self._find_tasks_file(self._selected_prd)
        else:
            # Manual-path fallback (shown only when no PRDs were discovered).
            try:
                raw_path = self.query_one("#manual-prd-path", Input).value.strip()
                if not raw_path:
                    return  # Nothing to do without a path.
                prd_path = Path(raw_path)
            except Exception:
                return
            tasks_path = None

        config = RalphConfig(
            prd=prd_path,
            tasks=tasks_path,
            iterations=iterations,
            model=model,
        )
        self.app.push_screen(RunScreen(config))


class RunScreen(Screen[None]):
    """Main run screen — three-pane layout: tasks · output · iterations.

    Layout:

    * **Left** — :class:`TaskPanel` (~25 cols): shows parsed tasks from the
      tasks file specified in *config*.
    * **Centre** — :class:`OutputPane` (fluid width): streams agent output.
    * **Right** — :class:`IterationList` (~22 cols): completed iterations.

    Selecting an item in the iteration list swaps the output pane content to
    that iteration's recorded chunks (stored in :attr:`_iteration_outputs`).
    Selecting the current/live iteration calls :meth:`OutputPane.resume_live`.

    Args:
        config: The :class:`~ralph.core.RalphConfig` that describes the run.
    """

    # ── Custom messages (Task 9) ────────────────────────────────────────

    class IterationStarted(Message):
        """Posted when a new agent iteration begins.

        Attributes:
            iteration: 1-based iteration number.
        """

        def __init__(self, iteration: int) -> None:
            super().__init__()
            self.iteration = iteration

    class OutputChunk(Message):
        """Posted for each text chunk streamed from the agent.

        Attributes:
            iteration: 1-based iteration number this chunk belongs to.
            text: The raw text chunk (may contain Rich markup).
        """

        def __init__(self, iteration: int, text: str) -> None:
            super().__init__()
            self.iteration = iteration
            self.text = text

    class IterationCompleted(Message):
        """Posted when an iteration finishes and yields an :class:`IterationResult`.

        Attributes:
            result: The completed iteration's result (metrics, completion flag).
        """

        def __init__(self, result: IterationResult) -> None:
            super().__init__()
            self.result = result

    class RunFinished(Message):
        """Posted when all iterations complete or the run is stopped early.

        Attributes:
            results: Ordered list of all completed iteration results.
        """

        def __init__(self, results: list[IterationResult]) -> None:
            super().__init__()
            self.results = results

    # ── Keybindings ─────────────────────────────────────────────────────

    BINDINGS = [
        # "Pause" shown when running; "Resume" shown when paused.
        # check_action() hides the inactive one from the footer.
        Binding("p,space", "pause_run", "Pause"),
        Binding("p,space", "resume_run", "Resume"),
        Binding("s", "stop_run", "Stop"),
        Binding("q", "app.quit", "Quit"),
    ]

    # ── Lifecycle ───────────────────────────────────────────────────────

    def __init__(self, config: RalphConfig, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = config
        # Maps 1-based iteration number → ordered list of output chunks.
        # Populated by the worker as text arrives; used for iteration switching.
        self._iteration_outputs: dict[int, list[str]] = {}
        # Last known PRD status — used by the post-iteration hook to detect
        # when the PRD transitions to 'done' so the header can be updated.
        self._last_prd_status: str | None = None
        # ── Task 11: run controls ────────────────────────────────────────────
        # asyncio.Event used to pause the worker between iterations.
        # Starts set (running); cleared by action_pause_run, re-set by
        # action_resume_run.  action_stop_run also sets it to unblock the
        # worker so the stop flag can be checked.
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()  # Unpaused by default.
        # True while the run is paused between iterations.
        self._paused: bool = False
        # True after the user requests an early stop.  The worker checks this
        # flag at each iteration boundary and exits cleanly.
        self._stop_requested: bool = False

    def compose(self) -> ComposeResult:
        # Load tasks from disk if a tasks file is configured.
        initial_tasks: list[TaskItem] = []
        if self._config.tasks is not None:
            initial_tasks = parse_tasks(self._config.tasks)

        yield Header()
        with Horizontal(id="run-main"):
            yield TaskPanel(initial_tasks, id="task-panel")
            yield OutputPane(id="output-pane")
            yield IterationList(id="iteration-list")
        yield Footer()

    def on_mount(self) -> None:
        """Start the run worker as soon as the screen is mounted."""
        self._start_run()

    # ── Worker (Task 9) ─────────────────────────────────────────────────

    @work(exclusive=True, exit_on_error=False, name="ralph-run")
    async def _start_run(self) -> None:
        """Consume :func:`~ralph.core.run_ralph` and post messages to drive the TUI.

        This is the bridge between the async agent generator and the Textual
        message system.  Each text chunk becomes an :class:`OutputChunk`
        message; each completed iteration becomes :class:`IterationCompleted`;
        when the loop ends (normally or on early completion) :class:`RunFinished`
        is posted so the run screen can transition to the summary.

        Discord notifications are fired here if the config includes a webhook URL.
        """
        notifier: DiscordNotifier | None = None
        if self._config.discord_notify and self._config.discord_webhook_url:
            notifier = DiscordNotifier(
                webhook_url=self._config.discord_webhook_url,
                min_interval=self._config.discord_min_interval,
            )

        current_iteration: int = 0
        results: list[IterationResult] = []

        async for iteration, item in run_ralph(self._config):
            if isinstance(item, IterationResult):
                results.append(item)
                self.post_message(self.IterationCompleted(item))
                if notifier is not None:
                    await notifier.send(
                        iteration=item.iteration,
                        summary=item.text,
                        cost_usd=item.cost_usd,
                        duration_s=item.duration_s,
                        is_complete=item.is_complete,
                    )
                # Stop if the agent declared completion or the user hit Stop.
                if item.is_complete or self._stop_requested:
                    break
                # ── Task 11: pause between iterations ───────────────────────
                # Blocks here when paused; resumes when pause_event is set
                # by action_resume_run() or action_stop_run().
                await self._pause_event.wait()
                # Re-check stop after being unblocked (user may have pressed
                # Stop while the run was paused).
                if self._stop_requested:
                    break
            else:
                # Text chunk — detect when a new iteration begins.
                if iteration != current_iteration:
                    current_iteration = iteration
                    self.post_message(self.IterationStarted(iteration))
                self.post_message(self.OutputChunk(iteration=iteration, text=item))

        self.post_message(self.RunFinished(results))

    # ── Message handlers (Task 9) ────────────────────────────────────────

    @on(IterationStarted)
    def _on_iteration_started(self, event: IterationStarted) -> None:
        """Clear the output pane and resume live mode when a new iteration begins."""
        pane = self.query_one("#output-pane", OutputPane)
        pane.clear()
        pane.resume_live()

    @on(OutputChunk)
    def _on_output_chunk(self, event: OutputChunk) -> None:
        """Record the chunk for iteration switching and write it to the live pane."""
        # Append to the recorded buffer for this iteration.
        chunks = self._iteration_outputs.setdefault(event.iteration, [])
        chunks.append(event.text)

        # Only write to the pane if the user is viewing the live stream.
        pane = self.query_one("#output-pane", OutputPane)
        if pane._is_live:
            pane.write_chunk(event.text)

    @on(IterationCompleted)
    def _on_iteration_completed(self, event: IterationCompleted) -> None:
        """Add the completed iteration result to the sidebar and run post-iteration hooks.

        Post-iteration hook (Task 10):

        * Re-reads the tasks file from disk and updates the :class:`TaskPanel`
          so any checkboxes ticked by the agent during this iteration are
          immediately visible — no file watcher needed.
        * Re-reads the PRD README frontmatter; if the status has changed to
          ``'done'`` since the last check, the app sub-title is updated to
          surface that information in the header.
        """
        iter_list = self.query_one("#iteration-list", IterationList)
        iter_list.add_result(event.result)

        # ── Task 10: post-iteration disk re-read ────────────────────────────
        # Refresh task panel from disk (no file watcher needed).
        if self._config.tasks is not None:
            self.query_one("#task-panel", TaskPanel).refresh_tasks(self._config.tasks)

        # Re-read PRD frontmatter and surface a 'done' status in the header.
        self._refresh_prd_status()

    def _refresh_prd_status(self) -> None:
        """Re-read PRD README frontmatter and update the app header on status change.

        Called from the post-iteration hook after each completed iteration.
        When the frontmatter ``status`` field transitions to ``'done'``, the
        app's :attr:`~textual.app.App.sub_title` is updated so the user can
        see the project is complete without leaving the run screen.

        Silently no-ops when the PRD file cannot be read (e.g. it was moved).
        No-ops when the status has not changed since the last call.
        """
        try:
            text = self._config.prd.read_text(encoding="utf-8")
        except OSError:
            return

        new_status = _parse_frontmatter(text).get("status", "")
        if new_status == self._last_prd_status:
            return  # No change — nothing to do.

        self._last_prd_status = new_status
        if new_status == "done":
            self.app.sub_title = "autonomous coding agent — PRD done ✓"

    @on(RunFinished)
    def _on_run_finished(self, event: RunFinished) -> None:
        """Push the summary screen when all iterations complete."""
        self.app.push_screen(
            SummaryScreen(config=self._config, results=event.results)
        )

    # ── Iteration switching handler (Task 8) ────────────────────────────

    @on(IterationList.IterationSelected)
    def _on_iteration_selected(self, event: IterationList.IterationSelected) -> None:
        """Swap the output pane to show the selected iteration's output.

        If the selected iteration has recorded chunks, they are displayed via
        :meth:`OutputPane.show_iteration`.  If no chunks are recorded (e.g. the
        selection refers to an iteration in progress), the pane returns to live
        mode via :meth:`OutputPane.resume_live`.
        """
        output_pane = self.query_one("#output-pane", OutputPane)
        chunks = self._iteration_outputs.get(event.iteration)
        if chunks is not None:
            output_pane.show_iteration(chunks)
        else:
            output_pane.resume_live()

    # ── Task 11: run controls ────────────────────────────────────────────

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Show 'Pause' in the footer when running; 'Resume' when paused.

        Textual calls this before firing an action and before rendering the
        footer.  Returning ``None`` hides a binding from the footer and
        prevents the key from triggering that action.

        * ``pause_run``  — visible only while *not* paused.
        * ``resume_run`` — visible only while *paused*.
        * All other actions are always available.
        """
        if action == "pause_run":
            return None if self._paused else True
        if action == "resume_run":
            return True if self._paused else None
        return True

    def action_pause_run(self) -> None:
        """Pause the run between iterations.

        Sets :attr:`_paused` to ``True`` and clears :attr:`_pause_event` so
        the worker will block after the current iteration completes.  The
        footer is refreshed so "Pause" swaps for "Resume".
        """
        self._paused = True
        self._pause_event.clear()
        self.refresh_bindings()

    def action_resume_run(self) -> None:
        """Resume the run after being paused.

        Sets :attr:`_paused` to ``False`` and sets :attr:`_pause_event` so
        the worker unblocks and starts the next iteration.  The footer is
        refreshed so "Resume" swaps back to "Pause".
        """
        self._paused = False
        self._pause_event.set()
        self.refresh_bindings()

    def action_stop_run(self) -> None:
        """Stop the run early after the current iteration.

        Sets the :attr:`_stop_requested` flag so the worker breaks out of the
        loop at the next iteration boundary, and sets :attr:`_pause_event` so
        the worker is unblocked immediately if it is currently paused.  The
        worker will then post :class:`RunFinished` which transitions the app
        to :class:`SummaryScreen`.
        """
        self._stop_requested = True
        self._pause_event.set()  # Unblock the worker if currently paused.


class SummaryScreen(Screen[None]):
    """Completion screen shown after a run finishes or is stopped early.

    Layout (centred panel):

    * **Title** — "Run Complete ✓" or "Run Stopped" depending on whether any
      iteration reported ``is_complete=True``.
    * **Stats** — iteration count, total cost, total wall-clock time, and a
      status badge.
    * **Task snapshot** — the final state of the task file parsed from disk
      (shown when ``config.tasks`` is set and the file exists).
    * **Action hints** — one-line reminder of the keybindings.

    Keybindings:

    * ``r`` — start the same run again (fresh :class:`RunScreen` with the same
      :class:`~ralph.core.RalphConfig`).
    * ``b`` — go back to the PRD browser (:class:`BrowserScreen`).
    * ``q`` — quit the app.

    Args:
        config: The :class:`~ralph.core.RalphConfig` used for the run, or
                ``None`` when not available (e.g. direct construction in tests).
        results: Ordered list of completed iteration results, or ``None``.
    """

    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("r", "run_again", "Run again"),
        ("b", "go_browser", "Browser"),
    ]

    def __init__(
        self,
        config: RalphConfig | None = None,
        results: list[IterationResult] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._results: list[IterationResult] = results if results is not None else []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _render_stats(self) -> str:
        """Return a Rich markup string summarising the run statistics.

        Includes: status badge, iteration count, total cost, and total time.
        Empty results produce an "n/a" placeholder for numeric fields.
        """
        n = len(self._results)
        total_cost = sum(r.cost_usd for r in self._results)
        total_time_s = sum(r.duration_s for r in self._results)
        is_complete = any(r.is_complete for r in self._results)

        status_markup = (
            "[green]✓ Complete[/green]"
            if is_complete
            else "[yellow]● Stopped early[/yellow]"
        )
        if n:
            return (
                f"Status:      {status_markup}\n"
                f"Iterations:  {n}\n"
                f"Total cost:  ${total_cost:.4f}\n"
                f"Total time:  {total_time_s:.1f}s"
            )
        return (
            f"Status:      {status_markup}\n"
            "Iterations:  0\n"
            "Total cost:  $0.0000\n"
            "Total time:  0.0s"
        )

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Render the centred summary panel."""
        is_complete = any(r.is_complete for r in self._results)
        title = "Run Complete ✓" if is_complete else "Run Stopped"

        # Load the final task snapshot from disk if a tasks file is configured.
        final_tasks: list[TaskItem] = []
        if self._config is not None and self._config.tasks is not None:
            final_tasks = parse_tasks(self._config.tasks)

        yield Header()
        with Vertical(id="summary-content"):
            yield Label(title, id="summary-title")
            yield Static(self._render_stats(), id="summary-stats")
            if final_tasks:
                yield TaskPanel(final_tasks, id="summary-tasks")
            yield Static(
                "[bold]r[/bold] Run again  "
                "[bold]b[/bold] PRD browser  "
                "[bold]q[/bold] Quit",
                id="summary-actions",
            )
        yield Footer()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_run_again(self) -> None:
        """Start another run with the same config.

        Pops this :class:`SummaryScreen` and replaces the underlying
        :class:`RunScreen` with a fresh instance using the same
        :class:`~ralph.core.RalphConfig`.  No-ops when ``_config`` is
        ``None`` (e.g. screen constructed without a config in tests).
        """
        if self._config is None:
            return
        # Pop SummaryScreen → back to the RunScreen that pushed us.
        self.app.pop_screen()
        # Replace the old (finished) RunScreen with a brand-new one.
        self.app.switch_screen(RunScreen(self._config))

    def action_go_browser(self) -> None:
        """Navigate back to the PRD browser.

        Pops this :class:`SummaryScreen` and replaces the underlying
        :class:`RunScreen` with a fresh :class:`BrowserScreen` so the user
        can pick a different PRD or re-configure the run.
        """
        # Pop SummaryScreen → back to the RunScreen (or whatever is below).
        self.app.pop_screen()
        # Replace the underlying screen (RunScreen) with a fresh BrowserScreen.
        self.app.switch_screen(BrowserScreen())


# ---------------------------------------------------------------------------
# HistoryScreen (Task 13)
# ---------------------------------------------------------------------------


class HistoryScreen(Screen[None]):
    """History tab — lists past runs from ``.ralph/runs/``.

    Layout (two-pane vertical):

    * **Top** — :class:`~textual.widgets.DataTable` listing all past runs with
      columns: Run ID, PRD, Iterations, Cost, Duration, Status.  Rows are
      sorted newest-first.
    * **Bottom** — detail panel that updates as the user moves the cursor,
      showing full metadata for the highlighted run plus the list of
      iteration JSONL files in that run's directory.

    Navigation:

    * ``escape`` — return to the previous screen (``pop_screen``).
    * Arrow keys — navigate the table; the detail panel updates live.

    Args:
        cwd: Working directory used to resolve ``.ralph/runs/``.  Defaults
             to the current working directory at construction time.
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self, cwd: Path | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cwd = cwd or Path.cwd()
        self._runs: list[dict[str, Any]] = []
        self._runs_dir = self._cwd / ".ralph" / "runs"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_runs(self) -> list[dict[str, Any]]:
        """Scan ``.ralph/runs/`` and return a list of run metadata dicts.

        Each dict is the parsed ``meta.json`` content with an extra
        ``"_run_dir"`` key pointing to the run's directory.  Directories
        with missing or invalid ``meta.json`` are skipped silently.
        Results are sorted newest-first by directory name (which is a
        timestamp slug, so lexicographic descending = chronological
        descending).

        Returns:
            List of metadata dicts, most-recent first.
        """
        runs: list[dict[str, Any]] = []
        if not self._runs_dir.exists():
            return runs
        for run_dir in sorted(self._runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            meta_path = run_dir / "meta.json"
            if not meta_path.exists():
                continue
            try:
                meta: dict[str, Any] = json.loads(
                    meta_path.read_text(encoding="utf-8")
                )
                meta["_run_dir"] = run_dir
                runs.append(meta)
            except (OSError, json.JSONDecodeError):
                pass
        return runs

    @staticmethod
    def _short_prd_name(prd_path: str | None) -> str:
        """Extract a short PRD name from a full path string.

        Walks the path components from right to left and returns the first
        component that is not a README filename.  For example::

            /…/docs/prds/run-history/README.md  →  "run-history"
            None / empty                         →  "—"

        Args:
            prd_path: Full path string from ``meta.json``, or ``None``.

        Returns:
            Short slug string, or ``"—"`` when the path is absent.
        """
        if not prd_path:
            return "—"
        parts = Path(prd_path).parts
        for part in reversed(parts):
            if part.lower() not in {"readme.md", "readme"}:
                return part
        return Path(prd_path).stem

    @staticmethod
    def _status_markup(status: str | None) -> str:
        """Return a Rich markup string for a run status value.

        Args:
            status: Value from the ``"status"`` key of ``meta.json``, or
                    ``None`` when the run is still in progress (no
                    ``completed_at`` key written yet).

        Returns:
            Rich markup string with colour coding:

            * ``"complete"``       → green
            * ``"max-iterations"`` → yellow
            * ``"error"``          → red
            * ``None``             → dim "in-progress"
            * anything else        → dim verbatim text
        """
        if status == "complete":
            return "[green]complete[/green]"
        if status == "max-iterations":
            return "[yellow]max-iter[/yellow]"
        if status == "error":
            return "[red]error[/red]"
        if status is None:
            return "[dim]in-progress[/dim]"
        return f"[dim]{escape(status)}[/dim]"

    def _render_run_detail(self, meta: dict[str, Any]) -> str:
        """Return Rich markup for the detail pane of the given run.

        Shows key metadata fields from ``meta.json`` (run ID, PRD, model,
        permission mode, iteration counts, cost, duration, timestamps, and
        status).  When the run directory is available, also lists the
        iteration JSONL files with their sizes.

        Args:
            meta: Parsed ``meta.json`` dict (with ``"_run_dir"`` key).

        Returns:
            Multi-line Rich markup string suitable for a
            :class:`~textual.widgets.Static` widget.
        """
        lines: list[str] = []

        run_id = meta.get("run_id", "—")
        prd = self._short_prd_name(meta.get("prd"))
        model = meta.get("model") or "default"
        perm = meta.get("permission_mode") or "—"
        iters_req = meta.get("iterations_requested", "—")
        iters_done = meta.get("iterations_completed", "—")
        cost = meta.get("total_cost_usd")
        duration = meta.get("total_duration_s")
        started = str(meta.get("started_at", "—"))
        completed = str(meta.get("completed_at") or "—")
        status = meta.get("status")

        lines.append(f"[bold]Run:[/bold]        {escape(str(run_id))}")
        lines.append(f"[bold]PRD:[/bold]        {escape(str(prd))}")
        lines.append(f"[bold]Model:[/bold]      {escape(str(model))}")
        lines.append(f"[bold]Permission:[/bold] {escape(str(perm))}")
        lines.append(f"[bold]Iterations:[/bold] {iters_done}/{iters_req}")
        if cost is not None:
            lines.append(f"[bold]Cost:[/bold]       ${cost:.4f}")
        if duration is not None:
            lines.append(f"[bold]Duration:[/bold]   {duration:.1f}s")
        lines.append(f"[bold]Started:[/bold]    {escape(started[:19])}")
        lines.append(f"[bold]Completed:[/bold]  {escape(completed[:19])}")
        lines.append(f"[bold]Status:[/bold]     {self._status_markup(status)}")

        # List iteration JSONL files if the run directory is attached.
        run_dir: Path | None = meta.get("_run_dir")
        if run_dir is not None:
            jsonl_files = sorted(run_dir.glob("iteration-*.jsonl"))
            if jsonl_files:
                lines.append("")
                lines.append("[bold]Iteration files:[/bold]")
                for f in jsonl_files:
                    size_kb = f.stat().st_size / 1024
                    lines.append(f"  [dim]{f.name}  ({size_kb:.1f} KB)[/dim]")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the two-pane history layout."""
        yield Header()
        with Vertical(id="history-main"):
            yield DataTable(id="history-table", cursor_type="row")
            yield Static(
                "[dim]No run selected.[/dim]",
                id="history-detail",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Load run history and populate the DataTable."""
        self._runs = self._load_runs()
        table: DataTable[str] = self.query_one("#history-table", DataTable)
        table.add_columns("Run ID", "PRD", "Iterations", "Cost", "Duration", "Status")

        if not self._runs:
            table.add_row("—", "No run history found", "—", "—", "—", "—")
            return

        for meta in self._runs:
            run_id = str(meta.get("run_id", "—"))
            prd = self._short_prd_name(meta.get("prd"))
            iters_done = meta.get("iterations_completed")
            iters_req = meta.get("iterations_requested")
            if iters_done is not None and iters_req is not None:
                iters = f"{iters_done}/{iters_req}"
            elif iters_req is not None:
                iters = f"?/{iters_req}"
            else:
                iters = "—"
            cost = meta.get("total_cost_usd")
            cost_str = f"${cost:.4f}" if cost is not None else "—"
            duration = meta.get("total_duration_s")
            dur_str = f"{duration:.1f}s" if duration is not None else "—"
            status = str(meta.get("status") or "in-progress")
            table.add_row(run_id, prd, iters, cost_str, dur_str, status)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(DataTable.RowHighlighted)
    def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update the detail pane when the cursor moves to a new row.

        This fires on every cursor movement so the detail panel stays in
        sync as the user navigates with arrow keys.
        """
        idx = event.cursor_row
        if 0 <= idx < len(self._runs):
            detail = self._render_run_detail(self._runs[idx])
            self.query_one("#history-detail", Static).update(detail)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


class RalphApp(App[None]):
    """Textual TUI application for ralph.

    If *config* is provided the app goes directly to :class:`RunScreen`;
    otherwise it starts on :class:`BrowserScreen` so the user can pick a PRD
    interactively.

    Args:
        config: Pre-built run configuration, or ``None`` to open the browser.
    """

    TITLE = "ralph"
    SUB_TITLE = "autonomous coding agent"

    # ------------------------------------------------------------------
    # Inline TCSS layout skeleton.
    # Side columns (task panel / iteration list) use fixed widths; the
    # output pane takes the remaining space.  The summary screen centres
    # its content.
    # ------------------------------------------------------------------

    CSS = """
    /* ── BrowserScreen ──────────────────────────────────── two-pane ── */
    BrowserScreen {
        layout: vertical;
    }

    /* Main content row: PrdTree | preview pane */
    BrowserScreen #browser-main {
        height: 1fr;
    }

    /* Left pane: PRD tree */
    BrowserScreen #prd-tree {
        width: 32;
        border-right: solid $primary-darken-2;
    }

    /* Right pane: task preview + config bar stacked vertically */
    BrowserScreen #preview-pane {
        width: 1fr;
        layout: vertical;
    }

    /* Task preview area fills remaining vertical space */
    BrowserScreen #task-preview {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }

    /* Config bar sits at the bottom of the preview pane */
    BrowserScreen #config-bar {
        height: auto;
        padding: 0 1;
        border-top: solid $primary-darken-2;
        align: left middle;
    }

    BrowserScreen .config-label {
        height: auto;
        content-align: left middle;
    }

    BrowserScreen #iterations-input {
        width: 6;
    }

    BrowserScreen #model-input {
        width: 20;
    }

    BrowserScreen #start-button {
        margin-left: 1;
    }

    /* No-PRDs fallback view */
    BrowserScreen #no-prds-view {
        width: 1fr;
        height: 1fr;
        align: center middle;
        padding: 2;
    }

    BrowserScreen #no-prds-label {
        margin-bottom: 1;
    }

    BrowserScreen #manual-prd-path {
        width: 60;
        margin-bottom: 1;
    }

    /* ── RunScreen ──────────────────────────────────────── 3-column ── */
    RunScreen {
        layout: vertical;
    }

    /* Main content row — fills all space between header and footer */
    RunScreen #run-main {
        height: 1fr;
    }

    /* Task panel — left sidebar, fixed width */
    RunScreen #task-panel {
        width: 25;
        border: solid $primary-darken-2;
        overflow-y: auto;
    }

    /* Output pane — fluid centre */
    RunScreen #output-pane {
        width: 1fr;
        border: solid $primary-darken-2;
        overflow-y: auto;
    }

    /* Iteration list — right sidebar, fixed width */
    RunScreen #iteration-list {
        width: 22;
        border: solid $primary-darken-2;
        overflow-y: auto;
    }

    /* ── SummaryScreen ──────────────────────────────────── centred ── */
    SummaryScreen {
        align: center middle;
        layout: vertical;
    }

    /* Centred panel — fixed width so the content doesn't stretch full-screen */
    SummaryScreen #summary-content {
        width: 60;
        height: auto;
        border: round $primary;
        padding: 1 2;
    }

    /* Bold centred title at the top of the panel */
    SummaryScreen #summary-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        width: 1fr;
    }

    /* Stats block — left-aligned key/value pairs */
    SummaryScreen #summary-stats {
        padding-bottom: 1;
    }

    /* Task snapshot — scrollable so it doesn't blow up the panel height */
    SummaryScreen #summary-tasks {
        height: auto;
        max-height: 15;
        overflow-y: auto;
        padding-bottom: 1;
    }

    /* Action hint bar separated from the stats by a horizontal rule */
    SummaryScreen #summary-actions {
        text-align: center;
        padding-top: 1;
        border-top: solid $primary-darken-2;
        width: 1fr;
    }

    /* ── HistoryScreen ───────────────────────────────── two-pane ── */
    HistoryScreen {
        layout: vertical;
    }

    /* Main content area fills all space between header and footer */
    HistoryScreen #history-main {
        height: 1fr;
        layout: vertical;
    }

    /* Runs table occupies the upper portion */
    HistoryScreen #history-table {
        height: 2fr;
        border-bottom: solid $primary-darken-2;
    }

    /* Detail pane shows selected run metadata in the lower portion */
    HistoryScreen #history-detail {
        height: 1fr;
        overflow-y: auto;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("h", "show_history", "History"),
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

    def on_mount(self) -> None:
        """Route to the appropriate starting screen based on *config*."""
        if self._config is not None:
            self.push_screen(RunScreen(self._config))
        else:
            self.push_screen(BrowserScreen(prd_dir=self._prd_dir))

    def action_show_history(self) -> None:
        """Push :class:`HistoryScreen` on top of the current screen.

        No-ops if the history screen is already the active (top-most)
        screen — prevents stacking multiple history screens on the
        screen stack.
        """
        if not isinstance(self.screen, HistoryScreen):
            cwd = self._config.cwd if self._config is not None else Path.cwd()
            self.push_screen(HistoryScreen(cwd=cwd))
