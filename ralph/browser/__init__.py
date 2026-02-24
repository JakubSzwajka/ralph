"""ralph.browser — PRD discovery and scanning.

This package scans the filesystem for PRD directories and parses their
metadata (frontmatter, titles, task files). It has no TUI dependencies.
"""

from ralph.browser.scanner import PrdInfo, extract_title, parse_frontmatter, scan_prds

# Backward compat aliases for internal callers that used the old private names
_parse_frontmatter = parse_frontmatter
_extract_title = extract_title

__all__ = [
    "PrdInfo",
    "parse_frontmatter",
    "extract_title",
    "scan_prds",
]
