"""Tests for ralph.browser — PRD scanner and browser app."""

from __future__ import annotations

from pathlib import Path

import pytest

from ralph.browser import (
    BrowserResult,
    NoPrdsFoundScreen,
    PrdInfo,
    RalphBrowser,
    _extract_title,
    _parse_frontmatter,
    _status_style,
    scan_prds,
)


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        text = "---\nstatus: draft\nauthor: alice\n---\n# Title\n"
        result = _parse_frontmatter(text)
        assert result == {"status": "draft", "author": "alice"}

    def test_no_frontmatter(self):
        text = "# Just a heading\nNo frontmatter here.\n"
        assert _parse_frontmatter(text) == {}

    def test_missing_closing_delimiter(self):
        text = "---\nstatus: draft\n# Forgot to close\n"
        assert _parse_frontmatter(text) == {}

    def test_quoted_values_stripped(self):
        text = '---\ngh-issue: ""\ntoken: \'abc\'\n---\n'
        result = _parse_frontmatter(text)
        assert result["gh-issue"] == ""
        assert result["token"] == "abc"

    def test_key_only_line(self):
        text = "---\nsome-key:\n---\n"
        result = _parse_frontmatter(text)
        assert result["some-key"] == ""

    def test_empty_frontmatter_block(self):
        text = "---\n---\n# Title\n"
        assert _parse_frontmatter(text) == {}


# ---------------------------------------------------------------------------
# _extract_title
# ---------------------------------------------------------------------------


class TestExtractTitle:
    def test_h1_heading(self):
        text = "---\nstatus: draft\n---\n# My Feature\n\nParagraph.\n"
        assert _extract_title(text) == "My Feature"

    def test_no_heading(self):
        text = "Just some text.\nNo headings here.\n"
        assert _extract_title(text) is None

    def test_first_h1_returned(self):
        text = "# First\n\n## Second\n\n# Third\n"
        assert _extract_title(text) == "First"

    def test_h2_not_matched(self):
        text = "## Section\n\nContent.\n"
        assert _extract_title(text) is None


# ---------------------------------------------------------------------------
# scan_prds
# ---------------------------------------------------------------------------


class TestScanPrds:
    def test_missing_docs_prds_returns_empty(self, tmp_path: Path):
        """scan_prds returns [] when docs/prds/ does not exist."""
        result = scan_prds(tmp_path)
        assert result == []

    def test_empty_prds_dir_returns_empty(self, tmp_path: Path):
        """scan_prds returns [] when docs/prds/ exists but has no sub-dirs."""
        (tmp_path / "docs" / "prds").mkdir(parents=True)
        assert scan_prds(tmp_path) == []

    def test_prd_without_readme_not_included(self, tmp_path: Path):
        """Directories without README.md are ignored."""
        prd_dir = tmp_path / "docs" / "prds" / "orphan"
        prd_dir.mkdir(parents=True)
        (prd_dir / "tasks.md").write_text("# Tasks\n")
        assert scan_prds(tmp_path) == []

    def test_valid_prd_all_fields(self, tmp_path: Path):
        """Valid PRD with frontmatter and H1 heading populates all PrdInfo fields."""
        prd_dir = tmp_path / "docs" / "prds" / "my-feature"
        prd_dir.mkdir(parents=True)
        readme = prd_dir / "README.md"
        readme.write_text(
            "---\nstatus: accepted\ndate: 2026-01-01\nauthor: alice\n---\n"
            "# My Feature\n\nDescription here.\n"
        )

        result = scan_prds(tmp_path)

        assert len(result) == 1
        prd = result[0]
        assert prd.slug == "my-feature"
        assert prd.title == "My Feature"
        assert prd.status == "accepted"
        assert prd.path == readme
        assert prd.task_files == []

    def test_missing_frontmatter_defaults_status_unknown(self, tmp_path: Path):
        """PRD without frontmatter gets status='unknown'."""
        prd_dir = tmp_path / "docs" / "prds" / "no-front"
        prd_dir.mkdir(parents=True)
        (prd_dir / "README.md").write_text("# No Frontmatter\n\nJust content.\n")

        result = scan_prds(tmp_path)

        assert len(result) == 1
        assert result[0].status == "unknown"
        assert result[0].title == "No Frontmatter"

    def test_missing_status_key_defaults_unknown(self, tmp_path: Path):
        """PRD with frontmatter but no status key gets status='unknown'."""
        prd_dir = tmp_path / "docs" / "prds" / "no-status"
        prd_dir.mkdir(parents=True)
        (prd_dir / "README.md").write_text(
            "---\nauthor: bob\n---\n# No Status Key\n"
        )

        result = scan_prds(tmp_path)

        assert result[0].status == "unknown"

    def test_malformed_frontmatter_defaults_unknown(self, tmp_path: Path):
        """Frontmatter with no valid key:value pairs gives status='unknown'."""
        prd_dir = tmp_path / "docs" / "prds" / "bad-front"
        prd_dir.mkdir(parents=True)
        (prd_dir / "README.md").write_text(
            "---\njust a line without colon\n---\n# Bad Frontmatter\n"
        )

        result = scan_prds(tmp_path)

        assert result[0].status == "unknown"

    def test_title_falls_back_to_slug(self, tmp_path: Path):
        """When there is no H1 heading, title defaults to the directory slug."""
        prd_dir = tmp_path / "docs" / "prds" / "my-slug"
        prd_dir.mkdir(parents=True)
        (prd_dir / "README.md").write_text(
            "---\nstatus: draft\n---\n\nNo heading here, just prose.\n"
        )

        result = scan_prds(tmp_path)

        assert result[0].title == "my-slug"

    def test_task_files_detected(self, tmp_path: Path):
        """task_files includes all .md files except README.md."""
        prd_dir = tmp_path / "docs" / "prds" / "with-tasks"
        prd_dir.mkdir(parents=True)
        readme = prd_dir / "README.md"
        readme.write_text("---\nstatus: draft\n---\n# With Tasks\n")
        tasks = prd_dir / "tasks.md"
        tasks.write_text("# Tasks\n")
        story = prd_dir / "story-1.md"
        story.write_text("# Story 1\n")

        result = scan_prds(tmp_path)

        assert result[0].task_files == sorted([tasks, story])

    def test_multiple_prds_sorted_by_slug(self, tmp_path: Path):
        """Multiple PRDs are returned sorted alphabetically by slug."""
        prds_dir = tmp_path / "docs" / "prds"
        for slug, status in [("zebra", "draft"), ("alpha", "accepted"), ("beta", "in-progress")]:
            prd_dir = prds_dir / slug
            prd_dir.mkdir(parents=True)
            (prd_dir / "README.md").write_text(
                f"---\nstatus: {status}\n---\n# {slug.title()}\n"
            )

        result = scan_prds(tmp_path)

        assert [p.slug for p in result] == ["alpha", "beta", "zebra"]
        assert [p.status for p in result] == ["accepted", "in-progress", "draft"]

    def test_real_project_prds_dir(self):
        """Smoke test: scan_prds on the actual project root returns at least one PRD."""
        project_root = Path(__file__).parent.parent
        result = scan_prds(project_root)
        # The project has at least the tui-control-panel PRD
        slugs = [p.slug for p in result]
        assert "tui-control-panel" in slugs

    def test_tui_control_panel_prd_fields(self):
        """The tui-control-panel PRD has expected fields."""
        project_root = Path(__file__).parent.parent
        result = scan_prds(project_root)
        prd = next(p for p in result if p.slug == "tui-control-panel")
        assert prd.status == "draft"
        assert prd.title == "TUI Control Panel — Ralph as a Persistent Textual App"
        assert any(f.name == "tasks.md" for f in prd.task_files)


# ---------------------------------------------------------------------------
# _status_style
# ---------------------------------------------------------------------------


class TestStatusStyle:
    def test_accepted_is_green(self):
        assert _status_style("accepted") == "green"

    def test_in_progress_is_yellow(self):
        assert _status_style("in-progress") == "yellow"

    def test_draft_is_dim(self):
        assert _status_style("draft") == "dim"

    def test_unknown_returns_empty_string(self):
        """unknown status has no special Rich style (displayed as [?] in the badge)."""
        assert _status_style("unknown") == ""

    def test_unrecognised_returns_empty_string(self):
        assert _status_style("foobar") == ""


# ---------------------------------------------------------------------------
# NoPrdsFoundScreen — instantiation (no Textual pilot needed)
# ---------------------------------------------------------------------------


class TestNoPrdsFoundScreen:
    def test_stores_prds_dir(self, tmp_path: Path):
        """NoPrdsFoundScreen remembers the directory it was given."""
        screen = NoPrdsFoundScreen(prds_dir=tmp_path / "docs" / "prds")
        assert screen._prds_dir == tmp_path / "docs" / "prds"

    def test_accepts_any_path(self, tmp_path: Path):
        """NoPrdsFoundScreen accepts an arbitrary Path without validation."""
        custom = tmp_path / "custom" / "location"
        screen = NoPrdsFoundScreen(prds_dir=custom)
        assert screen._prds_dir == custom


# ---------------------------------------------------------------------------
# RalphBrowser — _effective_prds_dir property
# ---------------------------------------------------------------------------


class TestRalphBrowserEffectivePrdsDir:
    def test_default_is_docs_prds(self, tmp_path: Path):
        """Without prd_dir, _effective_prds_dir is root/docs/prds."""
        app = RalphBrowser(root=tmp_path)
        assert app._effective_prds_dir == tmp_path / "docs" / "prds"

    def test_explicit_prd_dir_is_returned(self, tmp_path: Path):
        """With prd_dir set, _effective_prds_dir returns that path."""
        custom = tmp_path / "my-prds"
        app = RalphBrowser(root=tmp_path, prd_dir=custom)
        assert app._effective_prds_dir == custom

    def test_default_when_root_is_cwd(self):
        """Smoke test: no prd_dir → effective dir is relative to root."""
        import os
        root = Path(os.getcwd())
        app = RalphBrowser(root=root)
        assert app._effective_prds_dir == root / "docs" / "prds"


# ---------------------------------------------------------------------------
# RalphBrowser — Textual pilot integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRalphBrowserPilot:
    """End-to-end integration tests that drive the TUI via Textual's Pilot API.

    Each test runs the app in headless mode and simulates key presses through
    the real screen flow.  Key navigation conventions used here:

    * ``down`` / ``j`` — move tree cursor to next node
    * ``enter`` — select the focused tree node or confirm a screen
    * ``escape`` — dismiss / go back
    * ``q`` — quit the app (``RalphBrowser.BINDINGS``)
    """

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _make_prd(
        self,
        tmp_path: Path,
        slug: str = "my-prd",
        status: str = "draft",
        with_tasks: bool = False,
    ) -> tuple[Path, Path | None]:
        """Create a minimal PRD directory under *tmp_path*.

        Returns ``(readme_path, tasks_path)``; *tasks_path* is ``None`` when
        *with_tasks* is ``False``.
        """
        prd_dir = tmp_path / "docs" / "prds" / slug
        prd_dir.mkdir(parents=True)
        readme = prd_dir / "README.md"
        readme.write_text(
            f"---\nstatus: {status}\n---\n# {slug.replace('-', ' ').title()}\n"
        )
        tasks: Path | None = None
        if with_tasks:
            tasks = prd_dir / "tasks.md"
            tasks.write_text("# Tasks\n")
        return readme, tasks

    # ------------------------------------------------------------------
    # Quit / escape paths
    # ------------------------------------------------------------------

    async def test_quit_key_returns_none(self, tmp_path: Path) -> None:
        """Pressing 'q' at the PRD selection screen exits the app with None."""
        self._make_prd(tmp_path)
        app = RalphBrowser(root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()   # wait for on_mount + screen push to settle
            await pilot.press("q")
            await pilot.pause()
        assert app.return_value is None

    async def test_escape_on_prd_screen_returns_none(self, tmp_path: Path) -> None:
        """Pressing Escape on PrdSelectionScreen exits the app with None."""
        self._make_prd(tmp_path)
        app = RalphBrowser(root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.return_value is None

    async def test_no_prds_found_escape_returns_none(self, tmp_path: Path) -> None:
        """With an empty prds dir, pressing Escape on NoPrdsFoundScreen exits."""
        (tmp_path / "docs" / "prds").mkdir(parents=True)  # exists but empty
        app = RalphBrowser(root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.return_value is None

    async def test_escape_on_tasks_screen_goes_back(self, tmp_path: Path) -> None:
        """Pressing Escape on TasksSelectionScreen returns to PRD selection."""
        self._make_prd(tmp_path, with_tasks=True)
        app = RalphBrowser(root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Select the first (only) PRD
            await pilot.press("down", "enter")
            await pilot.pause()
            # On tasks screen: go back
            await pilot.press("escape")
            await pilot.pause()
            # Now back at PRD selection; quit cleanly
            await pilot.press("q")
            await pilot.pause()
        assert app.return_value is None

    async def test_escape_on_confirmation_screen_goes_back(self, tmp_path: Path) -> None:
        """Pressing Escape on ConfirmationScreen returns to PRD selection."""
        self._make_prd(tmp_path, with_tasks=True)
        app = RalphBrowser(root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            # PRD selection → tasks selection
            await pilot.press("down", "enter")
            await pilot.pause()
            # Tasks selection → confirmation
            await pilot.press("enter")
            await pilot.pause()
            # Confirmation → back to PRD selection via Escape
            await pilot.press("escape")
            await pilot.pause()
            # Quit from PRD selection
            await pilot.press("q")
            await pilot.pause()
        assert app.return_value is None

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    async def test_full_flow_returns_browser_result(self, tmp_path: Path) -> None:
        """Full flow: select PRD → select tasks → confirm → BrowserResult."""
        readme, tasks = self._make_prd(tmp_path, with_tasks=True)
        app = RalphBrowser(root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            # PRD selection: cursor starts on root; 'down' moves to first leaf
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            # Tasks selection: first task is pre-selected on mount
            await pilot.press("enter")
            await pilot.pause()
            # Confirmation: Enter to start
            await pilot.press("enter")
            await pilot.pause()
        result = app.return_value
        assert isinstance(result, BrowserResult)
        assert result.prd == readme
        assert result.tasks == tasks

    async def test_vim_j_key_navigates_down(self, tmp_path: Path) -> None:
        """The 'j' vim binding moves the tree cursor down identically to 'down'."""
        readme, tasks = self._make_prd(tmp_path, with_tasks=True)
        app = RalphBrowser(root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Use 'j' instead of 'down' to navigate to the first PRD leaf
            await pilot.press("j", "enter")
            await pilot.pause()
            await pilot.press("enter")   # confirm tasks
            await pilot.pause()
            await pilot.press("enter")   # confirm selection
            await pilot.pause()
        result = app.return_value
        assert isinstance(result, BrowserResult)
        assert result.prd == readme

    async def test_multiple_prds_second_prd_selectable(self, tmp_path: Path) -> None:
        """Pressing 'j' twice navigates to the second PRD in the list."""
        prds_dir = tmp_path / "docs" / "prds"
        for slug in ("alpha", "beta"):
            prd_dir = prds_dir / slug
            prd_dir.mkdir(parents=True)
            (prd_dir / "README.md").write_text(
                f"---\nstatus: draft\n---\n# {slug.title()}\n"
            )
            (prd_dir / "tasks.md").write_text("# Tasks\n")

        beta_readme = prds_dir / "beta" / "README.md"
        app = RalphBrowser(root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            # 'j' × 2: skip root, skip alpha, land on beta
            await pilot.press("j", "j", "enter")
            await pilot.pause()
            await pilot.press("enter")   # select tasks
            await pilot.pause()
            await pilot.press("enter")   # confirm
            await pilot.pause()
        result = app.return_value
        assert isinstance(result, BrowserResult)
        assert result.prd == beta_readme
