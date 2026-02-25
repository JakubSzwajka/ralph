"""ralph.core — the autonomous agent loop.

This package is the heart of ralph. Everything else (TUI, CLI, Discord)
is a consumer of this module.
"""

from ralph.core.config import RalphConfig
from ralph.core.loop import IterationResult, run_iteration, run_ralph
from ralph.core.prompts import COMPLETION_SIGNAL, SYSTEM_PROMPT, build_prompt, build_prompt_from_files

__all__ = [
    "RalphConfig",
    "IterationResult",
    "run_iteration",
    "run_ralph",
    "COMPLETION_SIGNAL",
    "SYSTEM_PROMPT",
    "build_prompt",
    "build_prompt_from_files",
]
