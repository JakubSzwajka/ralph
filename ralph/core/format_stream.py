"""Stream output formatter — transforms raw block data into concise labeled lines.

Usage::

    from ralph.core.format_stream import format_block

    text = format_block("Bash", {"command": "ls", "description": "List files"})
    # -> "[Bash] List files"

    suppressed = format_block("_thinking", "sig123")
    # -> None  (caller should skip yielding this)
"""

from __future__ import annotations

import ast
from pathlib import Path


def _shorten_path(path_str: str, cwd: Path | None) -> str:
    """Return *path_str* relative to *cwd* when possible; otherwise unchanged."""
    if cwd is None or not path_str:
        return path_str
    try:
        return str(Path(path_str).relative_to(cwd))
    except ValueError:
        return path_str


def _parse_input(raw_input: dict | str) -> dict | str:
    """Normalise *raw_input* to a dict where possible.

    Accepts an already-parsed dict, a JSON/repr string, or a plain string.
    Falls back to returning the original string on any parse error.
    """
    if isinstance(raw_input, dict):
        return raw_input
    # raw_input is a string — try ast.literal_eval (handles Python repr dicts)
    try:
        parsed = ast.literal_eval(raw_input)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, SyntaxError):
        pass
    return raw_input


def format_block(
    name: str,
    raw_input: dict | str,
    cwd: Path | None = None,
) -> str | None:
    """Format a stream block into a concise human-readable line.

    Parameters
    ----------
    name:
        Block/tool name, e.g. ``"Bash"``, ``"Read"``, ``"_thinking"``.
        Internal names ``"_thinking"`` and ``"_result"`` map to suppressed
        blocks (ThinkingBlock and ToolResultBlock respectively).
    raw_input:
        The raw input dict from ``block.input``, or its ``str()`` representation.
    cwd:
        Working directory used to shorten absolute file paths.

    Returns
    -------
    str | None
        A formatted one-liner, or ``None`` if the block should be suppressed.
    """
    # Suppress ThinkingBlock and ToolResultBlock — they're internal noise.
    if name in ("_thinking", "_result"):
        return None

    inp = _parse_input(raw_input)

    if name == "Bash":
        if isinstance(inp, dict):
            text = str(inp.get("description") or inp.get("command", ""))
        else:
            text = str(inp)
        return f"[Bash] {text[:120]}"

    if name == "Read":
        if isinstance(inp, dict):
            path = _shorten_path(inp.get("file_path", ""), cwd)
            offset = inp.get("offset")
            limit = inp.get("limit")
            suffix = (
                f":{offset}-{limit}"
                if (offset is not None or limit is not None)
                else ""
            )
            return f"[Read] {path}{suffix}"
        return f"[Read] {str(inp)[:100]}"

    if name == "Edit":
        if isinstance(inp, dict):
            path = _shorten_path(inp.get("file_path", ""), cwd)
            return f"[Edit] {path}"
        return f"[Edit] {str(inp)[:100]}"

    if name == "Write":
        if isinstance(inp, dict):
            path = _shorten_path(inp.get("file_path", ""), cwd)
            return f"[Write] {path}"
        return f"[Write] {str(inp)[:100]}"

    if name == "Task":
        if isinstance(inp, dict):
            subagent = inp.get("subagent_type", "")
            desc = inp.get("description", "")
            return f"[Task:{subagent}] {desc}"
        return f"[Task] {str(inp)[:100]}"

    if name == "Grep":
        if isinstance(inp, dict):
            pattern = inp.get("pattern", "")
            path = inp.get("path", "")
            if path:
                path = _shorten_path(path, cwd)
                return f'[Grep] "{pattern}" in {path}'
            return f'[Grep] "{pattern}"'
        return f"[Grep] {str(inp)[:100]}"

    if name == "Glob":
        if isinstance(inp, dict):
            return f"[Glob] {inp.get('pattern', '')}"
        return f"[Glob] {str(inp)[:100]}"

    if name == "TodoWrite":
        if isinstance(inp, dict):
            todos = inp.get("todos", [])
            n = len(todos) if isinstance(todos, list) else 0
            return f"[Todo] {n} items"
        return f"[Todo] {str(inp)[:100]}"

    # Fallback: generic label with first 100 chars of input
    text = str(inp)[:100]
    return f"[{name}] {text}"
