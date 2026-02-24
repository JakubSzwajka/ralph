"""GitHub Issues import utilities for ralph.

Provides helpers to:

* Fetch open GitHub issues via the ``gh`` CLI.
* Filter out issues already linked to existing PRDs.
* Derive filesystem-safe slugs from issue titles.
* Create PRD ``README.md`` files from imported issues.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path


def fetch_gh_issues() -> list[dict]:
    """Fetch open GitHub issues via the ``gh`` CLI.

    Runs ``gh issue list --json number,title,body,url --limit 50`` as a
    subprocess and returns the parsed JSON list.

    Returns:
        A list of issue dicts, each containing ``number``, ``title``,
        ``body``, and ``url`` keys.

    Raises:
        FileNotFoundError: When the ``gh`` CLI is not installed.
        subprocess.CalledProcessError: When the command exits non-zero.
        json.JSONDecodeError: When the output is not valid JSON.
    """
    result = subprocess.run(
        ["gh", "issue", "list", "--json", "number,title,body,url", "--limit", "50"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def filter_unlinked_issues(issues: list[dict], existing_gh_urls: set[str]) -> list[dict]:
    """Return only the issues whose URL is not already linked to a local PRD.

    Args:
        issues: Full list of GitHub issue dicts from :func:`fetch_gh_issues`.
        existing_gh_urls: Set of ``gh-issue`` URLs from existing PRD frontmatter.

    Returns:
        Subset of *issues* whose ``url`` field is not in *existing_gh_urls*.
    """
    return [i for i in issues if i.get("url", "") not in existing_gh_urls]


def slugify(title: str) -> str:
    """Convert *title* to a filesystem-safe kebab-case slug.

    Rules applied in order:

    1. Lowercase the title.
    2. Replace any run of non-alphanumeric characters with a single hyphen.
    3. Strip leading and trailing hyphens.
    4. Truncate to at most 50 characters, preferring a hyphen boundary.
    5. Strip trailing hyphens again after truncation.

    Args:
        title: Raw issue title string.

    Returns:
        A URL/filesystem-safe slug.  Returns ``"untitled"`` when the result
        would otherwise be empty.
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")

    if len(slug) > 50:
        # Try to truncate at a hyphen boundary within the first 51 chars.
        truncated = slug[:51]
        last_hyphen = truncated.rfind("-")
        if last_hyphen > 0:
            slug = truncated[:last_hyphen]
        else:
            slug = slug[:50]
        slug = slug.rstrip("-")

    return slug or "untitled"


def derive_slug(title: str, existing_slugs: set[str]) -> str:
    """Derive a unique slug for *title* that does not collide with *existing_slugs*.

    The base slug is computed with :func:`slugify`.  When the base slug
    already exists in *existing_slugs*, a numeric suffix is appended
    (``-2``, ``-3``, …) until a free slot is found.

    Args:
        title: Raw issue title string.
        existing_slugs: Set of slugs already in use.  **Not** modified by
                        this function; callers are responsible for tracking
                        newly created slugs.

    Returns:
        A slug string guaranteed not to be in *existing_slugs*.
    """
    base = slugify(title)
    if base not in existing_slugs:
        return base

    n = 2
    while True:
        candidate = f"{base}-{n}"
        if candidate not in existing_slugs:
            return candidate
        n += 1


def _build_prd_content(issue: dict) -> str:
    """Build the full content for a PRD ``README.md`` from a GitHub issue dict.

    Maps issue fields to the standard PRD frontmatter + markdown body format.
    The issue body is placed under the *Problem* section when it is at least
    50 characters long; otherwise a placeholder is used.  The *Proposed
    Solution* section always starts as a placeholder for the user to fill in.

    Args:
        issue: GitHub issue dict with ``number``, ``title``, ``body``, and
               ``url`` keys.

    Returns:
        Full file content string (frontmatter + body).
    """
    title = issue.get("title", "Untitled")
    url = issue.get("url", "")
    body = (issue.get("body") or "").strip()
    today = date.today().isoformat()

    # Use the issue body for the Problem section when it is substantive.
    if len(body) >= 50:
        problem = body
    else:
        problem = body if body else "_TODO: describe the problem_"

    proposed = "_TODO: fill in proposed solution_"

    lines = [
        "---",
        "status: draft",
        f"date: {today}",
        'author: "auto"',
        f"gh-issue: {url}",
        "---",
        "",
        f"# {title}",
        "",
        "## Problem",
        "",
        problem,
        "",
        "## Proposed Solution",
        "",
        proposed,
        "",
    ]
    return "\n".join(lines)


def create_prd_from_issue(
    issue: dict,
    prds_dir: Path,
    existing_slugs: set[str],
) -> Path:
    """Create a PRD directory and ``README.md`` from a GitHub issue.

    Derives a unique slug from the issue title, creates
    ``prds_dir/<slug>/``, and writes a ``README.md`` with frontmatter and
    content mapped from the issue.

    The *existing_slugs* set is updated **in-place** with the newly
    created slug so that subsequent calls within the same batch avoid
    collisions.

    Args:
        issue: GitHub issue dict with ``number``, ``title``, ``body``,
               and ``url`` keys.
        prds_dir: Directory in which to create the new PRD sub-directory.
        existing_slugs: Mutable set of slugs already in use; updated
                        in-place by this function.

    Returns:
        :class:`~pathlib.Path` to the newly created ``README.md``.
    """
    slug = derive_slug(issue.get("title", ""), existing_slugs)
    existing_slugs.add(slug)

    prd_dir = prds_dir / slug
    prd_dir.mkdir(parents=True, exist_ok=True)

    readme = prd_dir / "README.md"
    readme.write_text(_build_prd_content(issue), encoding="utf-8")
    return readme
