from __future__ import annotations

import json
import os
import signal
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
from pathlib import Path


class RunStatus(StrEnum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    KILLED = "killed"


@dataclass
class RunMeta:
    run_id: str
    pid: int | None = None
    started_at: str = ""
    completed_at: str | None = None
    status: RunStatus = RunStatus.RUNNING
    prd: str = "PRD.md"
    tasks: str | None = None
    iterations_requested: int = 10
    iterations_completed: int = 0
    total_duration_s: float = 0.0
    model: str | None = None
    permission_mode: str = "bypassPermissions"
    session_id: str | None = None
    context_files: list[str] = field(default_factory=list)

    def _to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "pid": self.pid,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": str(self.status),
            "prd": self.prd,
            "tasks": self.tasks,
            "iterations_requested": self.iterations_requested,
            "iterations_completed": self.iterations_completed,
            "total_duration_s": self.total_duration_s,
            "model": self.model,
            "permission_mode": self.permission_mode,
            "session_id": self.session_id,
            "context_files": self.context_files,
        }

    def write(self, runs_dir: Path) -> Path:
        out = runs_dir / self.run_id / "meta.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self._to_dict(), indent=2) + "\n")
        return out

    def update(self, runs_dir: Path, **fields: object) -> None:
        for k, v in fields.items():
            setattr(self, k, v)
        self.write(runs_dir)

    @staticmethod
    def read(path: Path) -> RunMeta:
        data = json.loads(path.read_text())
        return RunMeta(
            run_id=data["run_id"],
            pid=data.get("pid"),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
            status=RunStatus(data.get("status", "running")),
            prd=data.get("prd", "PRD.md"),
            tasks=data.get("tasks"),
            iterations_requested=data.get("iterations_requested", 10),
            iterations_completed=data.get("iterations_completed", 0),
            total_duration_s=data.get("total_duration_s", 0.0),
            model=data.get("model"),
            permission_mode=data.get("permission_mode", "bypassPermissions"),
            session_id=data.get("session_id"),
            context_files=data.get("context_files", []),
        )

    @staticmethod
    def list_runs(runs_dir: Path) -> list[RunMeta]:
        if not runs_dir.is_dir():
            return []
        results: list[RunMeta] = []
        for meta_path in runs_dir.glob("*/meta.json"):
            try:
                results.append(RunMeta.read(meta_path))
            except Exception:
                continue
        results.sort(key=lambda m: m.started_at, reverse=True)
        return results


def generate_run_id() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")


def default_runs_dir() -> Path:
    return Path.cwd() / ".ralph" / "runs"


COMPLETION_SIGNAL = "<promise>COMPLETE</promise>"


def cleanup_stale_runs(runs_dir: Path) -> None:
    for run in RunMeta.list_runs(runs_dir):
        if run.status != RunStatus.RUNNING:
            continue
        pid_alive = False
        if run.pid is not None:
            try:
                os.kill(run.pid, 0)
                pid_alive = True
            except OSError:
                pass

        log_path = runs_dir / run.run_id / "output.log"
        log_has_complete = False
        try:
            if log_path.is_file():
                log_has_complete = COMPLETION_SIGNAL in log_path.read_text(
                    errors="replace"
                )
        except Exception:
            pass

        if log_has_complete:
            run.update(runs_dir, status=RunStatus.DONE)
            if pid_alive and run.pid is not None:
                os.kill(run.pid, signal.SIGTERM)
        elif not pid_alive:
            run.update(runs_dir, status=RunStatus.ERROR)
