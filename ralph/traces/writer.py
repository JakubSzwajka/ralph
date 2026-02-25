"""JSONL writer and run directory management for agent traces."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Generator

from ralph.traces.events import AnyEvent, _now_iso

if TYPE_CHECKING:
    from ralph.core import IterationResult, RalphConfig


class IterationWriter:
    """Writes events to a single ``iteration-NN.jsonl`` file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fh = path.open("a", encoding="utf-8")

    def write_event(self, event: AnyEvent) -> None:
        self._fh.write(event.to_json_line() + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


class RunRecorder:
    """Manages a single run directory under ``<root>/.ralph/runs/<timestamp>/``."""

    _GITIGNORE_PATTERN = ".ralph/runs/"

    def __init__(self, root: Path) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        self.run_id = ts
        self.run_dir = root / ".ralph" / "runs" / ts
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._root = root
        self._ensure_gitignore()

    def _ensure_gitignore(self) -> None:
        pattern = self._GITIGNORE_PATTERN
        gitignore = self._root / ".gitignore"

        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            if pattern in content.splitlines():
                return
            separator = "" if content.endswith("\n") or not content else "\n"
            gitignore.write_text(content + separator + pattern + "\n", encoding="utf-8")
        else:
            gitignore.write_text(pattern + "\n", encoding="utf-8")

    def write_meta_start(self, config: "RalphConfig") -> None:
        meta: dict = {
            "run_id": self.run_id,
            "started_at": _now_iso(),
            "prd": str(config.prd),
            "tasks": str(config.tasks) if config.tasks else None,
            "iterations_requested": config.iterations,
            "model": config.model,
            "permission_mode": config.permission_mode,
            "context_files": [str(p) for p in config.context_files],
        }
        meta_path = self.run_dir / "meta.json"
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

    def write_meta_progress(self, iteration: int) -> None:
        meta_path = self.run_dir / "meta.json"
        if meta_path.exists():
            with meta_path.open("r", encoding="utf-8") as fh:
                meta: dict = json.load(fh)
        else:
            meta = {}
        meta.update({"iterations_completed": iteration, "status": "running"})
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

    def write_meta_end(self, results: "list[IterationResult]") -> None:
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

    @contextmanager
    def open_iteration(self, n: int) -> Generator[IterationWriter, None, None]:
        path = self.run_dir / f"iteration-{n:02d}.jsonl"
        writer = IterationWriter(path)
        try:
            yield writer
        finally:
            writer.close()
