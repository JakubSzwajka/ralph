"""Markdown task list parser for ralph.

Two parsing modes
-----------------
Structured tasks.md format
    Frontmatter + ``### N. Title`` sections containing ``<!-- status: … -->``,
    ``**Files:**`` and ``**Depends on:**`` blocks.  We correlate the quick
    ``- [ ]`` / ``- [x]`` checklist in the ``## Task List`` section with the
    detailed sections below to build rich TaskItem objects.

Plain checkbox fallback
    Any ``- [ ]`` or ``- [x]`` line in a plain markdown file.  Produces
    minimal TaskItems (title + done only).

Returns an empty list if the file doesn't exist or has no checkboxes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class TaskItem:
    """A single task parsed from a markdown task list.

    Attributes:
        title:       Human-readable task title (without leading number).
        done:        ``True`` when the checkbox is checked.
        index:       1-based position / number as found in the file.
        description: Optional body text extracted from a detailed section.
        files:       List of file paths mentioned in a ``**Files:**`` line.
        depends_on:  List of task indices mentioned in a ``**Depends on:**``
                     line (integers) or a ``[blocked by: …]`` annotation.
    """

    title: str
    done: bool
    index: int
    description: str | None = None
    files: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal regex patterns
# ---------------------------------------------------------------------------

# Matches a GFM task-list item:  - [ ] text  or  - [x] text
_CHECKBOX_RE = re.compile(r"^\s*-\s+\[([x ])\]\s+(.+)", re.IGNORECASE)

# Matches **N. Title** anywhere in a line (used inside quick-checklist items)
_NUMBERED_TITLE_RE = re.compile(r"\*\*(\d+)\.\s+(.+?)\*\*")

# Matches the start of a detailed section heading:  ### N. Title
# MULTILINE so that ^ anchors to line starts when used in search()
_SECTION_HEADING_RE = re.compile(r"^###\s+(\d+)\.\s+(.+)", re.MULTILINE)

# Matches a Files line:  **Files:** `ralph/foo.py`
_FILES_RE = re.compile(r"\*\*Files:\*\*\s+(.+)")

# Matches a Depends on line:  **Depends on:** 2, 3  or  —
_DEPENDS_ON_RE = re.compile(r"\*\*Depends on:\*\*\s+(.+)")

# Matches a status HTML comment:  <!-- status: done -->
_STATUS_COMMENT_RE = re.compile(r"<!--\s*status:\s*(\w+)\s*-->", re.IGNORECASE)

# Matches a YAML frontmatter block at the very start of a document
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from *text* if present."""
    m = _FRONTMATTER_RE.match(text)
    return text[m.end() :] if m else text


def _parse_depends_on(value: str) -> list[int]:
    """Convert a raw ``**Depends on:**`` value to a list of int indices.

    Handles:  "2, 3"  →  [2, 3]
              "—"     →  []
              "-"     →  []
    """
    value = value.strip()
    if value in ("—", "-", ""):
        return []
    result: list[int] = []
    for token in re.split(r"[,\s]+", value):
        try:
            result.append(int(token))
        except ValueError:
            pass
    return result


def _parse_files(value: str) -> list[str]:
    """Convert a raw ``**Files:**`` value to a list of file paths.

    Strips markdown backticks and splits on commas.
    Returns an empty list for "—" / "-".
    """
    paths: list[str] = []
    for token in value.split(","):
        cleaned = token.strip().strip("`").strip()
        if cleaned and cleaned not in ("—", "-"):
            paths.append(cleaned)
    return paths


# ---------------------------------------------------------------------------
# Structured parser (tasks.md format)
# ---------------------------------------------------------------------------


def _parse_structured(body: str) -> list[TaskItem] | None:
    """Parse the structured tasks.md format.

    Requires at least one ``### N. Title`` section.  Returns ``None`` when the
    format is not detected so the caller can fall back to plain parsing.
    """
    if not _SECTION_HEADING_RE.search(body):
        return None

    # --- Step 1: build a done-by-index map from the quick checklist ----------
    done_by_index: dict[int, bool] = {}
    for line in body.splitlines():
        cb = _CHECKBOX_RE.match(line)
        if cb:
            done = cb.group(1).lower() == "x"
            nm = _NUMBERED_TITLE_RE.match(cb.group(2))
            if nm:
                done_by_index[int(nm.group(1))] = done

    # --- Step 2: split on ### headings and parse each section ----------------
    # re.split with a lookahead keeps the delimiter at the start of each part.
    parts = re.split(r"(?m)^(?=###\s+\d+\.)", body)

    items: list[TaskItem] = []

    for part in parts:
        heading = _SECTION_HEADING_RE.match(part)
        if not heading:
            continue

        idx = int(heading.group(1))
        title = heading.group(2).strip()
        section_body = part[heading.end() :]

        # Determine done status (status comment takes precedence)
        status_m = _STATUS_COMMENT_RE.search(section_body)
        if status_m:
            done = status_m.group(1).lower() == "done"
        else:
            done = done_by_index.get(idx, False)

        # Extract structured fields and collect description lines
        files: list[str] = []
        depends_on: list[int] = []
        description_lines: list[str] = []

        for line in section_body.splitlines():
            stripped = line.strip()

            if not stripped or stripped == "---":
                continue

            files_m = _FILES_RE.search(line)
            depends_m = _DEPENDS_ON_RE.search(line)

            if files_m:
                files = _parse_files(files_m.group(1))
            elif depends_m:
                depends_on = _parse_depends_on(depends_m.group(1))
            elif _STATUS_COMMENT_RE.search(line):
                pass  # skip status comments — already handled above
            else:
                description_lines.append(stripped)

        description = "\n".join(description_lines) if description_lines else None

        items.append(
            TaskItem(
                title=title,
                done=done,
                index=idx,
                description=description,
                files=files,
                depends_on=depends_on,
            )
        )

    return sorted(items, key=lambda t: t.index) if items else None


# ---------------------------------------------------------------------------
# Plain checkbox parser (fallback)
# ---------------------------------------------------------------------------


def _parse_plain(text: str) -> list[TaskItem]:
    """Parse ``- [ ]`` / ``- [x]`` checkboxes from any markdown text.

    Produces minimal :class:`TaskItem` objects (title + done only).
    """
    items: list[TaskItem] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        m = _CHECKBOX_RE.match(line)
        if m:
            done = m.group(1).lower() == "x"
            # Remove **bold**, `code` markers to produce a clean title
            raw_title = m.group(2).strip()
            title = re.sub(r"\*\*|`", "", raw_title).strip()
            items.append(TaskItem(title=title, done=done, index=len(items) + 1))
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_tasks(path: Path) -> list[TaskItem]:
    """Parse a markdown task file and return a list of :class:`TaskItem` objects.

    Tries the structured ``tasks.md`` format (frontmatter + ``### N.`` sections)
    first.  Falls back to scanning for ``- [ ]`` / ``- [x]`` lines in plain
    markdown.

    Returns an empty list if the file does not exist, cannot be read, or
    contains no task checkboxes.

    Args:
        path: Path to the markdown task file.

    Returns:
        List of :class:`TaskItem` objects sorted by :attr:`~TaskItem.index`.
    """
    if not path.exists():
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    # Strip frontmatter so parsers work on the body only
    body = _strip_frontmatter(text)

    # Try structured format first
    structured = _parse_structured(body)
    if structured is not None:
        return structured

    # Fall back to plain checkbox scan
    return _parse_plain(body)
