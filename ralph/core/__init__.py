"""ralph.core — the autonomous agent loop.

This package is the heart of ralph. Everything else (CLI, Discord)
is a consumer of this module.
"""

from ralph.core.config import RalphConfig
from ralph.core.executor import RunResult, execute_run
from ralph.core.run_meta import RunMeta, RunStatus, default_runs_dir, generate_run_id
from ralph.core.loop import IterationResult, run_iteration, run_ralph
from ralph.core.prompts import (
    COMPLETION_SIGNAL,
    build_prompt_from_files,
)

__all__ = [
    "COMPLETION_SIGNAL",
    "IterationResult",
    "RalphConfig",
    "RunMeta",
    "RunResult",
    "RunStatus",
    "build_prompt_from_files",
    "default_runs_dir",
    "execute_run",
    "generate_run_id",
    "run_iteration",
    "run_ralph",
]
