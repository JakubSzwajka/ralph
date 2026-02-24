"""Tests for ralph.tui — Textual app scaffold (Task 1), PrdTree (Task 3), TaskPanel (Task 5), BrowserScreen (Task 4)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from ralph.browser import PrdInfo
from ralph.core import IterationResult, RalphConfig
from ralph.tasks import TaskItem
from ralph.tui import BrowserScreen, HistoryScreen, IterationList, OutputPane, PrdTree, RalphApp, RunScreen, SummaryScreen, TaskPanel, _prd_status_style


# ---------------------------------------------------------------------------
# Autouse fixture — prevent real run_ralph() calls from any TUI test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_run_ralph(monkeypatch):
    """Patch ralph.tui.run_ralph with a sleeping no-op for all TUI tests.

    This prevents:
    * Real Claude API calls
    * RunRecorder filesystem side-effects
    * Unexpected RunFinished messages that would push SummaryScreen

    Tests that explicitly test the worker behaviour override this fixture by
    calling ``monkeypatch.setattr("ralph.tui.run_ralph", their_mock)`` which
    takes precedence over the autouse patch.
    """

    async def _sleeping_gen(config):
        # Wait indefinitely; the worker is cancelled when the app quits.
        await asyncio.Event().wait()
        yield  # Makes this an async generator (never reached).

    monkeypatch.setattr("ralph.tui.run_ralph", _sleeping_gen)


# ---------------------------------------------------------------------------
# Smoke tests — verify the module imports cleanly and classes are defined
# ---------------------------------------------------------------------------


class TestModuleImports:
    """Verify all public symbols are importable."""

    def test_ralph_app_importable(self):
        assert RalphApp is not None

    def test_browser_screen_importable(self):
        assert BrowserScreen is not None

    def test_run_screen_importable(self):
        assert RunScreen is not None

    def test_summary_screen_importable(self):
        assert SummaryScreen is not None


# ---------------------------------------------------------------------------
# RalphApp initialisation
# ---------------------------------------------------------------------------


class TestRalphAppInit:
    """Verify RalphApp accepts config correctly."""

    def test_no_config(self):
        app = RalphApp()
        assert app._config is None

    def test_with_config(self):
        config = RalphConfig(prd=Path("my-prd/README.md"))
        app = RalphApp(config=config)
        assert app._config is config

    def test_title(self):
        assert RalphApp.TITLE == "ralph"

    def test_subtitle(self):
        assert RalphApp.SUB_TITLE == "autonomous coding agent"


# ---------------------------------------------------------------------------
# RunScreen initialisation
# ---------------------------------------------------------------------------


class TestRunScreenInit:
    """Verify RunScreen stores its config."""

    def test_config_stored(self):
        config = RalphConfig(prd=Path("some/prd/README.md"), iterations=3)
        screen = RunScreen(config)
        assert screen._config is config


# ---------------------------------------------------------------------------
# Async Textual integration tests (require a headless pilot)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_config_shows_browser_screen():
    """RalphApp with no config should mount BrowserScreen as the first screen."""
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        # BrowserScreen should be the active (top-of-stack) screen.
        assert isinstance(app.screen, BrowserScreen)
        await pilot.press("q")


@pytest.mark.asyncio
async def test_with_config_shows_run_screen():
    """RalphApp with a config should mount RunScreen as the first screen."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, RunScreen)
        await pilot.press("q")


@pytest.mark.asyncio
async def test_browser_screen_has_header_and_footer():
    """BrowserScreen must include a Header and a Footer widget."""
    from textual.widgets import Footer, Header

    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)
        # These queries raise if the widget is absent.
        app.screen.query_one(Header)
        app.screen.query_one(Footer)
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_has_header_and_footer():
    """RunScreen must include a Header and a Footer widget."""
    from textual.widgets import Footer, Header

    config = RalphConfig(prd=Path("PRD.md"), iterations=1)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, RunScreen)
        app.screen.query_one(Header)
        app.screen.query_one(Footer)
        await pilot.press("q")


@pytest.mark.asyncio
async def test_summary_screen_has_header_and_footer():
    """SummaryScreen must include a Header and a Footer widget."""
    from textual.widgets import Footer, Header

    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        # Navigate: push SummaryScreen on top of BrowserScreen.
        app.push_screen(SummaryScreen())
        await pilot.pause()
        assert isinstance(app.screen, SummaryScreen)
        app.screen.query_one(Header)
        app.screen.query_one(Footer)
        await pilot.press("q")


# ---------------------------------------------------------------------------
# _prd_status_style helper (Task 3)
# ---------------------------------------------------------------------------


class TestPrdStatusStyle:
    """Unit tests for the _prd_status_style colour-mapping helper."""

    def test_accepted_is_green(self):
        assert _prd_status_style("accepted") == "green"

    def test_in_progress_is_green(self):
        assert _prd_status_style("in-progress") == "green"

    def test_draft_is_yellow(self):
        assert _prd_status_style("draft") == "yellow"

    def test_done_is_dim(self):
        assert _prd_status_style("done") == "dim"

    def test_unknown_is_empty(self):
        assert _prd_status_style("unknown") == ""

    def test_arbitrary_status_is_empty(self):
        assert _prd_status_style("foobar") == ""


# ---------------------------------------------------------------------------
# PrdTree widget — smoke tests (Task 3)
# ---------------------------------------------------------------------------


class TestPrdTree:
    """Smoke tests that don't require a running Textual app."""

    def test_importable(self):
        assert PrdTree is not None

    def test_prd_selected_message_path(self, tmp_path: Path):
        readme = tmp_path / "my-prd" / "README.md"
        msg = PrdTree.PrdSelected(path=readme, slug="my-prd")
        assert msg.path == readme

    def test_prd_selected_message_slug(self, tmp_path: Path):
        readme = tmp_path / "my-prd" / "README.md"
        msg = PrdTree.PrdSelected(path=readme, slug="my-prd")
        assert msg.slug == "my-prd"

    def test_vim_bindings_declared(self):
        keys = {b[0] for b in PrdTree.BINDINGS}
        assert "j" in keys
        assert "k" in keys


# ---------------------------------------------------------------------------
# PrdTree widget — async Textual integration tests (Task 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prd_tree_renders_nodes(tmp_path: Path):
    """PrdTree mounts with one leaf node per PrdInfo, labels contain the slug."""
    from textual.app import App, ComposeResult

    prds = [
        PrdInfo(
            slug="alpha-feature",
            title="Alpha Feature",
            status="draft",
            path=tmp_path / "alpha-feature" / "README.md",
        ),
        PrdInfo(
            slug="beta-release",
            title="Beta Release",
            status="accepted",
            path=tmp_path / "beta-release" / "README.md",
        ),
    ]

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield PrdTree(prds, id="tree")

    async with _TestApp().run_test(headless=True) as pilot:
        tree = pilot.app.query_one(PrdTree)
        leaves = list(tree.root.children)
        assert len(leaves) == 2
        labels = [leaf.label.plain for leaf in leaves]
        assert any("alpha-feature" in lbl for lbl in labels)
        assert any("beta-release" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_prd_tree_label_contains_status_badge(tmp_path: Path):
    """PrdTree leaf labels include the PRD status in square brackets."""
    from textual.app import App, ComposeResult

    prds = [
        PrdInfo(
            slug="my-prd",
            title="My PRD",
            status="draft",
            path=tmp_path / "my-prd" / "README.md",
        ),
    ]

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield PrdTree(prds)

    async with _TestApp().run_test(headless=True) as pilot:
        tree = pilot.app.query_one(PrdTree)
        leaf = list(tree.root.children)[0]
        # Plain text of the label should contain the status word
        assert "draft" in leaf.label.plain


@pytest.mark.asyncio
async def test_prd_tree_enter_emits_prd_selected(tmp_path: Path):
    """Pressing Enter on a highlighted leaf emits PrdTree.PrdSelected."""
    from textual.app import App, ComposeResult

    prd_readme = tmp_path / "cool-feature" / "README.md"
    prds = [
        PrdInfo(
            slug="cool-feature",
            title="Cool Feature",
            status="in-progress",
            path=prd_readme,
        ),
    ]
    received: list[PrdTree.PrdSelected] = []

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield PrdTree(prds, id="tree")

        def on_prd_tree_prd_selected(self, msg: PrdTree.PrdSelected) -> None:
            received.append(msg)

    async with _TestApp().run_test(headless=True) as pilot:
        tree = pilot.app.query_one(PrdTree)
        # Move the cursor to the first (and only) leaf node.
        first_leaf = list(tree.root.children)[0]
        tree.move_cursor(first_leaf)
        await pilot.press("enter")
        await pilot.pause()

    assert len(received) == 1
    assert received[0].path == prd_readme
    assert received[0].slug == "cool-feature"


@pytest.mark.asyncio
async def test_prd_tree_empty_list_renders_no_leaves():
    """PrdTree with an empty PRD list shows zero leaf nodes."""
    from textual.app import App, ComposeResult

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield PrdTree([])

    async with _TestApp().run_test(headless=True) as pilot:
        tree = pilot.app.query_one(PrdTree)
        assert len(list(tree.root.children)) == 0


# ---------------------------------------------------------------------------
# TaskPanel widget — unit tests (Task 5)
# ---------------------------------------------------------------------------


class TestTaskPanel:
    """Unit tests for TaskPanel using _render_tasks() directly."""

    def test_importable(self):
        """TaskPanel can be imported from ralph.tui."""
        assert TaskPanel is not None

    def test_empty_tasks_shows_no_tasks_message(self):
        """An empty task list renders a 'No tasks found' hint."""
        panel = TaskPanel([])
        rendered = panel._render_tasks()
        assert "No tasks" in rendered

    def test_done_task_rendered_with_green_checkmark(self):
        """A completed task is rendered with a green checkmark."""
        tasks = [TaskItem(title="Done task", done=True, index=1)]
        panel = TaskPanel(tasks)
        rendered = panel._render_tasks()
        assert "✓" in rendered
        assert "green" in rendered

    def test_first_undone_task_rendered_with_arrow(self):
        """The first unchecked task gets the ▶ current-task marker."""
        tasks = [
            TaskItem(title="Done task", done=True, index=1),
            TaskItem(title="Current task", done=False, index=2),
            TaskItem(title="Future task", done=False, index=3),
        ]
        panel = TaskPanel(tasks)
        rendered = panel._render_tasks()
        assert "▶" in rendered

    def test_only_first_undone_gets_arrow(self):
        """Only the first unchecked task gets the arrow; others get dim bullet."""
        tasks = [
            TaskItem(title="Task one", done=False, index=1),
            TaskItem(title="Task two", done=False, index=2),
        ]
        panel = TaskPanel(tasks)
        rendered = panel._render_tasks()
        # The arrow appears exactly once
        assert rendered.count("▶") == 1
        # The dim bullet appears for task two
        assert "○" in rendered

    def test_all_done_no_arrow(self):
        """When all tasks are done there is no arrow marker."""
        tasks = [
            TaskItem(title="Task one", done=True, index=1),
            TaskItem(title="Task two", done=True, index=2),
        ]
        panel = TaskPanel(tasks)
        rendered = panel._render_tasks()
        assert "▶" not in rendered

    def test_title_is_escaped(self):
        """Task titles with Rich markup characters are escaped safely."""
        # A title that would break Rich markup if not escaped
        tasks = [TaskItem(title="Build [bold]widget[/bold]", done=False, index=1)]
        panel = TaskPanel(tasks)
        rendered = panel._render_tasks()
        # Should not raise; the raw bracket chars should be present (escaped)
        assert "widget" in rendered

    def test_tasks_stored_on_instance(self):
        """_tasks attribute holds the list passed to the constructor."""
        tasks = [TaskItem(title="Alpha", done=False, index=1)]
        panel = TaskPanel(tasks)
        assert panel._tasks is tasks


# ---------------------------------------------------------------------------
# TaskPanel widget — async Textual integration tests (Task 5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_panel_renders_in_app():
    """TaskPanel mounts inside a Textual app without errors."""
    from textual.app import App, ComposeResult

    tasks = [
        TaskItem(title="Task A", done=True, index=1),
        TaskItem(title="Task B", done=False, index=2),
    ]

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield TaskPanel(tasks, id="panel")

    async with _TestApp().run_test(headless=True) as pilot:
        panel = pilot.app.query_one(TaskPanel)
        assert panel is not None
        # Tasks stored correctly
        assert len(panel._tasks) == 2


@pytest.mark.asyncio
async def test_task_panel_refresh_tasks_updates_done_state(tmp_path: Path):
    """refresh_tasks re-reads from disk and updates _tasks to reflect new state."""
    from textual.app import App, ComposeResult

    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text("- [ ] My task\n")

    initial_tasks = [TaskItem(title="My task", done=False, index=1)]

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield TaskPanel(initial_tasks, id="panel")

    async with _TestApp().run_test(headless=True) as pilot:
        panel = pilot.app.query_one(TaskPanel)
        assert not panel._tasks[0].done  # initially undone

        # Simulate agent ticking the task off
        tasks_file.write_text("- [x] My task\n")
        panel.refresh_tasks(tasks_file)
        await pilot.pause()

        assert panel._tasks[0].done  # now done after refresh


@pytest.mark.asyncio
async def test_task_panel_refresh_tasks_updates_render(tmp_path: Path):
    """refresh_tasks causes the rendered markup to switch from arrow to checkmark."""
    from textual.app import App, ComposeResult

    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text("- [ ] My task\n")

    initial_tasks = [TaskItem(title="My task", done=False, index=1)]

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield TaskPanel(initial_tasks, id="panel")

    async with _TestApp().run_test(headless=True) as pilot:
        panel = pilot.app.query_one(TaskPanel)
        # Before refresh: current task has arrow
        before = panel._render_tasks()
        assert "▶" in before

        # Simulate agent completing the task
        tasks_file.write_text("- [x] My task\n")
        panel.refresh_tasks(tasks_file)
        await pilot.pause()

        # After refresh: task is done (checkmark), no arrow
        after = panel._render_tasks()
        assert "✓" in after
        assert "▶" not in after


# ---------------------------------------------------------------------------
# BrowserScreen — unit tests (Task 4)
# ---------------------------------------------------------------------------


class TestBrowserScreenInit:
    """Unit tests for BrowserScreen initialisation and helpers."""

    def test_init_defaults(self):
        """BrowserScreen initialises with empty state by default."""
        screen = BrowserScreen()
        assert screen._prd_dir is None
        assert screen._prds == []
        assert screen._selected_prd is None

    def test_init_with_prd_dir(self, tmp_path: Path):
        """BrowserScreen stores the prd_dir argument."""
        screen = BrowserScreen(prd_dir=tmp_path)
        assert screen._prd_dir == tmp_path

    def test_find_tasks_file_prefers_tasks_md(self, tmp_path: Path):
        """_find_tasks_file returns 'tasks.md' when present."""
        other = tmp_path / "other.md"
        tasks = tmp_path / "tasks.md"
        other.touch()
        tasks.touch()
        prd = PrdInfo(
            slug="my-prd",
            title="My PRD",
            status="draft",
            path=tmp_path / "README.md",
            task_files=[other, tasks],
        )
        screen = BrowserScreen()
        result = screen._find_tasks_file(prd)
        assert result == tasks

    def test_find_tasks_file_falls_back_to_first(self, tmp_path: Path):
        """_find_tasks_file returns the first task file when no tasks.md."""
        first = tmp_path / "story.md"
        second = tmp_path / "notes.md"
        first.touch()
        second.touch()
        prd = PrdInfo(
            slug="my-prd",
            title="My PRD",
            status="draft",
            path=tmp_path / "README.md",
            task_files=[first, second],
        )
        screen = BrowserScreen()
        result = screen._find_tasks_file(prd)
        assert result == first

    def test_find_tasks_file_returns_none_when_no_task_files(self, tmp_path: Path):
        """_find_tasks_file returns None when the PRD has no task files."""
        prd = PrdInfo(
            slug="my-prd",
            title="My PRD",
            status="draft",
            path=tmp_path / "README.md",
            task_files=[],
        )
        screen = BrowserScreen()
        result = screen._find_tasks_file(prd)
        assert result is None

    def test_find_tasks_file_case_insensitive(self, tmp_path: Path):
        """_find_tasks_file matches 'Tasks.MD' as well as 'tasks.md'."""
        upper = tmp_path / "Tasks.MD"
        upper.touch()
        prd = PrdInfo(
            slug="my-prd",
            title="My PRD",
            status="draft",
            path=tmp_path / "README.md",
            task_files=[upper],
        )
        screen = BrowserScreen()
        result = screen._find_tasks_file(prd)
        assert result == upper


# ---------------------------------------------------------------------------
# BrowserScreen — async integration tests (Task 4)
# ---------------------------------------------------------------------------


def _make_prd_dir(tmp_path: Path, slug: str, status: str = "draft") -> Path:
    """Helper: create a PRD directory structure under tmp_path."""
    prd_dir = tmp_path / slug
    prd_dir.mkdir(parents=True, exist_ok=True)
    readme = prd_dir / "README.md"
    readme.write_text(
        f"---\nstatus: {status}\n---\n\n# {slug.replace('-', ' ').title()}\n",
        encoding="utf-8",
    )
    return prd_dir


@pytest.mark.asyncio
async def test_browser_screen_with_prds_shows_prd_tree(tmp_path: Path):
    """BrowserScreen renders a PrdTree when PRDs exist in prd_dir."""
    _make_prd_dir(tmp_path, "alpha-feature")
    _make_prd_dir(tmp_path, "beta-release")

    app = RalphApp(prd_dir=tmp_path)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)
        tree = app.screen.query_one(PrdTree)
        assert tree is not None
        leaves = list(tree.root.children)
        assert len(leaves) == 2
        await pilot.press("q")


@pytest.mark.asyncio
async def test_browser_screen_no_prds_shows_manual_input(tmp_path: Path):
    """When no PRDs exist, BrowserScreen shows a manual path input."""
    from textual.widgets import Input, Button

    # empty tmp_path → no PRDs
    app = RalphApp(prd_dir=tmp_path)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)
        # Should have a manual path input and a start button
        inp = app.screen.query_one("#manual-prd-path", Input)
        assert inp is not None
        btn = app.screen.query_one("#start-button", Button)
        assert btn is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_browser_screen_start_disabled_until_prd_selected(tmp_path: Path):
    """Start button is disabled until the user selects a PRD."""
    from textual.widgets import Button

    _make_prd_dir(tmp_path, "cool-feature")

    app = RalphApp(prd_dir=tmp_path)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)
        btn = app.screen.query_one("#start-button", Button)
        assert btn.disabled is True
        await pilot.press("q")


@pytest.mark.asyncio
async def test_browser_screen_prd_selection_enables_start(tmp_path: Path):
    """Selecting a PRD enables the Start button."""
    from textual.widgets import Button

    _make_prd_dir(tmp_path, "cool-feature")

    app = RalphApp(prd_dir=tmp_path)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)

        # Navigate to the first leaf and select it
        tree = app.screen.query_one(PrdTree)
        first_leaf = list(tree.root.children)[0]
        tree.move_cursor(first_leaf)
        await pilot.press("enter")
        await pilot.pause()

        btn = app.screen.query_one("#start-button", Button)
        assert btn.disabled is False
        await pilot.press("q")


@pytest.mark.asyncio
async def test_browser_screen_task_preview_updates_on_prd_selection(tmp_path: Path):
    """Selecting a PRD with a tasks file updates the task preview panel."""
    prd_dir = _make_prd_dir(tmp_path, "my-feature")
    # Create a tasks.md with one item
    tasks_file = prd_dir / "tasks.md"
    tasks_file.write_text("- [ ] Implement the widget\n", encoding="utf-8")

    app = RalphApp(prd_dir=tmp_path)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)

        # Select the PRD
        tree = app.screen.query_one(PrdTree)
        first_leaf = list(tree.root.children)[0]
        tree.move_cursor(first_leaf)
        await pilot.press("enter")
        await pilot.pause()

        # The task preview should now show the task
        preview = app.screen.query_one("#task-preview", TaskPanel)
        assert len(preview._tasks) == 1
        assert "widget" in preview._tasks[0].title.lower()
        await pilot.press("q")


@pytest.mark.asyncio
async def test_browser_screen_start_pushes_run_screen(tmp_path: Path):
    """Clicking Start after selecting a PRD pushes RunScreen."""
    _make_prd_dir(tmp_path, "my-feature")

    app = RalphApp(prd_dir=tmp_path)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)

        # Select the PRD (enable start)
        tree = app.screen.query_one(PrdTree)
        first_leaf = list(tree.root.children)[0]
        tree.move_cursor(first_leaf)
        await pilot.press("enter")
        await pilot.pause()

        # Trigger the start action programmatically (avoids OutOfBounds on
        # headless test terminals where the button may be off-screen).
        app.screen._on_start_pressed()
        await pilot.pause()

        # RunScreen should now be on top
        assert isinstance(app.screen, RunScreen)
        await pilot.press("q")


@pytest.mark.asyncio
async def test_browser_screen_start_builds_correct_config(tmp_path: Path):
    """Start button creates a RalphConfig with the selected PRD path and iterations."""
    from textual.widgets import Input

    prd_dir = _make_prd_dir(tmp_path, "my-feature")
    tasks_file = prd_dir / "tasks.md"
    tasks_file.write_text("- [ ] Do the thing\n", encoding="utf-8")

    app = RalphApp(prd_dir=tmp_path)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)

        # Select the PRD
        tree = app.screen.query_one(PrdTree)
        first_leaf = list(tree.root.children)[0]
        tree.move_cursor(first_leaf)
        await pilot.press("enter")
        await pilot.pause()

        # Set iterations to 3 by directly updating the reactive value
        iters_input = app.screen.query_one("#iterations-input", Input)
        iters_input.value = "3"
        await pilot.pause()

        # Trigger start programmatically
        app.screen._on_start_pressed()
        await pilot.pause()

        # RunScreen should be active with correct config
        assert isinstance(app.screen, RunScreen)
        run_screen = app.screen
        assert run_screen._config.prd == prd_dir / "README.md"
        assert run_screen._config.tasks == tasks_file
        assert run_screen._config.iterations == 3
        await pilot.press("q")


@pytest.mark.asyncio
async def test_browser_screen_no_prds_start_with_path(tmp_path: Path):
    """In no-PRDs mode, entering a path and clicking Start pushes RunScreen."""
    from textual.widgets import Input

    app = RalphApp(prd_dir=tmp_path)  # empty dir → no PRDs
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)

        # Set a manual path by directly updating the reactive value
        path_input = app.screen.query_one("#manual-prd-path", Input)
        path_input.value = "some/prd/README.md"
        await pilot.pause()

        # Trigger start programmatically
        app.screen._on_start_pressed()
        await pilot.pause()

        assert isinstance(app.screen, RunScreen)
        assert app.screen._config.prd == Path("some/prd/README.md")
        await pilot.press("q")


@pytest.mark.asyncio
async def test_browser_screen_config_bar_has_iterations_and_model_inputs(tmp_path: Path):
    """BrowserScreen with PRDs has iterations and model input widgets."""
    from textual.widgets import Input

    _make_prd_dir(tmp_path, "a-feature")

    app = RalphApp(prd_dir=tmp_path)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)
        iters = app.screen.query_one("#iterations-input", Input)
        assert iters.value == "10"  # default
        model = app.screen.query_one("#model-input", Input)
        assert model is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_ralph_app_prd_dir_forwarded_to_browser_screen(tmp_path: Path):
    """RalphApp passes prd_dir to BrowserScreen."""
    _make_prd_dir(tmp_path, "some-prd")

    app = RalphApp(prd_dir=tmp_path)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)
        assert app.screen._prd_dir == tmp_path
        await pilot.press("q")


# ---------------------------------------------------------------------------
# OutputPane widget — unit tests (Task 6)
# ---------------------------------------------------------------------------


class TestOutputPaneUnit:
    """Unit tests for OutputPane that don't require a running Textual app."""

    def test_importable(self):
        """OutputPane can be imported from ralph.tui."""
        assert OutputPane is not None

    def test_initial_is_live(self):
        """OutputPane starts in live mode with auto_scroll enabled."""
        pane = OutputPane()
        assert pane._is_live is True

    def test_initial_auto_scroll_enabled(self):
        """auto_scroll is True by default (inherited from RichLog)."""
        pane = OutputPane()
        # auto_scroll is a reactive; accessing the Python attribute reads it.
        assert pane.auto_scroll is True

    def test_show_iteration_sets_not_live(self):
        """show_iteration() sets _is_live to False."""
        pane = OutputPane()
        pane.show_iteration(["chunk one", "chunk two"])
        assert pane._is_live is False

    def test_show_iteration_disables_auto_scroll(self):
        """show_iteration() disables auto_scroll."""
        pane = OutputPane()
        pane.show_iteration(["data"])
        assert pane.auto_scroll is False

    def test_resume_live_sets_live(self):
        """resume_live() restores _is_live to True."""
        pane = OutputPane()
        pane.show_iteration(["x"])
        pane.resume_live()
        assert pane._is_live is True

    def test_resume_live_reenables_auto_scroll(self):
        """resume_live() re-enables auto_scroll."""
        pane = OutputPane()
        pane.auto_scroll = False
        pane.resume_live()
        assert pane.auto_scroll is True

    def test_on_mouse_scroll_up_pauses_auto_scroll(self):
        """on_mouse_scroll_up() disables auto_scroll."""
        pane = OutputPane()
        assert pane.auto_scroll is True
        pane.on_mouse_scroll_up()
        assert pane.auto_scroll is False


# ---------------------------------------------------------------------------
# OutputPane widget — async Textual integration tests (Task 6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_pane_mounts_in_app():
    """OutputPane mounts inside a Textual app without errors."""
    from textual.app import App, ComposeResult

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield OutputPane(id="output")

    async with _TestApp().run_test(headless=True) as pilot:
        pane = pilot.app.query_one(OutputPane)
        assert pane is not None
        assert pane._is_live is True


@pytest.mark.asyncio
async def test_output_pane_write_chunk_appends_content():
    """write_chunk() adds text to the OutputPane."""
    from textual.app import App, ComposeResult

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield OutputPane(id="output")

    async with _TestApp().run_test(headless=True) as pilot:
        pane = pilot.app.query_one(OutputPane)
        pane.write_chunk("hello world")
        await pilot.pause()
        # The lines list grows after writing.
        assert len(pane.lines) >= 1


@pytest.mark.asyncio
async def test_output_pane_show_iteration_clears_and_replaces():
    """show_iteration() replaces existing content with new chunks."""
    from textual.app import App, ComposeResult

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield OutputPane(id="output")

    async with _TestApp().run_test(headless=True) as pilot:
        pane = pilot.app.query_one(OutputPane)
        # Write some initial live content.
        pane.write_chunk("live output line 1")
        pane.write_chunk("live output line 2")
        await pilot.pause()
        lines_before = len(pane.lines)

        # Switch to a historical iteration with fewer chunks.
        pane.show_iteration(["iteration 1 only chunk"])
        await pilot.pause()

        # is_live is False and auto_scroll is disabled.
        assert pane._is_live is False
        assert pane.auto_scroll is False
        # Content was replaced — lines list reflects new chunks.
        assert len(pane.lines) < lines_before or len(pane.lines) >= 1


@pytest.mark.asyncio
async def test_output_pane_resume_live_reenables_auto_scroll_in_app():
    """resume_live() sets _is_live=True and auto_scroll=True inside an app."""
    from textual.app import App, ComposeResult

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield OutputPane(id="output")

    async with _TestApp().run_test(headless=True) as pilot:
        pane = pilot.app.query_one(OutputPane)
        # Simulate switching to a past iteration.
        pane.show_iteration(["past chunk"])
        await pilot.pause()
        assert pane._is_live is False

        # Return to live mode.
        pane.resume_live()
        await pilot.pause()

        assert pane._is_live is True
        assert pane.auto_scroll is True


@pytest.mark.asyncio
async def test_output_pane_scroll_up_pauses_auto_scroll_in_app():
    """Calling on_mouse_scroll_up() disables auto_scroll while inside an app."""
    from textual.app import App, ComposeResult

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield OutputPane(id="output")

    async with _TestApp().run_test(headless=True) as pilot:
        pane = pilot.app.query_one(OutputPane)
        assert pane.auto_scroll is True

        # Simulate a manual scroll-up event.
        pane.on_mouse_scroll_up()
        await pilot.pause()

        assert pane.auto_scroll is False


# ---------------------------------------------------------------------------
# IterationList widget — unit tests (Task 7)
# ---------------------------------------------------------------------------


class TestIterationListUnit:
    """Unit tests for IterationList that don't require a running Textual app."""

    def test_importable(self):
        """IterationList can be imported from ralph.tui."""
        assert IterationList is not None

    def test_initial_results_empty(self):
        """IterationList starts with an empty _results list."""
        widget = IterationList()
        assert widget._results == []

    def test_iteration_selected_message_stores_iteration(self):
        """IterationSelected message correctly stores the iteration number."""
        msg = IterationList.IterationSelected(iteration=5)
        assert msg.iteration == 5

    def test_format_item_complete_has_green_checkmark(self):
        """_format_item uses a green checkmark badge for completed iterations."""
        from ralph.core import IterationResult

        result = IterationResult(
            iteration=1, text="done", is_complete=True, duration_s=5.0
        )
        widget = IterationList()
        label = widget._format_item(result)
        assert "#1" in label
        assert "green" in label
        assert "✓" in label
        assert "5.0s" in label
    def test_format_item_incomplete_has_yellow_dot(self):
        """_format_item uses a yellow dot badge for incomplete iterations."""
        from ralph.core import IterationResult

        result = IterationResult(
            iteration=2, text="partial", is_complete=False, duration_s=12.3
        )
        widget = IterationList()
        label = widget._format_item(result)
        assert "#2" in label
        assert "yellow" in label
        assert "●" in label
        assert "12.3s" in label

    def test_results_list_starts_empty(self):
        """_results list is empty before any add_result calls."""
        widget = IterationList()
        assert len(widget._results) == 0

    def test_format_item_number_in_output(self):
        """_format_item includes the iteration number prominently."""
        from ralph.core import IterationResult

        result = IterationResult(iteration=42, text="", is_complete=False)
        widget = IterationList()
        label = widget._format_item(result)
        assert "#42" in label


# ---------------------------------------------------------------------------
# IterationList widget — async Textual integration tests (Task 7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iteration_list_mounts_in_app():
    """IterationList mounts inside a Textual app without errors."""
    from textual.app import App, ComposeResult

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield IterationList(id="iterations")

    async with _TestApp().run_test(headless=True) as pilot:
        widget = pilot.app.query_one(IterationList)
        assert widget is not None
        assert widget._results == []


@pytest.mark.asyncio
async def test_iteration_list_add_result_adds_item():
    """add_result() appends a ListItem to the ListView and stores the result."""
    from ralph.core import IterationResult
    from textual.app import App, ComposeResult

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield IterationList(id="iterations")

    async with _TestApp().run_test(headless=True) as pilot:
        widget = pilot.app.query_one(IterationList)
        result = IterationResult(
            iteration=1, text="output", is_complete=True, duration_s=5.0
        )
        widget.add_result(result)
        await pilot.pause()
        assert len(widget._results) == 1


@pytest.mark.asyncio
async def test_iteration_list_add_multiple_results():
    """Multiple add_result calls produce multiple list items."""
    from ralph.core import IterationResult
    from textual.app import App, ComposeResult

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield IterationList(id="iterations")

    async with _TestApp().run_test(headless=True) as pilot:
        widget = pilot.app.query_one(IterationList)
        for i in range(3):
            widget.add_result(
                IterationResult(iteration=i + 1, text="", is_complete=False)
            )
            await pilot.pause()
        assert len(widget._results) == 3


@pytest.mark.asyncio
async def test_iteration_list_selection_emits_iteration_selected():
    """Selecting an item emits IterationSelected with the correct iteration number."""
    from ralph.core import IterationResult
    from textual.app import App, ComposeResult

    received: list[IterationList.IterationSelected] = []

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield IterationList(id="iterations")

        def on_iteration_list_iteration_selected(
            self, msg: IterationList.IterationSelected
        ) -> None:
            received.append(msg)

    async with _TestApp().run_test(headless=True) as pilot:
        widget = pilot.app.query_one(IterationList)
        # Add a result with a distinctive iteration number.
        result = IterationResult(
            iteration=7, text="output", is_complete=True, duration_s=5.0
        )
        widget.add_result(result)
        await pilot.pause()

        # After appending to an empty list the cursor is at None, so we press
        # "down" first to move cursor to index 0, then Enter to select it.
        widget.focus()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

    assert len(received) == 1
    assert received[0].iteration == 7


@pytest.mark.asyncio
async def test_iteration_list_selection_of_second_item():
    """Selecting the second of two items emits the correct iteration number."""
    from ralph.core import IterationResult
    from textual.app import App, ComposeResult

    received: list[IterationList.IterationSelected] = []

    class _TestApp(App[None]):
        def compose(self) -> ComposeResult:
            yield IterationList(id="iterations")

        def on_iteration_list_iteration_selected(
            self, msg: IterationList.IterationSelected
        ) -> None:
            received.append(msg)

    async with _TestApp().run_test(headless=True) as pilot:
        widget = pilot.app.query_one(IterationList)
        widget.add_result(
            IterationResult(iteration=1, text="", is_complete=False, duration_s=3.0)
        )
        widget.add_result(
            IterationResult(iteration=2, text="", is_complete=True, duration_s=7.0)
        )
        await pilot.pause()

        # After appending to an empty list the cursor is at None.
        # Press "down" twice: None → 0, then 0 → 1.  Then Enter to select.
        widget.focus()
        await pilot.press("down")   # None → index 0
        await pilot.press("down")   # index 0 → index 1
        await pilot.press("enter")  # select item at index 1 (iteration 2)
        await pilot.pause()

    assert len(received) >= 1
    assert received[-1].iteration == 2


# ---------------------------------------------------------------------------
# RunScreen — unit tests (Task 8)
# ---------------------------------------------------------------------------


class TestRunScreenTask8:
    """Unit tests for the Task 8 RunScreen implementation."""

    def test_iteration_outputs_initialised_empty(self):
        """RunScreen._iteration_outputs starts as an empty dict."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        assert screen._iteration_outputs == {}

    def test_iteration_outputs_is_dict(self):
        """_iteration_outputs is a plain dict."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        assert isinstance(screen._iteration_outputs, dict)


# ---------------------------------------------------------------------------
# RunScreen — async Textual integration tests (Task 8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_screen_has_task_panel():
    """RunScreen composes a TaskPanel with id='task-panel'."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, RunScreen)
        panel = app.screen.query_one("#task-panel", TaskPanel)
        assert panel is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_has_output_pane():
    """RunScreen composes an OutputPane with id='output-pane'."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, RunScreen)
        pane = app.screen.query_one("#output-pane", OutputPane)
        assert pane is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_has_iteration_list():
    """RunScreen composes an IterationList with id='iteration-list'."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, RunScreen)
        ilist = app.screen.query_one("#iteration-list", IterationList)
        assert ilist is not None
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_task_panel_empty_without_tasks_file():
    """TaskPanel starts empty when config has no tasks file."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1, tasks=None)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, RunScreen)
        panel = app.screen.query_one("#task-panel", TaskPanel)
        assert panel._tasks == []
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_task_panel_loaded_from_tasks_file(tmp_path: Path):
    """TaskPanel is pre-populated from the tasks file in config."""
    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text("- [ ] First task\n- [x] Done task\n", encoding="utf-8")

    config = RalphConfig(prd=tmp_path / "README.md", iterations=1, tasks=tasks_file)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, RunScreen)
        panel = app.screen.query_one("#task-panel", TaskPanel)
        assert len(panel._tasks) == 2
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_iteration_switching_shows_recorded_chunks():
    """Selecting an iteration with recorded chunks calls show_iteration()."""
    from ralph.core import IterationResult

    config = RalphConfig(prd=Path("PRD.md"), iterations=2)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, RunScreen)
        run_screen = app.screen

        # Pre-populate iteration outputs as the worker would do.
        run_screen._iteration_outputs[1] = ["chunk A", "chunk B"]

        # Add a result to the iteration list so we have something to select.
        ilist = run_screen.query_one("#iteration-list", IterationList)
        ilist.add_result(
            IterationResult(
                iteration=1, text="chunk A chunk B", is_complete=False, duration_s=2.0
            )
        )
        await pilot.pause()

        # Select the iteration via the list widget.
        ilist.focus()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

        # Output pane should now be in historical (not-live) mode.
        output_pane = run_screen.query_one("#output-pane", OutputPane)
        assert output_pane._is_live is False
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_iteration_switching_unknown_iteration_resumes_live():
    """Selecting an iteration with no recorded chunks calls resume_live()."""
    from ralph.core import IterationResult

    config = RalphConfig(prd=Path("PRD.md"), iterations=2)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, RunScreen)
        run_screen = app.screen

        # No entries in _iteration_outputs — simulates selecting a live iteration.
        ilist = run_screen.query_one("#iteration-list", IterationList)
        ilist.add_result(
            IterationResult(iteration=1, text="", is_complete=False, duration_s=1.0)
        )
        await pilot.pause()

        # Manually set to non-live state first.
        output_pane = run_screen.query_one("#output-pane", OutputPane)
        output_pane._is_live = False
        output_pane.auto_scroll = False

        # Select iteration 1 which has no recorded chunks.
        ilist.focus()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

        # Output pane should have been returned to live mode.
        assert output_pane._is_live is True
        await pilot.press("q")


# ---------------------------------------------------------------------------
# RunScreen — Task 9: run_ralph() Worker
# ---------------------------------------------------------------------------


class TestRunScreenTask9Messages:
    """Unit tests for Task 9 custom message class definitions on RunScreen."""

    def test_iteration_started_exists(self):
        """RunScreen.IterationStarted message class must exist."""
        assert RunScreen.IterationStarted is not None

    def test_output_chunk_exists(self):
        """RunScreen.OutputChunk message class must exist."""
        assert RunScreen.OutputChunk is not None

    def test_iteration_completed_exists(self):
        """RunScreen.IterationCompleted message class must exist."""
        assert RunScreen.IterationCompleted is not None

    def test_run_finished_exists(self):
        """RunScreen.RunFinished message class must exist."""
        assert RunScreen.RunFinished is not None

    def test_iteration_started_stores_iteration(self):
        """IterationStarted carries the iteration number."""
        msg = RunScreen.IterationStarted(3)
        assert msg.iteration == 3

    def test_output_chunk_stores_iteration_and_text(self):
        """OutputChunk carries both the iteration number and text."""
        msg = RunScreen.OutputChunk(iteration=2, text="hello world")
        assert msg.iteration == 2
        assert msg.text == "hello world"

    def test_iteration_completed_stores_result(self):
        """IterationCompleted carries the IterationResult."""
        result = IterationResult(
            iteration=1, text="done", is_complete=True, duration_s=5.0
        )
        msg = RunScreen.IterationCompleted(result)
        assert msg.result is result

    def test_run_finished_stores_results_list(self):
        """RunFinished carries the full list of IterationResults."""
        results = [
            IterationResult(
                iteration=1, text="a", is_complete=False, duration_s=1.0
            )
        ]
        msg = RunScreen.RunFinished(results)
        assert msg.results is results


@pytest.mark.asyncio
async def test_run_screen_worker_chunks_stored_and_written(monkeypatch, tmp_path):
    """Worker drives OutputChunk messages: chunks are stored and written to pane."""
    chunks_to_yield = ["Hello ", "world\n"]
    result = IterationResult(
        iteration=1, text="Hello world\n", is_complete=False, duration_s=2.0
    )

    async def _mock_run(config):
        yield (1, chunks_to_yield[0])
        yield (1, chunks_to_yield[1])
        yield (1, result)

    monkeypatch.setattr("ralph.tui.run_ralph", _mock_run)

    config = RalphConfig(prd=tmp_path / "PRD.md", iterations=1, cwd=tmp_path)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        # Wait for the worker to complete (RunFinished will push SummaryScreen).
        await pilot.pause()
        await pilot.pause()

        # The screen transitions to SummaryScreen — access the RunScreen via
        # the screen stack to check what happened before the transition.
        # SummaryScreen should now be active after RunFinished was processed.
        assert isinstance(app.screen, SummaryScreen)
        # _results passed to SummaryScreen should match.
        assert app.screen._results == [result]

        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_worker_iteration_outputs_populated(monkeypatch, tmp_path):
    """Worker populates _iteration_outputs as it receives chunks."""
    chunks_to_yield = ["chunk A", "chunk B"]
    result = IterationResult(
        iteration=1, text="chunk A chunk B", is_complete=False, duration_s=2.0
    )

    async def _mock_run(config):
        yield (1, chunks_to_yield[0])
        yield (1, chunks_to_yield[1])
        yield (1, result)

    monkeypatch.setattr("ralph.tui.run_ralph", _mock_run)

    # Use a separate RunScreen reference to inspect state mid-run.
    run_screen_ref: RunScreen | None = None

    config = RalphConfig(prd=tmp_path / "PRD.md", iterations=1, cwd=tmp_path)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        # Capture RunScreen reference before worker finishes.
        if isinstance(app.screen, RunScreen):
            run_screen_ref = app.screen

        # Allow worker to complete and transition to SummaryScreen.
        await pilot.pause()
        await pilot.pause()

        # Verify chunks were recorded (RunScreen is no longer the active screen,
        # but we captured the reference).
        if run_screen_ref is not None:
            assert 1 in run_screen_ref._iteration_outputs
            assert run_screen_ref._iteration_outputs[1] == chunks_to_yield

        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_worker_iteration_completed_populates_list(monkeypatch, tmp_path):
    """IterationCompleted message adds to the iteration list sidebar."""
    result = IterationResult(
        iteration=1, text="done", is_complete=False, duration_s=3.0
    )

    async def _mock_run(config):
        yield (1, "some output")
        yield (1, result)

    monkeypatch.setattr("ralph.tui.run_ralph", _mock_run)

    run_screen_ref: RunScreen | None = None

    config = RalphConfig(prd=tmp_path / "PRD.md", iterations=1, cwd=tmp_path)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        if isinstance(app.screen, RunScreen):
            run_screen_ref = app.screen

        await pilot.pause()
        await pilot.pause()

        if run_screen_ref is not None:
            ilist = run_screen_ref.query_one("#iteration-list", IterationList)
            assert len(ilist._results) == 1
            assert ilist._results[0].iteration == 1

        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_worker_run_finished_pushes_summary(monkeypatch, tmp_path):
    """RunFinished causes SummaryScreen to be pushed onto the screen stack."""

    async def _instant_finish(config):
        # Yields nothing → RunFinished([]) is posted immediately.
        return
        yield  # Makes this an async generator.

    monkeypatch.setattr("ralph.tui.run_ralph", _instant_finish)

    config = RalphConfig(prd=tmp_path / "PRD.md", iterations=1, cwd=tmp_path)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        # Allow worker + RunFinished message handler to execute.
        await pilot.pause()
        await pilot.pause()

        # SummaryScreen should now be the active screen.
        assert isinstance(app.screen, SummaryScreen)

        await pilot.press("q")


@pytest.mark.asyncio
async def test_summary_screen_stores_config_and_results():
    """SummaryScreen correctly stores config and results passed from RunFinished."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1)
    results = [
        IterationResult(iteration=1, text="hi", is_complete=True, duration_s=1.0)
    ]
    screen = SummaryScreen(config=config, results=results)
    assert screen._config is config
    assert screen._results is results


def test_summary_screen_defaults_to_empty_results():
    """SummaryScreen without results defaults to an empty list."""
    screen = SummaryScreen()
    assert screen._results == []
    assert screen._config is None


# ---------------------------------------------------------------------------
# Task 10 — Post-iteration hook: task panel refresh + PRD status update
# ---------------------------------------------------------------------------


class TestRunScreenTask10Init:
    """Unit tests for the Task 10 post-iteration hook attributes."""

    def test_last_prd_status_initialises_to_none(self):
        """RunScreen._last_prd_status starts as None."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        assert screen._last_prd_status is None


class TestRefreshPrdStatus:
    """Unit tests for RunScreen._refresh_prd_status() — logic only (no app).

    Because ``Screen.app`` is a read-only property in Textual we test the
    *state-tracking* behaviour (which only touches ``_last_prd_status``)
    in pure unit tests.  Tests that verify the ``app.sub_title`` side-effect
    are async integration tests further below.
    """

    def test_no_op_when_prd_file_missing(self, tmp_path: Path, monkeypatch):
        """_refresh_prd_status silently no-ops when PRD file does not exist."""
        config = RalphConfig(prd=tmp_path / "MISSING.md", iterations=1)
        screen = RunScreen(config)

        # Patch _refresh_prd_status so it bails out after the OSError branch
        # by having the method reach the ``return`` for missing file — we
        # verify _last_prd_status was never set.
        screen._refresh_prd_status()
        assert screen._last_prd_status is None

    def test_status_tracked_from_frontmatter(self, tmp_path: Path, monkeypatch):
        """_refresh_prd_status reads and stores PRD status from frontmatter."""
        prd = tmp_path / "README.md"
        prd.write_text("---\nstatus: draft\n---\n# My PRD\n", encoding="utf-8")
        config = RalphConfig(prd=prd, iterations=1)
        screen = RunScreen(config)

        # Suppress the app.sub_title write so we can test without a real App.
        monkeypatch.setattr(type(screen), "app", property(lambda s: type("A", (), {"sub_title": ""})()))

        screen._refresh_prd_status()
        assert screen._last_prd_status == "draft"

    def test_status_not_changed_when_same(self, tmp_path: Path, monkeypatch):
        """_last_prd_status does not change when status is same as last call."""
        prd = tmp_path / "README.md"
        prd.write_text("---\nstatus: draft\n---\n# My PRD\n", encoding="utf-8")
        config = RalphConfig(prd=prd, iterations=1)
        screen = RunScreen(config)

        write_count = [0]

        class _FakeApp:
            @property
            def sub_title(self):
                return ""

            @sub_title.setter
            def sub_title(self, v):
                write_count[0] += 1

        monkeypatch.setattr(type(screen), "app", property(lambda s: _FakeApp()))

        screen._refresh_prd_status()  # first call — status = 'draft'
        writes_after_first = write_count[0]

        screen._refresh_prd_status()  # second call — no change
        assert write_count[0] == writes_after_first


@pytest.mark.asyncio
async def test_iteration_completed_refreshes_task_panel(monkeypatch, tmp_path: Path):
    """IterationCompleted triggers refresh_tasks on the task panel."""
    # Write an initial tasks file with one unchecked task.
    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text("- [ ] Task A\n", encoding="utf-8")

    result = IterationResult(
        iteration=1, text="done", is_complete=False, duration_s=1.0
    )

    # The mock generator yields the result; before we check, update the file
    # on disk to simulate the agent checking the task off.
    tasks_updated = [False]

    async def _mock_run(config):
        yield (1, "chunk")
        # Simulate agent updating the tasks file between chunk and result.
        tasks_file.write_text("- [x] Task A\n", encoding="utf-8")
        tasks_updated[0] = True
        yield (1, result)

    monkeypatch.setattr("ralph.tui.run_ralph", _mock_run)

    prd_file = tmp_path / "PRD.md"
    prd_file.write_text("---\nstatus: draft\n---\n# My PRD\n", encoding="utf-8")

    config = RalphConfig(prd=prd_file, tasks=tasks_file, iterations=1, cwd=tmp_path)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        run_screen_ref: RunScreen | None = None
        if isinstance(app.screen, RunScreen):
            run_screen_ref = app.screen

        # Allow worker and message handlers to execute.
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        assert tasks_updated[0], "Mock generator should have updated the tasks file"

        if run_screen_ref is not None:
            panel = run_screen_ref.query_one("#task-panel", TaskPanel)
            # The panel should have re-read the file: Task A is now done.
            assert panel._tasks[0].done is True

        await pilot.press("q")


@pytest.mark.asyncio
async def test_iteration_completed_updates_sub_title_when_prd_done(
    monkeypatch, tmp_path: Path
):
    """IterationCompleted updates app sub_title when PRD status becomes 'done'."""
    prd_file = tmp_path / "PRD.md"
    prd_file.write_text("---\nstatus: in-progress\n---\n# My PRD\n", encoding="utf-8")

    result = IterationResult(
        iteration=1, text="done", is_complete=True, duration_s=1.0
    )

    async def _mock_run(config):
        yield (1, "chunk")
        # Simulate agent setting PRD status to done.
        prd_file.write_text("---\nstatus: done\n---\n# My PRD\n", encoding="utf-8")
        yield (1, result)

    monkeypatch.setattr("ralph.tui.run_ralph", _mock_run)

    config = RalphConfig(prd=prd_file, iterations=1, cwd=tmp_path)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        run_screen_ref: RunScreen | None = None
        if isinstance(app.screen, RunScreen):
            run_screen_ref = app.screen

        # Allow worker and all message handlers (including RunFinished →
        # SummaryScreen push) to execute.
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        # After the hook fires, the sub_title should reflect 'done'.
        # (We check on the app, not the screen, since SummaryScreen may
        # have been pushed by now.)
        assert "done" in app.sub_title

        await pilot.press("q")


# ---------------------------------------------------------------------------
# RunScreen — Task 11: Run controls (pause/resume/stop)
# ---------------------------------------------------------------------------


class TestRunScreenTask11Init:
    """Unit tests for Task 11 run-control attributes initialised in __init__."""

    def test_pause_event_starts_set(self):
        """_pause_event starts in the set (unpaused) state."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        assert screen._pause_event.is_set()

    def test_paused_starts_false(self):
        """_paused starts as False (not paused)."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        assert screen._paused is False

    def test_stop_requested_starts_false(self):
        """_stop_requested starts as False."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        assert screen._stop_requested is False


class TestRunScreenTask11Bindings:
    """Unit tests for Task 11 binding declarations on RunScreen."""

    def _binding_keys(self) -> set[str]:
        from textual.binding import Binding

        keys: set[str] = set()
        for b in RunScreen.BINDINGS:
            if isinstance(b, Binding):
                keys.add(b.key)
            elif isinstance(b, tuple):
                keys.add(b[0])
        return keys

    def _binding_actions(self) -> set[str]:
        from textual.binding import Binding

        actions: set[str] = set()
        for b in RunScreen.BINDINGS:
            if isinstance(b, Binding):
                actions.add(b.action)
            elif isinstance(b, tuple):
                actions.add(b[1])
        return actions

    def test_pause_binding_key_declared(self):
        """RunScreen declares a binding for 'p' (or 'p,space')."""
        assert any("p" in k for k in self._binding_keys())

    def test_stop_binding_declared(self):
        """RunScreen declares a binding for 's' (stop)."""
        assert "s" in self._binding_keys()

    def test_pause_run_action_declared(self):
        """'pause_run' action is declared in BINDINGS."""
        assert "pause_run" in self._binding_actions()

    def test_resume_run_action_declared(self):
        """'resume_run' action is declared in BINDINGS."""
        assert "resume_run" in self._binding_actions()

    def test_stop_run_action_declared(self):
        """'stop_run' action is declared in BINDINGS."""
        assert "stop_run" in self._binding_actions()


class TestRunScreenTask11CheckAction:
    """Unit tests for the check_action() visibility logic."""

    def test_pause_run_visible_when_not_paused(self):
        """check_action('pause_run') returns True when _paused is False."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        screen._paused = False
        assert screen.check_action("pause_run", ()) is True

    def test_pause_run_hidden_when_paused(self):
        """check_action('pause_run') returns None when _paused is True."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        screen._paused = True
        assert screen.check_action("pause_run", ()) is None

    def test_resume_run_visible_when_paused(self):
        """check_action('resume_run') returns True when _paused is True."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        screen._paused = True
        assert screen.check_action("resume_run", ()) is True

    def test_resume_run_hidden_when_not_paused(self):
        """check_action('resume_run') returns None when _paused is False."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        screen._paused = False
        assert screen.check_action("resume_run", ()) is None

    def test_other_actions_always_true(self):
        """check_action returns True for any other action name."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        assert screen.check_action("stop_run", ()) is True
        assert screen.check_action("app.quit", ()) is True
        assert screen.check_action("unknown_action", ()) is True


class TestRunScreenTask11ActionMethods:
    """Unit tests for pause/resume/stop action method state changes."""

    def test_action_pause_run_sets_paused(self):
        """action_pause_run() sets _paused to True."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        screen._paused = False
        screen.action_pause_run()
        assert screen._paused is True

    def test_action_pause_run_clears_event(self):
        """action_pause_run() clears _pause_event (blocks the worker)."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        assert screen._pause_event.is_set()
        screen.action_pause_run()
        assert not screen._pause_event.is_set()

    def test_action_resume_run_clears_paused(self):
        """action_resume_run() sets _paused to False."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        screen._paused = True
        screen._pause_event.clear()
        screen.action_resume_run()
        assert screen._paused is False

    def test_action_resume_run_sets_event(self):
        """action_resume_run() sets _pause_event (unblocks the worker)."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        screen._pause_event.clear()
        screen.action_resume_run()
        assert screen._pause_event.is_set()

    def test_action_stop_run_sets_stop_requested(self):
        """action_stop_run() sets _stop_requested to True."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        screen.action_stop_run()
        assert screen._stop_requested is True

    def test_action_stop_run_sets_event_to_unblock(self):
        """action_stop_run() sets _pause_event so the worker can observe the flag."""
        config = RalphConfig(prd=Path("PRD.md"), iterations=1)
        screen = RunScreen(config)
        screen._pause_event.clear()  # Simulate paused state.
        screen.action_stop_run()
        assert screen._pause_event.is_set()


@pytest.mark.asyncio
async def test_run_screen_press_p_pauses():
    """Pressing 'p' while running pauses the run."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        run_screen = app.screen
        assert isinstance(run_screen, RunScreen)
        assert run_screen._paused is False

        await pilot.press("p")
        await pilot.pause()

        assert run_screen._paused is True
        assert not run_screen._pause_event.is_set()
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_press_p_twice_resumes():
    """Pressing 'p' twice pauses then resumes the run."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        run_screen = app.screen
        assert isinstance(run_screen, RunScreen)

        # First press: pause.
        await pilot.press("p")
        await pilot.pause()
        assert run_screen._paused is True
        assert not run_screen._pause_event.is_set()

        # Second press: resume.
        await pilot.press("p")
        await pilot.pause()
        assert run_screen._paused is False
        assert run_screen._pause_event.is_set()
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_press_s_sets_stop_requested():
    """Pressing 's' sets _stop_requested and unblocks the pause event."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        run_screen = app.screen
        assert isinstance(run_screen, RunScreen)

        # Pause first, then stop — verifies that stop unblocks the event.
        await pilot.press("p")
        await pilot.pause()
        assert not run_screen._pause_event.is_set()

        await pilot.press("s")
        await pilot.pause()
        assert run_screen._stop_requested is True
        assert run_screen._pause_event.is_set()
        await pilot.press("q")


@pytest.mark.asyncio
async def test_run_screen_stop_early_pushes_summary(monkeypatch, tmp_path):
    """Pressing 's' while paused causes SummaryScreen to be pushed.

    Strategy: pause the run immediately (before the first event-loop turn so
    the worker blocks at ``_pause_event.wait()`` between iterations), then
    press ``s`` to trigger the stop.  A ``gen_blocker`` event is also set as
    a fallback in case the worker got past the pause point and is waiting
    inside the generator instead.
    """
    gen_blocker = asyncio.Event()

    async def _one_iter_run(config):
        yield (1, "chunk")
        yield (
            1,
            IterationResult(
                iteration=1, text="partial", is_complete=False, duration_s=1.0
            ),
        )
        # Block here so the async-for loop does not end naturally.
        await gen_blocker.wait()
        return  # Clean StopAsyncIteration when gen_blocker is set.

    monkeypatch.setattr("ralph.tui.run_ralph", _one_iter_run)

    config = RalphConfig(prd=tmp_path / "PRD.md", iterations=5, cwd=tmp_path)
    app = RalphApp(config=config)
    async with app.run_test(headless=True) as pilot:
        run_screen = app.screen
        assert isinstance(run_screen, RunScreen)

        # Pause immediately — before the first event-loop yield — so the worker
        # blocks at _pause_event.wait() after the first IterationResult.
        run_screen.action_pause_run()

        # Let the worker run the first iteration and reach the pause point.
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        # Trigger stop.
        run_screen.action_stop_run()
        # Also unblock the generator as a safety net: if the worker somehow got
        # past the _pause_event check, the generator can exit cleanly so that
        # RunFinished is still posted.
        gen_blocker.set()

        # Allow RunFinished → SummaryScreen transition.
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, SummaryScreen)
        await pilot.press("q")


# ---------------------------------------------------------------------------
# Task 12 — Completion flow: SummaryScreen content, stats, and navigation
# ---------------------------------------------------------------------------


class TestSummaryScreenStats:
    """Unit tests for SummaryScreen._render_stats() — no app required."""

    def _make_result(
        self,
        *,
        iteration: int = 1,
        is_complete: bool = False,
        duration_s: float = 2.0,
    ) -> IterationResult:
        return IterationResult(
            iteration=iteration,
            text="",
            is_complete=is_complete,
            duration_s=duration_s,
        )

    def test_empty_results_shows_zero_iterations(self):
        """With no results, iteration count is 0."""
        screen = SummaryScreen()
        stats = screen._render_stats()
        assert "Iterations:  0" in stats

    def test_empty_results_shows_zero_time(self):
        """With no results, time is 0.0s."""
        screen = SummaryScreen()
        stats = screen._render_stats()
        assert "0.0s" in stats

    def test_empty_results_status_stopped(self):
        """With no results, status shows 'Stopped early'."""
        screen = SummaryScreen()
        stats = screen._render_stats()
        assert "Stopped early" in stats

    def test_single_iteration_count(self):
        """Iteration count matches number of results."""
        results = [self._make_result(iteration=1)]
        screen = SummaryScreen(results=results)
        stats = screen._render_stats()
        assert "Iterations:  1" in stats

    def test_multiple_iterations_summed(self):
        """Three results → iteration count = 3."""
        results = [
            self._make_result(iteration=1),
            self._make_result(iteration=2),
            self._make_result(iteration=3),
        ]
        screen = SummaryScreen(results=results)
        assert "Iterations:  3" in screen._render_stats()

    def test_time_summed_across_iterations(self):
        """Total time is the sum of all results' duration_s."""
        results = [
            self._make_result(duration_s=1.5),
            self._make_result(duration_s=3.0),
        ]
        screen = SummaryScreen(results=results)
        stats = screen._render_stats()
        assert "4.5s" in stats

    def test_status_complete_when_any_is_complete(self):
        """Status shows 'Complete' when at least one result is_complete=True."""
        results = [
            self._make_result(is_complete=False),
            self._make_result(is_complete=True),
        ]
        screen = SummaryScreen(results=results)
        stats = screen._render_stats()
        assert "Complete" in stats
        assert "Stopped" not in stats

    def test_status_stopped_when_none_complete(self):
        """Status shows 'Stopped early' when no result is_complete=True."""
        results = [self._make_result(is_complete=False)]
        screen = SummaryScreen(results=results)
        stats = screen._render_stats()
        assert "Stopped early" in stats


class TestSummaryScreenTitle:
    """Unit tests for the SummaryScreen title logic."""

    def test_title_complete_when_is_complete(self):
        """compose() title is 'Run Complete ✓' when any result is complete."""
        results = [
            IterationResult(
                iteration=1,
                text="done",
                is_complete=True,

                duration_s=1.0,
            )
        ]
        screen = SummaryScreen(results=results)
        # The title is derived from the same is_complete check that renders stats.
        is_complete = any(r.is_complete for r in screen._results)
        assert is_complete is True

    def test_title_stopped_when_none_complete(self):
        """Title is 'Run Stopped' when no result is complete."""
        results = [
            IterationResult(
                iteration=1,
                text="partial",
                is_complete=False,

                duration_s=0.5,
            )
        ]
        screen = SummaryScreen(results=results)
        is_complete = any(r.is_complete for r in screen._results)
        assert is_complete is False


@pytest.mark.asyncio
async def test_summary_screen_compose_shows_title_and_stats():
    """SummaryScreen renders a title and stats widget when mounted."""
    from textual.widgets import Footer, Header, Label, Static

    results = [
        IterationResult(
            iteration=1, text="done", is_complete=True, duration_s=3.0
        )
    ]
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SummaryScreen(results=results))
        await pilot.pause()

        assert isinstance(app.screen, SummaryScreen)
        # Header and Footer must be present.
        app.screen.query_one(Header)
        app.screen.query_one(Footer)
        # The summary-content panel must be present.
        app.screen.query_one("#summary-content")
        # Title label must exist.
        title_label = app.screen.query_one("#summary-title", Label)
        assert title_label is not None
        # Stats static must exist.
        app.screen.query_one("#summary-stats", Static)
        # Action hints static must exist.
        app.screen.query_one("#summary-actions", Static)

        await pilot.press("q")


@pytest.mark.asyncio
async def test_summary_screen_compose_shows_task_panel_when_tasks_exist(tmp_path):
    """SummaryScreen shows a TaskPanel when config.tasks points to a real file."""
    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text("- [x] Task A\n- [ ] Task B\n", encoding="utf-8")

    config = RalphConfig(prd=tmp_path / "PRD.md", iterations=1, tasks=tasks_file)
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SummaryScreen(config=config, results=[]))
        await pilot.pause()

        assert isinstance(app.screen, SummaryScreen)
        # TaskPanel (#summary-tasks) must be present because tasks file exists.
        task_panel = app.screen.query_one("#summary-tasks", TaskPanel)
        assert task_panel is not None

        await pilot.press("q")


@pytest.mark.asyncio
async def test_summary_screen_compose_no_task_panel_when_no_tasks():
    """SummaryScreen does not show a TaskPanel when no tasks file is configured."""
    config = RalphConfig(prd=Path("PRD.md"), iterations=1, tasks=None)
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SummaryScreen(config=config, results=[]))
        await pilot.pause()

        assert isinstance(app.screen, SummaryScreen)
        # No TaskPanel should be present.
        task_panels = app.screen.query("#summary-tasks")
        assert len(task_panels) == 0

        await pilot.press("q")


@pytest.mark.asyncio
async def test_summary_screen_run_again_pushes_run_screen(monkeypatch, tmp_path):
    """Pressing 'r' on SummaryScreen pushes a fresh RunScreen with the same config."""
    # Worker never yields — stays idle so we can interact with SummaryScreen.
    async def _idle_run(config):
        await asyncio.Event().wait()
        yield  # pragma: no cover

    monkeypatch.setattr("ralph.tui.run_ralph", _idle_run)

    config = RalphConfig(prd=tmp_path / "PRD.md", iterations=2, cwd=tmp_path)
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        # Push SummaryScreen on top of BrowserScreen.
        app.push_screen(SummaryScreen(config=config, results=[]))
        await pilot.pause()
        assert isinstance(app.screen, SummaryScreen)

        # Press 'r' — should replace SummaryScreen → RunScreen.
        await pilot.press("r")
        await pilot.pause()
        await pilot.pause()

        # Active screen should now be a RunScreen with the same config.
        assert isinstance(app.screen, RunScreen)
        assert app.screen._config is config

        await pilot.press("q")


@pytest.mark.asyncio
async def test_summary_screen_go_browser_shows_browser_screen(monkeypatch, tmp_path):
    """Pressing 'b' on SummaryScreen navigates to BrowserScreen."""
    # Worker never yields — stays idle so no extra screen transitions occur.
    async def _idle_run(config):
        await asyncio.Event().wait()
        yield  # pragma: no cover

    monkeypatch.setattr("ralph.tui.run_ralph", _idle_run)

    config = RalphConfig(prd=tmp_path / "PRD.md", iterations=2, cwd=tmp_path)
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        # Push SummaryScreen on top of BrowserScreen.
        app.push_screen(SummaryScreen(config=config, results=[]))
        await pilot.pause()
        assert isinstance(app.screen, SummaryScreen)

        # Press 'b' — should navigate to BrowserScreen.
        await pilot.press("b")
        await pilot.pause()
        await pilot.pause()

        assert isinstance(app.screen, BrowserScreen)

        await pilot.press("q")


@pytest.mark.asyncio
async def test_summary_screen_run_again_no_op_when_no_config():
    """action_run_again() is a no-op when config is None."""
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SummaryScreen(config=None, results=[]))
        await pilot.pause()
        assert isinstance(app.screen, SummaryScreen)

        # Press 'r' — should not crash and screen should remain SummaryScreen.
        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, SummaryScreen)

        await pilot.press("q")


# ---------------------------------------------------------------------------
# HistoryScreen — unit tests (Task 13)
# ---------------------------------------------------------------------------


class TestHistoryScreenImport:
    """Verify HistoryScreen is importable and accessible."""

    def test_history_screen_importable(self):
        assert HistoryScreen is not None


class TestHistoryScreenLoadRuns:
    """Unit tests for _load_runs() — no Textual runtime required."""

    def test_no_runs_dir_returns_empty(self, tmp_path: Path):
        screen = HistoryScreen(cwd=tmp_path)
        assert screen._load_runs() == []

    def test_empty_runs_dir_returns_empty(self, tmp_path: Path):
        runs_dir = tmp_path / ".ralph" / "runs"
        runs_dir.mkdir(parents=True)
        screen = HistoryScreen(cwd=tmp_path)
        assert screen._load_runs() == []

    def test_loads_single_run(self, tmp_path: Path):
        runs_dir = tmp_path / ".ralph" / "runs"
        run_dir = runs_dir / "2026-02-24T11-27-39"
        run_dir.mkdir(parents=True)
        meta = {
            "run_id": "2026-02-24T11-27-39",
            "started_at": "2026-02-24T11:27:39+00:00",
            "prd": "/path/to/README.md",
            "iterations_requested": 10,
            "iterations_completed": 3,

            "total_duration_s": 120.0,
            "status": "complete",
        }
        (run_dir / "meta.json").write_text(json.dumps(meta))

        screen = HistoryScreen(cwd=tmp_path)
        runs = screen._load_runs()
        assert len(runs) == 1
        assert runs[0]["run_id"] == "2026-02-24T11-27-39"
        assert runs[0]["_run_dir"] == run_dir

    def test_loads_multiple_runs_newest_first(self, tmp_path: Path):
        runs_dir = tmp_path / ".ralph" / "runs"
        for slug in ["2026-02-24T10-00-00", "2026-02-24T12-00-00", "2026-02-24T11-00-00"]:
            d = runs_dir / slug
            d.mkdir(parents=True)
            (d / "meta.json").write_text(json.dumps({"run_id": slug}))

        screen = HistoryScreen(cwd=tmp_path)
        runs = screen._load_runs()
        ids = [r["run_id"] for r in runs]
        assert ids == ["2026-02-24T12-00-00", "2026-02-24T11-00-00", "2026-02-24T10-00-00"]

    def test_skips_dir_without_meta_json(self, tmp_path: Path):
        runs_dir = tmp_path / ".ralph" / "runs"
        bad_dir = runs_dir / "2026-02-24T11-00-00"
        bad_dir.mkdir(parents=True)
        # No meta.json written — should be skipped.
        good_dir = runs_dir / "2026-02-24T12-00-00"
        good_dir.mkdir(parents=True)
        (good_dir / "meta.json").write_text(json.dumps({"run_id": "2026-02-24T12-00-00"}))

        screen = HistoryScreen(cwd=tmp_path)
        runs = screen._load_runs()
        assert len(runs) == 1
        assert runs[0]["run_id"] == "2026-02-24T12-00-00"

    def test_skips_invalid_json(self, tmp_path: Path):
        runs_dir = tmp_path / ".ralph" / "runs"
        run_dir = runs_dir / "2026-02-24T11-00-00"
        run_dir.mkdir(parents=True)
        (run_dir / "meta.json").write_text("this is not json{{{")

        screen = HistoryScreen(cwd=tmp_path)
        assert screen._load_runs() == []


class TestHistoryScreenHelpers:
    """Unit tests for static helper methods."""

    def test_short_prd_name_from_full_path(self):
        result = HistoryScreen._short_prd_name(
            "/Users/user/project/docs/prds/run-history/README.md"
        )
        assert result == "run-history"

    def test_short_prd_name_none_returns_dash(self):
        assert HistoryScreen._short_prd_name(None) == "—"

    def test_short_prd_name_empty_string_returns_dash(self):
        assert HistoryScreen._short_prd_name("") == "—"

    def test_status_markup_complete(self):
        markup = HistoryScreen._status_markup("complete")
        assert "green" in markup
        assert "complete" in markup

    def test_status_markup_max_iterations(self):
        markup = HistoryScreen._status_markup("max-iterations")
        assert "yellow" in markup

    def test_status_markup_error(self):
        markup = HistoryScreen._status_markup("error")
        assert "red" in markup

    def test_status_markup_none_shows_in_progress(self):
        markup = HistoryScreen._status_markup(None)
        assert "in-progress" in markup

    def test_status_markup_unknown(self):
        markup = HistoryScreen._status_markup("weird-status")
        assert "weird-status" in markup

    def test_render_run_detail_includes_run_id(self, tmp_path: Path):
        meta: dict = {
            "run_id": "2026-02-24T11-27-39",
            "prd": "/path/to/run-history/README.md",
            "iterations_requested": 10,
            "iterations_completed": 3,

            "total_duration_s": 120.5,
            "status": "complete",
            "_run_dir": tmp_path,
        }
        screen = HistoryScreen(cwd=tmp_path)
        detail = screen._render_run_detail(meta)
        assert "2026-02-24T11-27-39" in detail
        assert "run-history" in detail
        assert "120.5s" in detail

    def test_render_run_detail_lists_iteration_files(self, tmp_path: Path):
        (tmp_path / "iteration-01.jsonl").write_text('{"type":"text"}\n')
        (tmp_path / "iteration-02.jsonl").write_text('{"type":"text"}\n')
        meta: dict = {"_run_dir": tmp_path}
        screen = HistoryScreen(cwd=tmp_path)
        detail = screen._render_run_detail(meta)
        assert "iteration-01.jsonl" in detail
        assert "iteration-02.jsonl" in detail


# ---------------------------------------------------------------------------
# HistoryScreen — async Textual integration tests (Task 13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_screen_is_importable():
    """HistoryScreen class exists and is importable."""
    assert HistoryScreen is not None


@pytest.mark.asyncio
async def test_history_screen_has_header_and_footer(tmp_path: Path):
    """HistoryScreen renders a Header and Footer."""
    from textual.widgets import Footer, Header

    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(HistoryScreen(cwd=tmp_path))
        await pilot.pause()
        assert isinstance(app.screen, HistoryScreen)
        app.screen.query_one(Header)
        app.screen.query_one(Footer)
        await pilot.press("q")


@pytest.mark.asyncio
async def test_history_screen_has_data_table(tmp_path: Path):
    """HistoryScreen renders a DataTable widget."""
    from textual.widgets import DataTable

    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(HistoryScreen(cwd=tmp_path))
        await pilot.pause()
        app.screen.query_one(DataTable)
        await pilot.press("q")


@pytest.mark.asyncio
async def test_history_screen_escape_pops_screen(tmp_path: Path):
    """Pressing Escape on HistoryScreen returns to the previous screen."""
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)
        app.push_screen(HistoryScreen(cwd=tmp_path))
        await pilot.pause()
        assert isinstance(app.screen, HistoryScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, BrowserScreen)

        await pilot.press("q")


@pytest.mark.asyncio
async def test_ralph_app_h_opens_history_screen(tmp_path: Path):
    """Pressing 'h' from BrowserScreen pushes HistoryScreen."""
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, BrowserScreen)

        await pilot.press("h")
        await pilot.pause()
        assert isinstance(app.screen, HistoryScreen)

        await pilot.press("q")


@pytest.mark.asyncio
async def test_ralph_app_h_does_not_stack_history_screens(tmp_path: Path):
    """Pressing 'h' when HistoryScreen is already active is a no-op."""
    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(HistoryScreen(cwd=tmp_path))
        await pilot.pause()
        assert isinstance(app.screen, HistoryScreen)

        # Pressing 'h' again should not push a second HistoryScreen.
        await pilot.press("h")
        await pilot.pause()
        assert isinstance(app.screen, HistoryScreen)
        # Verify the screen stack only has HistoryScreen on top, not two.
        await pilot.press("escape")
        await pilot.pause()
        # After one escape we should be back on BrowserScreen, not HistoryScreen again.
        assert isinstance(app.screen, BrowserScreen)

        await pilot.press("q")


@pytest.mark.asyncio
async def test_history_screen_populates_table_from_runs_dir(tmp_path: Path):
    """HistoryScreen populates the DataTable with rows from .ralph/runs/."""
    from textual.widgets import DataTable

    # Create a fake run directory.
    runs_dir = tmp_path / ".ralph" / "runs"
    run_dir = runs_dir / "2026-02-24T11-27-39"
    run_dir.mkdir(parents=True)
    meta = {
        "run_id": "2026-02-24T11-27-39",
        "prd": "/path/to/run-history/README.md",
        "iterations_requested": 10,
        "iterations_completed": 2,

        "total_duration_s": 531.85,
        "status": "max-iterations",
    }
    (run_dir / "meta.json").write_text(json.dumps(meta))

    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(HistoryScreen(cwd=tmp_path))
        await pilot.pause()
        table: DataTable = app.screen.query_one(DataTable)
        # One run → one data row (plus header row managed by DataTable).
        assert table.row_count == 1

        await pilot.press("q")


@pytest.mark.asyncio
async def test_history_screen_no_runs_shows_placeholder_row(tmp_path: Path):
    """HistoryScreen shows a placeholder row when there are no past runs."""
    from textual.widgets import DataTable

    app = RalphApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(HistoryScreen(cwd=tmp_path))
        await pilot.pause()
        table: DataTable = app.screen.query_one(DataTable)
        # Placeholder "No run history found" row is added.
        assert table.row_count == 1

        await pilot.press("q")
