from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunSummary:
    run_id: str
    started_at: str
    completed_at: str | None
    status: str
    iterations_requested: int
    iterations_completed: int
    total_duration_s: float
    context_files: list[str] = field(default_factory=list)
    model: str | None = None


def list_runs(root: Path) -> list[RunSummary]:
    runs_dir = root / ".ralph" / "runs"
    if not runs_dir.is_dir():
        return []

    summaries: list[RunSummary] = []
    for meta_path in runs_dir.glob("*/meta.json"):
        try:
            data = json.loads(meta_path.read_text())
            summaries.append(
                RunSummary(
                    run_id=data["run_id"],
                    started_at=data["started_at"],
                    completed_at=data.get("completed_at"),
                    status=data.get("status", "unknown"),
                    iterations_requested=data.get("iterations_requested", 0),
                    iterations_completed=data.get("iterations_completed", 0),
                    total_duration_s=data.get("total_duration_s", 0.0),
                    context_files=data.get("context_files", []),
                    model=data.get("model"),
                )
            )
        except (json.JSONDecodeError, KeyError, OSError):
            continue

    summaries.sort(key=lambda s: s.started_at, reverse=True)
    return summaries
