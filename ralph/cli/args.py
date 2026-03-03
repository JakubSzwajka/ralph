from __future__ import annotations

import argparse
import os
from glob import glob, has_magic
from pathlib import Path

from ralph.config import load_config
from ralph.core import RalphConfig


def parse_args(
    argv: list[str] | None = None,
) -> tuple[RalphConfig, bool]:
    """Parse CLI arguments and return ``(RalphConfig, prd_explicit)``.

    *prd_explicit* is ``True`` when the user passed ``--prd`` on the command
    line.  When it is ``False`` the caller should exit with actionable usage
    guidance since CLI mode always requires explicit PRD input.
    """
    parser = argparse.ArgumentParser(
        prog="ralph",
        description="Autonomous coding agent loop powered by Claude",
    )
    parser.add_argument(
        "--prd",
        type=str,
        nargs="+",
        default=None,
        help=("Path(s) to PRD files, PRD directories, or glob patterns (required)."),
    )
    parser.add_argument(
        "--tasks", type=Path, default=None, help="Path to tasks list or directory"
    )
    parser.add_argument(
        "--cwd", type=Path, default=Path.cwd(), help="Working directory"
    )
    parser.add_argument(
        "--permission-mode",
        default="bypassPermissions",
        choices=["default", "acceptEdits", "plan", "bypassPermissions"],
    )
    parser.add_argument("--model", default=None, help="Claude model to use")
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Max Ralph loop iterations (default: 20)",
    )
    parser.add_argument(
        "--discord-webhook",
        default=None,
        metavar="URL",
        help="Discord webhook URL for notifications (also reads RALPH_DISCORD_WEBHOOK env var)",
    )
    parser.add_argument(
        "--discord-interval",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Minimum interval between Discord notification messages (default: 5s)",
    )

    args = parser.parse_args(argv)

    # Track whether the user explicitly provided --prd so main() can
    # produce an actionable error when it is missing.
    prd_explicit: bool = args.prd is not None
    context_files: list[Path] = []
    if prd_explicit:
        prd_candidates: list[Path] = []
        for raw in args.prd:
            prd_candidates.extend(_resolve_prd_candidates(raw, args.cwd))

        # Preserve order while dropping duplicates from overlapping globs.
        unique_candidates: list[Path] = []
        seen: set[str] = set()
        for p in prd_candidates:
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            unique_candidates.append(p)

        if unique_candidates:
            prd: Path = unique_candidates[0]
            if len(unique_candidates) > 1:
                context_files = unique_candidates
        else:
            # No glob match: keep literal path so main() can show a clear
            # "file not found" error.
            first = Path(os.path.expanduser(args.prd[0]))
            prd = first if first.is_absolute() else args.cwd / first
    else:
        prd = Path("PRD.md")

    # Load config file values (lowest precedence after defaults)
    file_config = load_config()

    # Resolve webhook URL: CLI flag > env var > config file
    discord_webhook_url = (
        args.discord_webhook
        or os.environ.get("RALPH_DISCORD_WEBHOOK")
        or file_config.get("discord_webhook_url")
        or None
    )

    # Resolve discord interval: CLI flag > config file > default (5.0)
    # args.discord_interval always has a value (default=5.0), so we check whether the
    # user explicitly provided it by comparing against the sentinel default.
    _interval_default = 5.0
    if args.discord_interval != _interval_default:
        # User explicitly set --discord-interval on the CLI; it wins.
        discord_min_interval: float = args.discord_interval
    else:
        # Fall back to config file, then default.
        discord_min_interval = float(
            file_config.get("discord_min_interval", _interval_default)
        )

    # Resolve iterations: --max-turns > config file > default (20)
    _iterations_default = 20
    if args.max_turns is not None:
        iterations = args.max_turns
    else:
        iterations = int(file_config.get("iterations", _iterations_default))

    return (
        RalphConfig(
            prd=prd,
            tasks=args.tasks,
            context_files=context_files,
            iterations=iterations,
            cwd=args.cwd,
            permission_mode=args.permission_mode,
            model=args.model,
            max_turns=None,
            discord_webhook_url=discord_webhook_url,
            discord_min_interval=discord_min_interval,
        ),
        prd_explicit,
    )


def _resolve_prd_candidates(raw: str, cwd: Path) -> list[Path]:
    """Resolve one --prd value to one or more markdown files.

    Supports files, globs, and directories. Directory resolution prefers
    a local README.md/PRD.md and falls back to recursive PRD discovery.
    """
    expanded = os.path.expanduser(raw)

    if has_magic(expanded):
        pattern = expanded if Path(expanded).is_absolute() else str(cwd / expanded)
        return [
            p
            for p in sorted(Path(p) for p in glob(pattern, recursive=True))
            if p.is_file()
        ]

    path = Path(expanded)
    resolved = path if path.is_absolute() else cwd / path

    if resolved.is_dir():
        direct = [resolved / "README.md", resolved / "PRD.md"]
        direct_matches = [p for p in direct if p.is_file()]
        if direct_matches:
            return direct_matches

        recursive: list[Path] = []
        recursive.extend(
            sorted(p for p in resolved.glob("**/README.md") if p.is_file())
        )
        recursive.extend(sorted(p for p in resolved.glob("**/PRD.md") if p.is_file()))
        if recursive:
            # Preserve discovery order while dropping duplicates.
            unique_recursive: list[Path] = []
            seen: set[str] = set()
            for p in recursive:
                key = str(p)
                if key in seen:
                    continue
                seen.add(key)
                unique_recursive.append(p)
            return unique_recursive

    return [resolved]
