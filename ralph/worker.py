from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
import uuid
from datetime import datetime, UTC
from pathlib import Path

from ralph.core.config import RalphConfig
from ralph.core.loop import IterationResult, run_ralph
from ralph.core.run_meta import RunMeta, RunStatus, default_runs_dir, generate_run_id


def serialize_config(config: RalphConfig) -> str:
    data = {
        "prd": str(config.prd),
        "tasks": str(config.tasks) if config.tasks else None,
        "context_files": [str(p) for p in config.context_files],
        "iterations": config.iterations,
        "cwd": str(config.cwd),
        "permission_mode": str(config.permission_mode),
        "model": config.model,
        "max_turns": config.max_turns,
        "discord_webhook_url": config.discord_webhook_url,
        "discord_notify": config.discord_notify,
        "discord_min_interval": config.discord_min_interval,
    }
    import tempfile

    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


def _parse_config(path: str) -> RalphConfig:
    raw = json.loads(Path(path).read_text())
    return RalphConfig(
        prd=Path(raw["prd"]),
        tasks=Path(raw["tasks"]) if raw.get("tasks") else None,
        context_files=[Path(p) for p in raw.get("context_files", [])],
        iterations=raw.get("iterations", 10),
        cwd=Path(raw.get("cwd", ".")),
        permission_mode=raw.get("permission_mode", "bypassPermissions"),
        model=raw.get("model"),
        max_turns=raw.get("max_turns"),
        discord_webhook_url=raw.get("discord_webhook_url"),
        discord_notify=raw.get("discord_notify", False),
        discord_min_interval=raw.get("discord_min_interval", 5.0),
    )


async def worker_main(config_path: str) -> None:
    config = _parse_config(config_path)
    run_id = generate_run_id()
    runs_dir = default_runs_dir()

    print(run_id, flush=True)

    log_path = runs_dir / run_id / "output.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w")

    session_id = uuid.uuid4().hex

    meta = RunMeta(
        run_id=run_id,
        pid=os.getpid(),
        started_at=datetime.now(UTC).isoformat(),
        status=RunStatus.RUNNING,
        prd=str(config.prd),
        tasks=str(config.tasks) if config.tasks else None,
        iterations_requested=config.iterations,
        model=config.model,
        permission_mode=str(config.permission_mode),
        session_id=session_id,
        context_files=[str(p) for p in config.context_files],
    )
    meta.write(runs_dir)

    killed = False

    def _on_sigterm(_signum: int, _frame: object) -> None:
        nonlocal killed
        killed = True

    signal.signal(signal.SIGTERM, _on_sigterm)

    start = time.monotonic()
    try:
        async for _iteration, item in run_ralph(config, session_id=session_id):
            if isinstance(item, str):
                log_file.write(item)
                log_file.flush()
            elif isinstance(item, IterationResult):
                log_file.write(
                    f"\n--- Iteration {item.iteration} done ({item.duration_s:.1f}s) ---\n"
                )
                log_file.flush()
                elapsed = time.monotonic() - start
                meta.update(
                    runs_dir,
                    iterations_completed=item.iteration,
                    total_duration_s=round(elapsed, 2),
                )
                if item.is_complete:
                    break

            if killed:
                meta.update(
                    runs_dir,
                    status=RunStatus.KILLED,
                    completed_at=datetime.now(UTC).isoformat(),
                    total_duration_s=round(time.monotonic() - start, 2),
                )
                return

        meta.update(
            runs_dir,
            status=RunStatus.DONE,
            completed_at=datetime.now(UTC).isoformat(),
            total_duration_s=round(time.monotonic() - start, 2),
        )
    except Exception:
        import traceback

        traceback.print_exc(file=log_file)
        meta.update(
            runs_dir,
            status=RunStatus.ERROR,
            completed_at=datetime.now(UTC).isoformat(),
            total_duration_s=round(time.monotonic() - start, 2),
        )
    finally:
        log_file.close()


if __name__ == "__main__":
    asyncio.run(worker_main(sys.argv[1]))
