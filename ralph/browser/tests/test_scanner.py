"""Tests for ralph.browser — PRD scanner."""
from __future__ import annotations

from pathlib import Path

from ralph.browser import PrdInfo, extract_title, parse_frontmatter, scan_prds


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        text = "---\nstatus: draft\nauthor: alice\n---\n# Title\n"
        result = parse_frontmatter(text)
        assert result == {"status": "draft", "author": "alice"}

    def test_no_frontmatter(self):
        assert parse_frontmatter("# Just a heading\n") == {}

    def test_missing_closing_delimiter(self):
        assert parse_frontmatter("---\nstatus: draft\n# Forgot\n") == {}

    def test_quoted_values_stripped(self):
        text = '---\ngh-issue: ""\ntoken: \'abc\'\n---\n'
        result = parse_frontmatter(text)
        assert result["gh-issue"] == ""
        assert result["token"] == "abc"

    def test_key_only_line(self):
        result = parse_frontmatter("---\nsome-key:\n---\n")
        assert result["some-key"] == ""

    def test_empty_frontmatter_block(self):
        assert parse_frontmatter("---\n---\n# Title\n") == {}


# ---------------------------------------------------------------------------
# extract_title
# ---------------------------------------------------------------------------


class TestExtractTitle:
    def test_h1_heading(self):
        assert extract_title("---\nstatus: draft\n---\n# My Feature\n") == "My Feature"

    def test_no_heading(self):
        assert extract_title("Just some text.\n") is None

    def test_first_h1_returned(self):
        assert extract_title("# First\n## Second\n# Third\n") == "First"

    def test_h2_not_matched(self):
        assert extract_title("## Section\n") is None


# ---------------------------------------------------------------------------
# scan_prds
# ---------------------------------------------------------------------------


class TestScanPrds:
    def test_missing_docs_prds_returns_empty(self, tmp_path: Path):
        assert scan_prds(tmp_path) == []

    def test_empty_prds_dir_returns_empty(self, tmp_path: Path):
        (tmp_path / "docs" / "prds").mkdir(parents=True)
        assert scan_prds(tmp_path) == []

    def test_prd_without_readme_not_included(self, tmp_path: Path):
        prd_dir = tmp_path / "docs" / "prds" / "orphan"
        prd_dir.mkdir(parents=True)
        (prd_dir / "tasks.md").write_text("# Tasks\n")
        assert scan_prds(tmp_path) == []

    def test_valid_prd_all_fields(self, tmp_path: Path):
        prd_dir = tmp_path / "docs" / "prds" / "my-feature"
        prd_dir.mkdir(parents=True)
        readme = prd_dir / "README.md"
        readme.write_text(
            "---\nstatus: accepted\n---\n# My Feature\n\nDescription.\n"
        )

        result = scan_prds(tmp_path)
        assert len(result) == 1
        prd = result[0]
        assert prd.slug == "my-feature"
        assert prd.title == "My Feature"
        assert prd.status == "accepted"
        assert prd.path == readme

    def test_missing_frontmatter_defaults_unknown(self, tmp_path: Path):
        prd_dir = tmp_path / "docs" / "prds" / "no-front"
        prd_dir.mkdir(parents=True)
        (prd_dir / "README.md").write_text("# No Frontmatter\n")
        assert scan_prds(tmp_path)[0].status == "unknown"

    def test_title_falls_back_to_slug(self, tmp_path: Path):
        prd_dir = tmp_path / "docs" / "prds" / "my-slug"
        prd_dir.mkdir(parents=True)
        (prd_dir / "README.md").write_text("---\nstatus: draft\n---\nNo heading.\n")
        assert scan_prds(tmp_path)[0].title == "my-slug"

    def test_task_files_detected(self, tmp_path: Path):
        prd_dir = tmp_path / "docs" / "prds" / "with-tasks"
        prd_dir.mkdir(parents=True)
        (prd_dir / "README.md").write_text("---\nstatus: draft\n---\n# With Tasks\n")
        tasks = prd_dir / "tasks.md"
        tasks.write_text("# Tasks\n")
        story = prd_dir / "story-1.md"
        story.write_text("# Story 1\n")
        assert scan_prds(tmp_path)[0].task_files == sorted([tasks, story])

    def test_multiple_prds_sorted_by_slug(self, tmp_path: Path):
        prds_dir = tmp_path / "docs" / "prds"
        for slug in ("zebra", "alpha", "beta"):
            d = prds_dir / slug
            d.mkdir(parents=True)
            (d / "README.md").write_text(f"---\nstatus: draft\n---\n# {slug.title()}\n")
        assert [p.slug for p in scan_prds(tmp_path)] == ["alpha", "beta", "zebra"]

    def test_real_project_prds_dir(self):
        project_root = Path(__file__).parent.parent.parent.parent
        result = scan_prds(project_root)
        assert "tui-control-panel" in [p.slug for p in result]

    def test_gh_issue_parsed(self, tmp_path: Path):
        prd_dir = tmp_path / "docs" / "prds" / "linked"
        prd_dir.mkdir(parents=True)
        (prd_dir / "README.md").write_text(
            "---\nstatus: draft\ngh-issue: https://github.com/org/repo/issues/1\n---\n# Linked\n"
        )
        assert scan_prds(tmp_path)[0].gh_issue == "https://github.com/org/repo/issues/1"

    def test_gh_issue_null_is_none(self, tmp_path: Path):
        prd_dir = tmp_path / "docs" / "prds" / "nulled"
        prd_dir.mkdir(parents=True)
        (prd_dir / "README.md").write_text("---\nstatus: draft\ngh-issue: ~\n---\n# Nulled\n")
        assert scan_prds(tmp_path)[0].gh_issue is None
