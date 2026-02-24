"""PRD scanner — discovers and parses PRD directories from disk."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PrdInfo:
    """Information about a discovered PRD directory."""

    slug: str
    title: str
    status: str
    path: Path
    task_files: list[Path] = field(default_factory=list)
    gh_issue: str | None = None


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse simple YAML frontmatter delimited by ``---`` lines.

    Only handles flat ``key: value`` pairs. Returns an empty dict when
    frontmatter is absent or the closing delimiter is not found.
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


def extract_title(text: str) -> str | None:
    """Return the text of the first H1 heading (``# …``) in *text*, or ``None``."""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def scan_prds(root: Path, prds_dir: Path | None = None) -> list[PrdInfo]:
    """Scan for PRD directories.

    Each sub-directory containing a ``README.md`` is treated as one PRD.

    Args:
        root: Project root directory.
        prds_dir: Explicit directory to scan. Defaults to ``root/docs/prds/``.

    Returns:
        List of PrdInfo objects sorted alphabetically by slug.
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

        frontmatter = parse_frontmatter(text)
        title = extract_title(text) or slug
        status = frontmatter.get("status", "unknown")

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
