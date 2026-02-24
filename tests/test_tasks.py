"""Tests for ralph.tasks — markdown task list parser (Task 2)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from ralph.tasks import TaskItem, parse_tasks


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

STRUCTURED_TASKS_MD = dedent("""\
    ---
    prd: example
    generated: 2026-01-01
    ---

    # Tasks: Example

    > Summary: A small example task list.

    ## Task List

    - [x] **1. First task** — do the first thing
    - [ ] **2. Second task** — do the second thing `[blocked by: 1]`
    - [x] **3. Third task** — do the third thing

    ---

    ### 1. First task
    <!-- status: done -->

    Description of the first task.

    **Files:** `ralph/foo.py`
    **Depends on:** —
    **Validates:** foo is correct

    ---

    ### 2. Second task
    <!-- status: pending -->

    Description of the second task.
    It spans multiple lines.

    **Files:** `ralph/bar.py`, `ralph/baz.py`
    **Depends on:** 1
    **Validates:** bar and baz work together

    ---

    ### 3. Third task
    <!-- status: done -->

    Description of the third task.

    **Files:** `ralph/qux.py`
    **Depends on:** 1, 2
    **Validates:** qux integrates everything

    ---
""")

PLAIN_TASKS_MD = dedent("""\
    # My Plain Task List

    Some intro text.

    - [x] Fix the login bug
    - [ ] Write unit tests
    - [ ] Update the documentation
""")

MIXED_CONTENT_MD = dedent("""\
    Some preamble.

    - [x] **Done item**
    This is not a checkbox.
    - [ ] Pending item
    - [X] Case-insensitive done item
""")


# ---------------------------------------------------------------------------
# Edge cases — missing / empty files
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """parse_tasks() should gracefully handle bad inputs."""

    def test_nonexistent_file_returns_empty(self, tmp_path: Path):
        result = parse_tasks(tmp_path / "nonexistent.md")
        assert result == []

    def test_empty_file_returns_empty(self, tmp_path: Path):
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        assert parse_tasks(f) == []

    def test_no_checkboxes_returns_empty(self, tmp_path: Path):
        f = tmp_path / "no_tasks.md"
        f.write_text("# Just a heading\n\nSome text.\n", encoding="utf-8")
        assert parse_tasks(f) == []

    def test_returns_list(self, tmp_path: Path):
        f = tmp_path / "tasks.md"
        f.write_text(PLAIN_TASKS_MD, encoding="utf-8")
        result = parse_tasks(f)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Plain checkbox fallback
# ---------------------------------------------------------------------------


class TestPlainCheckboxParsing:
    """parse_tasks() falls back to plain checkbox scanning for simple files."""

    def setup_method(self, tmp_path_factory) -> None:
        pass  # tmp_path is used via pytest fixture injection

    def test_basic_done_status(self, tmp_path: Path):
        f = tmp_path / "tasks.md"
        f.write_text(PLAIN_TASKS_MD, encoding="utf-8")
        items = parse_tasks(f)

        assert len(items) == 3
        assert items[0].done is True
        assert items[1].done is False
        assert items[2].done is False

    def test_plain_titles_are_cleaned(self, tmp_path: Path):
        f = tmp_path / "tasks.md"
        f.write_text(PLAIN_TASKS_MD, encoding="utf-8")
        items = parse_tasks(f)

        assert items[0].title == "Fix the login bug"
        assert items[1].title == "Write unit tests"
        assert items[2].title == "Update the documentation"

    def test_indices_are_sequential(self, tmp_path: Path):
        f = tmp_path / "tasks.md"
        f.write_text(PLAIN_TASKS_MD, encoding="utf-8")
        items = parse_tasks(f)

        assert [t.index for t in items] == [1, 2, 3]

    def test_plain_items_have_no_files_or_depends(self, tmp_path: Path):
        f = tmp_path / "tasks.md"
        f.write_text(PLAIN_TASKS_MD, encoding="utf-8")
        items = parse_tasks(f)

        for item in items:
            assert item.files == []
            assert item.depends_on == []
            assert item.description is None

    def test_case_insensitive_x(self, tmp_path: Path):
        """Both [x] and [X] are treated as done."""
        f = tmp_path / "tasks.md"
        f.write_text(MIXED_CONTENT_MD, encoding="utf-8")
        items = parse_tasks(f)

        # Find case-insensitive done item
        upper_x = next(t for t in items if "Case-insensitive" in t.title)
        assert upper_x.done is True

    def test_bold_markers_stripped_from_title(self, tmp_path: Path):
        """**Bold** markers in plain items are stripped."""
        f = tmp_path / "tasks.md"
        f.write_text(MIXED_CONTENT_MD, encoding="utf-8")
        items = parse_tasks(f)

        done_item = next(t for t in items if t.done and "Done" in t.title)
        assert "**" not in done_item.title


# ---------------------------------------------------------------------------
# Structured tasks.md format
# ---------------------------------------------------------------------------


class TestStructuredParsing:
    """parse_tasks() extracts richer info from the structured tasks.md format."""

    @pytest.fixture
    def items(self, tmp_path: Path) -> list[TaskItem]:
        f = tmp_path / "tasks.md"
        f.write_text(STRUCTURED_TASKS_MD, encoding="utf-8")
        return parse_tasks(f)

    def test_correct_count(self, items: list[TaskItem]):
        assert len(items) == 3

    def test_sorted_by_index(self, items: list[TaskItem]):
        assert [t.index for t in items] == [1, 2, 3]

    def test_done_status_from_status_comment(self, items: list[TaskItem]):
        """Status comment <!-- status: done --> takes precedence."""
        assert items[0].done is True   # status: done
        assert items[1].done is False  # status: pending
        assert items[2].done is True   # status: done

    def test_title_extraction(self, items: list[TaskItem]):
        assert items[0].title == "First task"
        assert items[1].title == "Second task"
        assert items[2].title == "Third task"

    def test_files_single(self, items: list[TaskItem]):
        assert items[0].files == ["ralph/foo.py"]

    def test_files_multiple(self, items: list[TaskItem]):
        assert items[1].files == ["ralph/bar.py", "ralph/baz.py"]

    def test_files_empty_for_dash(self, items: list[TaskItem]):
        """**Depends on:** — should produce an empty depends_on list."""
        assert items[0].depends_on == []

    def test_depends_on_single(self, items: list[TaskItem]):
        assert items[1].depends_on == [1]

    def test_depends_on_multiple(self, items: list[TaskItem]):
        assert items[2].depends_on == [1, 2]

    def test_description_present(self, items: list[TaskItem]):
        assert items[0].description is not None
        assert "first task" in items[0].description.lower()

    def test_description_multiline(self, items: list[TaskItem]):
        """Multi-line descriptions are preserved."""
        assert items[1].description is not None
        assert "multiple lines" in items[1].description.lower()

    def test_description_excludes_files_line(self, items: list[TaskItem]):
        desc = items[0].description or ""
        assert "**Files:**" not in desc

    def test_description_excludes_depends_line(self, items: list[TaskItem]):
        desc = items[0].description or ""
        assert "**Depends on:**" not in desc

    def test_taskitem_is_dataclass(self, items: list[TaskItem]):
        item = items[0]
        assert isinstance(item, TaskItem)
        assert hasattr(item, "title")
        assert hasattr(item, "done")
        assert hasattr(item, "index")
        assert hasattr(item, "description")
        assert hasattr(item, "files")
        assert hasattr(item, "depends_on")


# ---------------------------------------------------------------------------
# Status comment vs quick-checklist disagreement
# ---------------------------------------------------------------------------


class TestStatusPrecedence:
    """The <!-- status: done --> comment overrides the checkbox state."""

    def test_comment_overrides_unchecked_box(self, tmp_path: Path):
        """A section marked done via comment should be done even if checkbox
        in the quick list is ``[ ]``."""
        content = dedent("""\
            ## Task List

            - [ ] **1. A task** — description

            ---

            ### 1. A task
            <!-- status: done -->

            Some body text.

            **Files:** `ralph/a.py`
            **Depends on:** —
            **Validates:** it works

            ---
        """)
        f = tmp_path / "tasks.md"
        f.write_text(content, encoding="utf-8")
        items = parse_tasks(f)
        assert len(items) == 1
        assert items[0].done is True

    def test_comment_overrides_checked_box(self, tmp_path: Path):
        """A pending comment should mark the task not done even if the
        checkbox is ``[x]``."""
        content = dedent("""\
            ## Task List

            - [x] **1. A task** — description

            ---

            ### 1. A task
            <!-- status: pending -->

            Some body text.

            **Files:** `ralph/a.py`
            **Depends on:** —

            ---
        """)
        f = tmp_path / "tasks.md"
        f.write_text(content, encoding="utf-8")
        items = parse_tasks(f)
        assert len(items) == 1
        assert items[0].done is False


# ---------------------------------------------------------------------------
# Real-world file: docs/prds/tui-control-panel/tasks.md
# ---------------------------------------------------------------------------


class TestRealTasksFile:
    """Smoke-test against the actual tasks file in this repository."""

    @pytest.fixture
    def real_tasks_path(self) -> Path:
        return Path(__file__).parent.parent / "docs" / "prds" / "tui-control-panel" / "tasks.md"

    def test_file_exists(self, real_tasks_path: Path):
        assert real_tasks_path.exists(), "tasks.md should be present in the repo"

    def test_returns_14_items(self, real_tasks_path: Path):
        items = parse_tasks(real_tasks_path)
        assert len(items) == 14

    def test_first_item_is_done(self, real_tasks_path: Path):
        """Task 1 (scaffold) is marked done in tasks.md."""
        items = parse_tasks(real_tasks_path)
        first = items[0]
        assert first.index == 1
        assert first.done is True

    def test_completed_tasks_are_done(self, real_tasks_path: Path):
        """Tasks 1–13 are all marked done (completed in prior iterations)."""
        items = parse_tasks(real_tasks_path)
        for item in items[:13]:
            assert item.done is True, f"Task {item.index} should be done"

    def test_remaining_items_are_pending(self, real_tasks_path: Path):
        """Task 14 is still pending."""
        items = parse_tasks(real_tasks_path)
        for item in items[13:]:
            assert item.done is False, f"Task {item.index} should be pending"

    def test_indices_are_contiguous(self, real_tasks_path: Path):
        items = parse_tasks(real_tasks_path)
        assert [t.index for t in items] == list(range(1, 15))

    def test_task_14_has_file(self, real_tasks_path: Path):
        """Task 14 mentions ralph/cli.py in its Files field."""
        items = parse_tasks(real_tasks_path)
        task_14 = items[13]
        assert task_14.index == 14
        assert any("cli.py" in f for f in task_14.files)
