from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


CONFIG_PATH = Path.home() / ".ralph" / "config.json"

# Keys recognised in the config file; unknown keys are silently ignored.
_KNOWN_KEYS: frozenset[str] = frozenset(
    {
        "discord_webhook_url",
        "discord_min_interval",
        "prd_directory",
    }
)


def load_config() -> dict[str, Any]:
    """Read ~/.ralph/config.json and return the parsed dict.

    Returns an empty dict if the file does not exist (silently ignores missing
    file or missing directory).  Unknown keys are silently dropped.

    Exits with code 1 and prints a message to stderr if the file contains
    invalid JSON.
    """
    if not CONFIG_PATH.exists():
        return {}

    try:
        with CONFIG_PATH.open() as f:
            raw: dict[str, object] = json.load(f)
    except json.JSONDecodeError as exc:
        print(
            f"ralph: error: {CONFIG_PATH} contains invalid JSON — {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Silently drop unknown keys to stay forward-compatible.
    return {k: v for k, v in raw.items() if k in _KNOWN_KEYS}
