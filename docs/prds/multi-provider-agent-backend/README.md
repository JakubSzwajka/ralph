---
status: draft
date: 2026-03-02
author: "kuba.szwajka + codex"
gh-issue: ""
---

# Provider-Agnostic Agent Backend (Claude + Codex CLI)

## Problem

Ralph currently supports only Claude through `claude-agent-sdk`, and this coupling is embedded in core runtime code and user-facing CLI text. Users who prefer Codex CLI (or need to switch between providers by task, environment, or cost) cannot use Ralph without rewriting core modules. This limits adoption and makes future provider integrations expensive because each provider-specific assumption leaks into config, loop orchestration, and stream formatting. We need a provider abstraction so the runtime can choose an AI backend dynamically while preserving the same PRD-driven workflow.

## Proposed Solution

Introduce a provider interface module that defines the contract Ralph core uses for iteration execution and stream events. Implement two adapters: one for existing Claude behavior and one for Codex CLI behavior, then add configuration and CLI flags to select provider explicitly (with sensible defaults). Refactor the current loop so provider-specific SDK imports and message parsing move out of `ralph/core/loop.py` into isolated provider packages. Keep higher-level Ralph behavior unchanged: same PRD/task progression, completion signal semantics, run metadata, and TUI/headless UX. When done, users can switch providers without changing business flow logic.

## Key Cases

- User runs `ralph` with default settings and gets current Claude behavior with no regression.
- User runs `ralph --provider codex` and executes iterations through Codex CLI with streamed output in the same UI surfaces.
- User selects provider + model together (`--provider ... --model ...`) and receives clear validation when a model is incompatible with the chosen provider.
- Core run metadata persists provider and model so history screens and logs show which backend was used.
- Tests can run provider-specific logic via adapter tests while keeping existing loop tests provider-neutral.

## Out of Scope

- Building a generic plugin marketplace or dynamic provider loading from third-party packages.
- Supporting more than two providers in this first increment (target: Claude + Codex CLI only).
- Redesigning TUI/CLI user experience beyond provider/model selection and validation messaging.
- Rewriting prompt strategy, task semantics, or completion protocol.

## Open Questions

- Should provider selection live only in CLI/config, or also be inferable from environment (for CI portability)?
- What is the minimal normalized stream-event schema that can represent both Claude SDK events and Codex CLI output without losing useful detail?
- Should Codex integration use direct Python bindings (if available) or shell orchestration through the existing Codex CLI binary?
- Do we need provider-specific permission mode mapping, or should unsupported modes fail fast during config validation?

## References

- `ralph/core/loop.py` (Claude-coupled iteration logic)
- `ralph/core/config.py` (Claude-specific permission type import)
- `ralph/cli/args.py` (Claude wording in CLI description and `--model` help)
- `README.md` (project positioning currently Claude-only)
