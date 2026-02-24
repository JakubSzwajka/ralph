---
prd: local-config
generated: 2026-02-24
last-updated: 2026-02-24
---

# Tasks: Local Configuration File

> Summary: Add `~/.ralph/config.json` loading with standard CLI > env > config > defaults precedence chain.

## Task List

- [x] **1. Add config loader module** — read and parse `~/.ralph/config.json`
- [x] **2. Integrate config into CLI** — merge loaded config into `parse_args` precedence chain
- [x] **3. Handle errors and edge cases** — malformed JSON, unknown keys, missing dir

---

### 1. Add config loader module
<!-- status: done -->

Create `ralph/config.py` with a function that reads `~/.ralph/config.json` and returns a dict. If the file doesn't exist, return an empty dict silently. Define a constant for the config path (`~/.ralph/config.json`). Keep it minimal — just read + `json.load` + return.

**Files:** `ralph/config.py` (new), `tests/test_config.py` (new)
**Depends on:** —
**Validates:** Calling the loader with no config file returns `{}`. Calling it with a valid JSON file returns the parsed dict.

---

### 2. Integrate config into CLI
<!-- status: done -->

In `ralph/cli.py`, call the config loader before building `RalphConfig`. Apply precedence: CLI flag wins over env var, env var wins over config file value, config file wins over defaults. Wire up `discord_webhook_url` and `discord_min_interval` from the config file. The config file keys should match the JSON shape, e.g. `{"discord_webhook_url": "...", "discord_min_interval": 10}`.

**Files:** `ralph/cli.py`, `tests/test_cli_config.py` (new)
**Depends on:** 1
**Validates:** Running `ralph` with `discord_webhook_url` set in `~/.ralph/config.json` (and no CLI flag or env var) picks up the webhook URL. CLI flag still overrides config file.

---

### 3. Handle errors and edge cases
<!-- status: done -->

Add error handling in the config loader: if JSON is malformed, print a clear error message to stderr and exit with code 1. Unknown keys in the JSON should be silently ignored (don't pass them through). Ensure `~/.ralph/` directory missing is not an error.

**Files:** `ralph/config.py`, `tests/test_config.py`
**Depends on:** 1
**Validates:** A config file with invalid JSON prints an error and exits. A config file with `{"foo": "bar"}` loads without error and the unknown key is dropped.

---
