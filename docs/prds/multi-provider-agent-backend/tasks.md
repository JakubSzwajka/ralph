---
prd: multi-provider-agent-backend
generated: 2026-03-02
last-updated: 2026-03-02
---

# Tasks: Provider-Agnostic Agent Backend (Claude + Codex CLI)

> Summary: Add a provider abstraction so Ralph can run with Claude (existing behavior) or Codex CLI (new behavior), with provider-aware config, validation, metadata, and docs.

## Task List

- [ ] **1. Add provider primitives to core config** — introduce provider as a first-class run setting and remove Claude-only typing from shared config.
- [ ] **2. Add provider selection to CLI and file config** — support `--provider` with clear precedence and defaults. `[blocked by: 1]`
- [ ] **3. Persist and display provider in run metadata** — include provider in stored run records and history/detail views. `[blocked by: 2]`
- [ ] **4. Introduce provider interface and registry** — create a normalized contract for provider adapters and runtime dispatch. `[blocked by: 1]`
- [ ] **5. Move current Claude logic into a Claude adapter** — preserve existing behavior behind the new provider interface. `[blocked by: 4]`
- [ ] **6. Implement Codex CLI adapter** — add a second adapter that executes iterations through Codex CLI with streamed output. `[blocked by: 4]`
- [ ] **7. Wire provider validation and runtime selection in the loop** — route iterations through the selected adapter and fail fast on invalid provider/model/permission combos. `[blocked by: 2, 5, 6]`
- [ ] **8. Add regression tests for provider-aware flow** — cover argument parsing, registry dispatch, and metadata round-trip behavior. `[blocked by: 3, 7]`
- [ ] **9. Update docs to provider-agnostic language and examples** — document Claude + Codex usage and new configuration surface. `[blocked by: 2, 3, 7]`

---

### 1. Add provider primitives to core config
<!-- status: pending -->

Create provider-neutral types used by run configuration so `RalphConfig` no longer imports Claude-specific SDK types in shared core code. Add a `provider` field with default `claude`, keep backward compatibility for existing runs, and define a single source of truth for allowed provider names. This task should establish the foundational types other tasks can reuse without circular imports.

**Files:** `ralph/core/config.py`, `ralph/core/__init__.py`, `ralph/providers/types.py`, `ralph/providers/__init__.py`
**Depends on:** —
**Validates:** Importing `RalphConfig` works without provider SDK side effects, and `RalphConfig()` defaults to provider `claude`.

---

### 2. Add provider selection to CLI and file config
<!-- status: pending -->

Expose provider choice in argument parsing using `--provider` (initial values: `claude`, `codex`) and merge it with existing config precedence rules. Extend `~/.ralph/config.json` support so provider can be set globally but overridden on the CLI. Keep current command behavior unchanged when `--provider` is omitted.

**Files:** `ralph/cli/args.py`, `ralph/config/loader.py`
**Depends on:** 1
**Validates:** `ralph --help` lists `--provider`, and parsed config resolves provider via CLI > config file > default.

---

### 3. Persist and display provider in run metadata
<!-- status: pending -->

Add provider to `RunMeta` serialization/deserialization so every run record stores which backend executed it. Update run history/detail rendering and run confirmation/headless summary surfaces to include provider next to model. Ensure older `meta.json` files without provider still load safely.

**Files:** `ralph/core/run_meta.py`, `ralph/tui/screens/run_browser.py`, `ralph/tui/screens/confirm_run.py`, `ralph/cli/headless.py`
**Depends on:** 2
**Validates:** New runs write `provider` in `.ralph/runs/*/meta.json`, and history/details show the provider without breaking legacy run entries.

---

### 4. Introduce provider interface and registry
<!-- status: pending -->

Define a normalized adapter contract for one iteration execution (input config + prompt, output streamed text/events + completion signal compatibility). Implement a registry/factory that resolves adapter implementations from provider name and produces clear errors for unsupported values. Keep this layer free of provider-specific business logic.

**Files:** `ralph/providers/base.py`, `ralph/providers/registry.py`, `ralph/providers/__init__.py`
**Depends on:** 1
**Validates:** Registry returns a concrete adapter for `claude` and `codex`, and unknown providers raise an actionable error.

---

### 5. Move current Claude logic into a Claude adapter
<!-- status: pending -->

Extract the existing `claude_agent_sdk` option-building and stream parsing from `ralph/core/loop.py` into a dedicated Claude adapter that implements the provider contract. Preserve current output formatting behavior, including suppression of internal thinking/result blocks and early completion handling. The objective is behavior parity, not feature expansion.

**Files:** `ralph/providers/claude.py`, `ralph/core/loop.py`, `ralph/core/format_stream.py`
**Depends on:** 4
**Validates:** Running with provider `claude` produces equivalent streamed output and completion behavior to current main branch behavior.

---

### 6. Implement Codex CLI adapter
<!-- status: pending -->

Add a Codex adapter that executes through the Codex CLI process and converts streamed output into the normalized provider contract. Handle startup failures (for example missing binary or auth issues) with explicit, user-facing error text and non-hanging execution. Keep model forwarding/provider-specific options encapsulated inside this adapter.

**Files:** `ralph/providers/codex.py`, `ralph/providers/base.py`, `ralph/providers/registry.py`
**Depends on:** 4
**Validates:** `ralph --provider codex ...` enters the run loop and either streams output or exits quickly with a clear adapter startup error.

---

### 7. Wire provider validation and runtime selection in the loop
<!-- status: pending -->

Refactor loop orchestration to select adapter by `config.provider`, run the provider contract, and keep `IterationResult` semantics unchanged for callers. Add centralized validation for provider/model/permission compatibility before execution begins so invalid combinations fail fast in both headless and TUI paths. Ensure `execute_run` and UI entry points surface these errors consistently.

**Files:** `ralph/core/loop.py`, `ralph/core/executor.py`, `ralph/cli/app.py`, `ralph/cli/args.py`, `ralph/providers/validate.py`
**Depends on:** 2, 5, 6
**Validates:** Invalid provider combinations fail before starting a run, and valid Claude/Codex runs both produce `IterationResult` updates through existing callbacks.

---

### 8. Add regression tests for provider-aware flow
<!-- status: pending -->

Create targeted tests for provider parsing precedence, run metadata round-trip compatibility, and adapter registry dispatch. Add at least one loop-level test that exercises provider selection via a lightweight stub adapter so core loop behavior is verified independent of external provider binaries. Keep tests deterministic and runnable in CI without real API credentials.

**Files:** `tests/test_cli_args.py`, `tests/test_run_meta.py`, `tests/test_provider_registry.py`, `tests/test_loop_provider_dispatch.py`
**Depends on:** 3, 7
**Validates:** `uv run pytest` passes locally with the new provider tests and no network dependency.

---

### 9. Update docs to provider-agnostic language and examples
<!-- status: pending -->

Update top-level and module READMEs to remove Claude-only positioning and document provider selection, expected setup, and examples for both `claude` and `codex`. Reflect any new config keys and clarify fallback/default behavior. Keep documentation aligned with implemented flags and runtime metadata fields.

**Files:** `README.md`, `ralph/core/README.md`, `ralph/cli/README.md`
**Depends on:** 2, 3, 7
**Validates:** Documentation consistently references multi-provider support and includes at least one working `--provider` usage example.

