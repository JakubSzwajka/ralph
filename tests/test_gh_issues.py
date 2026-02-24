"""Tests for ralph.gh_issues — GitHub issue import utilities."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ralph.gh_issues import (
    _build_prd_content,
    create_prd_from_issue,
    derive_slug,
    fetch_gh_issues,
    filter_unlinked_issues,
    slugify,
)


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    """Unit tests for the slugify() helper."""

    def test_basic_title(self):
        assert slugify("My Feature Request") == "my-feature-request"

    def test_numbers_preserved(self):
        assert slugify("Add OAuth2 support") == "add-oauth2-support"

    def test_special_chars_become_hyphens(self):
        assert slugify("Foo: Bar / Baz!") == "foo-bar-baz"

    def test_multiple_spaces_collapse(self):
        assert slugify("foo   bar") == "foo-bar"

    def test_leading_trailing_hyphens_stripped(self):
        assert slugify("--hello world--") == "hello-world"

    def test_empty_string(self):
        assert slugify("") == "untitled"

    def test_only_special_chars(self):
        assert slugify("!!!") == "untitled"

    def test_truncation_at_50_chars(self):
        long_title = "a" * 60
        result = slugify(long_title)
        assert len(result) <= 50

    def test_truncation_prefers_hyphen_boundary(self):
        # Title: "abcde-" repeated, so truncation should land on a hyphen.
        title = "hello world " * 6  # "hello-world-hello-world-..." repeated
        result = slugify(title)
        assert len(result) <= 50
        assert not result.endswith("-")

    def test_no_trailing_hyphen_after_truncation(self):
        # Construct a slug that would end in '-' at exactly 50 chars.
        # "abcde-" * 9 = 54 chars → truncated to 50 → "abcde-abcde-...-abcde" ends in 'e'
        title = "abcde " * 10
        result = slugify(title)
        assert not result.endswith("-")

    def test_already_short_title(self):
        result = slugify("fix bug")
        assert result == "fix-bug"

    def test_exactly_50_chars(self):
        title = "a" * 50
        result = slugify(title)
        assert result == "a" * 50
        assert len(result) == 50

    def test_unicode_collapsed(self):
        """Non-ASCII characters (outside a-z0-9) are replaced with hyphens."""
        result = slugify("café au lait")
        assert result == "caf-au-lait"


# ---------------------------------------------------------------------------
# derive_slug
# ---------------------------------------------------------------------------


class TestDeriveSlug:
    """Unit tests for the derive_slug() collision-resolution helper."""

    def test_no_collision(self):
        result = derive_slug("My Feature", set())
        assert result == "my-feature"

    def test_no_collision_with_unrelated_existing(self):
        result = derive_slug("My Feature", {"other-slug", "yet-another"})
        assert result == "my-feature"

    def test_single_collision_appends_2(self):
        existing = {"my-feature"}
        result = derive_slug("My Feature", existing)
        assert result == "my-feature-2"

    def test_multiple_collisions_increment(self):
        existing = {"my-feature", "my-feature-2", "my-feature-3"}
        result = derive_slug("My Feature", existing)
        assert result == "my-feature-4"

    def test_does_not_mutate_existing_slugs(self):
        """derive_slug() must not modify the existing_slugs set."""
        existing = {"my-feature"}
        original_size = len(existing)
        derive_slug("My Feature", existing)
        assert len(existing) == original_size

    def test_empty_title_uses_untitled(self):
        result = derive_slug("", set())
        assert result == "untitled"

    def test_empty_title_collision(self):
        result = derive_slug("", {"untitled"})
        assert result == "untitled-2"


# ---------------------------------------------------------------------------
# filter_unlinked_issues
# ---------------------------------------------------------------------------


class TestFilterUnlinkedIssues:
    """Unit tests for filter_unlinked_issues()."""

    def _make_issues(self):
        return [
            {"number": 1, "title": "First", "url": "https://github.com/o/r/issues/1"},
            {"number": 2, "title": "Second", "url": "https://github.com/o/r/issues/2"},
            {"number": 3, "title": "Third", "url": "https://github.com/o/r/issues/3"},
        ]

    def test_no_existing_urls(self):
        issues = self._make_issues()
        result = filter_unlinked_issues(issues, set())
        assert result == issues

    def test_all_linked(self):
        issues = self._make_issues()
        existing = {i["url"] for i in issues}
        result = filter_unlinked_issues(issues, existing)
        assert result == []

    def test_partial_filter(self):
        issues = self._make_issues()
        existing = {"https://github.com/o/r/issues/2"}
        result = filter_unlinked_issues(issues, existing)
        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[1]["number"] == 3

    def test_empty_issues(self):
        result = filter_unlinked_issues([], {"https://github.com/o/r/issues/1"})
        assert result == []


# ---------------------------------------------------------------------------
# _build_prd_content
# ---------------------------------------------------------------------------


class TestBuildPrdContent:
    """Unit tests for _build_prd_content()."""

    def _make_issue(self, title="My Feature", body="", url="https://github.com/o/r/issues/99"):
        return {"number": 99, "title": title, "body": body, "url": url}

    def test_contains_frontmatter_delimiters(self):
        content = _build_prd_content(self._make_issue())
        assert content.startswith("---")
        # Closing delimiter in first 10 lines.
        lines = content.split("\n")
        assert "---" in lines[1:7]

    def test_status_is_draft(self):
        content = _build_prd_content(self._make_issue())
        assert "status: draft" in content

    def test_gh_issue_url_in_frontmatter(self):
        content = _build_prd_content(self._make_issue(url="https://github.com/o/r/issues/42"))
        assert "gh-issue: https://github.com/o/r/issues/42" in content

    def test_title_as_h1(self):
        content = _build_prd_content(self._make_issue(title="Cool Feature"))
        assert "# Cool Feature" in content

    def test_long_body_used_in_problem_section(self):
        long_body = "This is a very detailed description of the problem. " * 3
        content = _build_prd_content(self._make_issue(body=long_body))
        assert long_body.strip() in content
        assert "## Problem" in content

    def test_short_body_uses_placeholder(self):
        content = _build_prd_content(self._make_issue(body="short"))
        # Short body still appears but proposed solution is placeholder.
        assert "## Proposed Solution" in content
        assert "_TODO: fill in proposed solution_" in content

    def test_empty_body_uses_placeholder(self):
        content = _build_prd_content(self._make_issue(body=""))
        assert "_TODO: describe the problem_" in content

    def test_proposed_solution_placeholder(self):
        content = _build_prd_content(self._make_issue())
        assert "_TODO: fill in proposed solution_" in content

    def test_author_auto(self):
        content = _build_prd_content(self._make_issue())
        assert 'author: "auto"' in content


# ---------------------------------------------------------------------------
# create_prd_from_issue
# ---------------------------------------------------------------------------


class TestCreatePrdFromIssue:
    """Integration tests for create_prd_from_issue()."""

    def _make_issue(self, number=1, title="My Feature", body="", url="https://gh/1"):
        return {"number": number, "title": title, "body": body, "url": url}

    def test_creates_directory_and_readme(self, tmp_path):
        prds_dir = tmp_path / "prds"
        prds_dir.mkdir()
        existing_slugs: set[str] = set()

        readme = create_prd_from_issue(self._make_issue(), prds_dir, existing_slugs)

        assert readme.exists()
        assert readme.name == "README.md"

    def test_slug_derived_from_title(self, tmp_path):
        prds_dir = tmp_path / "prds"
        prds_dir.mkdir()
        existing_slugs: set[str] = set()

        readme = create_prd_from_issue(
            self._make_issue(title="Add OAuth2"), prds_dir, existing_slugs
        )

        assert readme.parent.name == "add-oauth2"

    def test_existing_slugs_updated_in_place(self, tmp_path):
        prds_dir = tmp_path / "prds"
        prds_dir.mkdir()
        existing_slugs: set[str] = set()

        create_prd_from_issue(self._make_issue(title="My Feature"), prds_dir, existing_slugs)

        assert "my-feature" in existing_slugs

    def test_collision_numeric_suffix(self, tmp_path):
        prds_dir = tmp_path / "prds"
        prds_dir.mkdir()
        existing_slugs: set[str] = {"my-feature"}

        readme = create_prd_from_issue(
            self._make_issue(title="My Feature"), prds_dir, existing_slugs
        )

        assert readme.parent.name == "my-feature-2"

    def test_batch_no_collision_within_batch(self, tmp_path):
        """Creating multiple PRDs with the same title resolves collisions."""
        prds_dir = tmp_path / "prds"
        prds_dir.mkdir()
        existing_slugs: set[str] = set()

        issue = self._make_issue(title="Same Title")
        r1 = create_prd_from_issue(issue, prds_dir, existing_slugs)
        r2 = create_prd_from_issue(issue, prds_dir, existing_slugs)

        assert r1.parent.name == "same-title"
        assert r2.parent.name == "same-title-2"

    def test_readme_contains_correct_content(self, tmp_path):
        prds_dir = tmp_path / "prds"
        prds_dir.mkdir()
        existing_slugs: set[str] = set()

        issue = self._make_issue(
            title="Cool Feature",
            body="A " * 30,  # long enough body (> 50 chars)
            url="https://github.com/org/repo/issues/42",
        )
        readme = create_prd_from_issue(issue, prds_dir, existing_slugs)
        content = readme.read_text(encoding="utf-8")

        assert "status: draft" in content
        assert "gh-issue: https://github.com/org/repo/issues/42" in content
        assert "# Cool Feature" in content

    def test_creates_parent_dirs(self, tmp_path):
        """prds_dir does not need to pre-exist — it is created."""
        prds_dir = tmp_path / "nested" / "prds"
        existing_slugs: set[str] = set()

        readme = create_prd_from_issue(self._make_issue(), prds_dir, existing_slugs)

        assert readme.exists()


# ---------------------------------------------------------------------------
# fetch_gh_issues
# ---------------------------------------------------------------------------


class TestFetchGhIssues:
    """Tests for fetch_gh_issues() — mocks the subprocess call."""

    def test_returns_parsed_json(self, monkeypatch):
        issues = [
            {"number": 1, "title": "First", "body": "body1", "url": "https://gh/1"},
            {"number": 2, "title": "Second", "body": "body2", "url": "https://gh/2"},
        ]

        class FakeResult:
            stdout = json.dumps(issues)
            returncode = 0

        monkeypatch.setattr(
            "ralph.gh_issues.subprocess.run",
            lambda *args, **kwargs: FakeResult(),
        )

        result = fetch_gh_issues()
        assert result == issues

    def test_raises_file_not_found_when_gh_missing(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise FileNotFoundError("gh not found")

        monkeypatch.setattr("ralph.gh_issues.subprocess.run", _raise)

        with pytest.raises(FileNotFoundError):
            fetch_gh_issues()

    def test_raises_on_nonzero_exit(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise subprocess.CalledProcessError(1, "gh")

        monkeypatch.setattr("ralph.gh_issues.subprocess.run", _raise)

        with pytest.raises(subprocess.CalledProcessError):
            fetch_gh_issues()
