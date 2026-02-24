"""Run history recorder — event schema and JSONL writer.

Events are persisted to ``.ralph/runs/<timestamp>/iteration-NN.jsonl`` as
individual JSON lines (one object per line).  Each event carries a ``type``
discriminator, an ISO-8601 UTC ``timestamp``, and the relevant payload.

Usage example::

    recorder = RunRecorder(project_root)
    with recorder.open_iteration(1) as writer:
        writer.write_event(TextEvent(text="hello"))
"""
from __future__ import annotations

import dataclasses
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from ralph.core import IterationResult, RalphConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Event schema
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class TextEvent:
    """A plain-text chunk from an assistant message."""

    # ``type`` is a class-level constant — excluded from __init__ (init=False)
    # so that it does not participate in the constructor argument ordering rules.
    type: str = dataclasses.field(default="text", init=False)
    text: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        """Serialise to a single JSON line (no trailing newline)."""
        return json.dumps(dataclasses.asdict(self))


@dataclasses.dataclass
class ThinkingEvent:
    """A thinking block produced by an extended-thinking model."""

    type: str = dataclasses.field(default="thinking", init=False)
    thinking: str = ""
    signature: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self))


@dataclasses.dataclass
class ToolUseEvent:
    """A tool-use block — the agent calling a tool."""

    type: str = dataclasses.field(default="tool_use", init=False)
    name: str = ""
    # ``input`` is stored as its string representation to avoid custom
    # JSON encoders for arbitrary dict payloads.
    input: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self))


@dataclasses.dataclass
class ToolResultEvent:
    """The result returned from a tool invocation."""

    type: str = dataclasses.field(default="tool_result", init=False)
    tool_use_id: str = ""
    content: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self))


@dataclasses.dataclass
class UserMessageEvent:
    """A user-turn message injected into the conversation."""

    type: str = dataclasses.field(default="user_message", init=False)
    content: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self))


# Union type for all event kinds.
AnyEvent = (
    TextEvent
    | ThinkingEvent
    | ToolUseEvent
    | ToolResultEvent
    | UserMessageEvent
)


# ---------------------------------------------------------------------------
# IterationWriter
# ---------------------------------------------------------------------------


class IterationWriter:
    """Writes events to a single ``iteration-NN.jsonl`` file.

    Keeps the file handle open for the duration of the iteration and flushes
    after every event so that partial results are visible immediately.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fh = path.open("a", encoding="utf-8")

    def write_event(self, event: AnyEvent) -> None:
        """Append *event* as a JSON line and flush."""
        self._fh.write(event.to_json_line() + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


# ---------------------------------------------------------------------------
# RunRecorder
# ---------------------------------------------------------------------------


class RunRecorder:
    """Manages a single run directory under ``<root>/.ralph/runs/<timestamp>/``.

    Parameters
    ----------
    root:
        Project root directory.  The run directory is created as
        ``<root>/.ralph/runs/<timestamp>/`` where *timestamp* uses the format
        ``YYYY-MM-DDTHH-MM-SS``.
    """

    #: Pattern added to ``.gitignore`` so run history is not committed.
    _GITIGNORE_PATTERN = ".ralph/runs/"

    def __init__(self, root: Path) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        self.run_id = ts
        self.run_dir = root / ".ralph" / "runs" / ts
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._root = root
        self._ensure_gitignore()

    def _ensure_gitignore(self) -> None:
        """Add ``.ralph/runs/`` to ``.gitignore`` if not already present.

        Creates ``.gitignore`` when it does not exist.  Skips silently when the
        pattern is already listed (exact line match) to avoid duplicates.
        """
        pattern = self._GITIGNORE_PATTERN
        gitignore = self._root / ".gitignore"

        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            if pattern in content.splitlines():
                return  # Already present — nothing to do.
            # Append on a new line, preserving any trailing content.
            separator = "" if content.endswith("\n") or not content else "\n"
            gitignore.write_text(content + separator + pattern + "\n", encoding="utf-8")
        else:
            gitignore.write_text(pattern + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # Meta-data persistence
    # ------------------------------------------------------------------

    def write_meta_start(self, config: "RalphConfig") -> None:
        """Write ``meta.json`` with a config snapshot at run start.

        Parameters
        ----------
        config:
            The :class:`~ralph.core.RalphConfig` used for this run.
        """
        meta: dict = {
            "run_id": self.run_id,
            "started_at": _now_iso(),
            "prd": str(config.prd),
            "tasks": str(config.tasks) if config.tasks else None,
            "iterations_requested": config.iterations,
            "model": config.model,
            "permission_mode": config.permission_mode,
        }
        meta_path = self.run_dir / "meta.json"
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

    def write_meta_end(self, results: "list[IterationResult]") -> None:
        """Update ``meta.json`` with run totals at completion.

        Reads the existing ``meta.json`` (written by :meth:`write_meta_start`)
        and appends completion fields so that both ``started_at`` and
        ``completed_at`` are present after a run.

        Parameters
        ----------
        results:
            Ordered list of :class:`~ralph.core.IterationResult` objects
            collected during the run.
        """
        meta_path = self.run_dir / "meta.json"
        if meta_path.exists():
            with meta_path.open("r", encoding="utf-8") as fh:
                meta: dict = json.load(fh)
        else:
            meta = {}

        total_duration = sum(r.duration_s for r in results)
        iterations_completed = len(results)

        if any(r.is_complete for r in results):
            status = "complete"
        elif iterations_completed > 0:
            status = "max-iterations"
        else:
            status = "error"

        meta.update(
            {
                "completed_at": _now_iso(),
                "iterations_completed": iterations_completed,
                "total_duration_s": total_duration,
                "status": status,
            }
        )
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

    # ------------------------------------------------------------------
    # Iteration context manager
    # ------------------------------------------------------------------

    @contextmanager
    def open_iteration(self, n: int) -> Generator[IterationWriter, None, None]:
        """Return a context manager that yields an :class:`IterationWriter`.

        The writer appends JSON lines to ``iteration-{n:02d}.jsonl`` inside
        the run directory.  The file handle is closed on context exit.

        Parameters
        ----------
        n:
            1-based iteration number.
        """
        path = self.run_dir / f"iteration-{n:02d}.jsonl"
        writer = IterationWriter(path)
        try:
            yield writer
        finally:
            writer.close()
