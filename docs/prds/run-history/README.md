---
status: done
date: 2026-02-24
author: kuba
gh-issue: ""
---

# Run History — Persist and Review Agent Traces

## Problem

Ralph runs are ephemeral. Once a session ends, the only trace is whatever the agent committed to git. There's no way to review what the agent did across iterations — what it tried, what tools it called, how long each step took, or why it made certain decisions. This makes it hard to learn from runs, debug issues, or brainstorm improvements.

## Proposed Solution

Persist full run traces to `.ralph/runs/` in the project directory. Each run gets a timestamped directory with a `meta.json` (config snapshot, totals, status) and one `iteration-NN.jsonl` per iteration containing the full stream of events (text, tool calls, tool results, thinking blocks). Add a `ralph runs` CLI command to list past runs and `ralph runs <id>` to print a summary of a specific run for review.

## Key Cases

- Every run automatically writes to `.ralph/runs/<timestamp>/`
- `meta.json` written at start (config) and updated at end (totals, completion status)
- Each iteration streams events to `iteration-01.jsonl`, `iteration-02.jsonl`, etc.
- JSONL format: one JSON object per event, appendable during streaming
- `ralph runs` lists past runs with date, PRD, iteration count, cost, status
- `ralph runs <id>` prints iteration summaries (duration, cost, key actions)
- `.ralph/runs/` added to `.gitignore` by default

## Out of Scope

- TUI viewer for runs (future — could integrate with interactive browser PRD)
- Run diffing or comparison between runs
- Remote storage or syncing of run history
- Automatic cleanup / retention policies

## Open Questions

- Should `meta.json` include the full system prompt or just a reference?
- Max disk usage concern — should we cap run retention or warn?

## References

- Stream events: `ralph/core.py:run_iteration()` lines 101-135
- CLI entry: `ralph/cli.py:main()`
