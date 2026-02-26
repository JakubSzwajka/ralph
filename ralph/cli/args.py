from __future__ import annotations

import argparse
import os
from pathlib import Path

from ralph.config import load_config
from ralph.core import RalphConfig


def parse_args(
    argv: list[str] | None = None,
) -> tuple[RalphConfig, bool, Path | None, bool]:
    """Parse CLI arguments and return (RalphConfig, prd_explicit, prd_dir, no_tui).

    *prd_explicit* is ``True`` when the user passed ``--prd`` on the command
    line.  When it is ``False`` the caller should launch the interactive file
    browser to let the user choose a PRD.

    *prd_dir* is the resolved directory to scan for PRDs.  ``None`` means
    "use the browser default (cwd/docs/prds)".  A non-``None`` value means
    the directory was explicitly configured via ``--prd-dir`` or
    ``prd_directory`` in the config file.

    *no_tui* is ``True`` when ``--no-tui`` was passed.  The caller should
    also force headless mode when stdout is not a TTY.
    """
    parser = argparse.ArgumentParser(
        prog="ralph",
        description="Autonomous coding agent loop powered by Claude",
    )
    parser.add_argument(
        "iterations",
        type=int,
        nargs="?",
        default=None,
        help="Number of iterations to run (default: 20)",
    )
    parser.add_argument(
        "--prd",
        type=Path,
        default=None,
        help="Path to PRD file (omit to use the interactive file browser)",
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
        "--max-turns", type=int, default=None, help="Max turns per iteration"
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
    parser.add_argument(
        "--prd-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Directory to scan for docs when using the interactive browser "
            "(also reads prd_directory from ~/.ralph/config.json; default: docs/)"
        ),
    )
    parser.add_argument(
        "--no-tui",
        action="store_true",
        default=False,
        help=(
            "Disable the Textual TUI and use the legacy Rich output instead. "
            "Automatically enabled when stdout is not a TTY (e.g. piped output, CI)."
        ),
    )

    args = parser.parse_args(argv)

    # Track whether the user explicitly provided --prd so main() can decide
    # whether to show the interactive browser.
    prd_explicit: bool = args.prd is not None
    prd: Path = args.prd if prd_explicit else Path("PRD.md")

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

    # Resolve iterations: CLI flag > config file > default (20)
    _iterations_default = 20
    if args.iterations is not None:
        iterations: int = args.iterations
    else:
        iterations = int(file_config.get("iterations", _iterations_default))

    # Resolve PRD scan directory: CLI flag > config file > None (use browser default)
    if args.prd_dir is not None:
        # User explicitly passed --prd-dir; resolve relative paths against cwd.
        prd_dir: Path | None = (
            args.prd_dir if args.prd_dir.is_absolute() else args.cwd / args.prd_dir
        )
    elif "prd_directory" in file_config:
        prd_dir = args.cwd / file_config["prd_directory"]
    else:
        prd_dir = None

    return (
        RalphConfig(
            prd=prd,
            tasks=args.tasks,
            iterations=iterations,
            cwd=args.cwd,
            permission_mode=args.permission_mode,
            model=args.model,
            max_turns=args.max_turns,
            discord_webhook_url=discord_webhook_url,
            discord_min_interval=discord_min_interval,
        ),
        prd_explicit,
        prd_dir,
        args.no_tui,
    )
