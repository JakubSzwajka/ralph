# ralph/traces

Agent run trace recording. Captures every event from each iteration as JSONL files.

## How it works

```
.ralph/runs/
└── 2026-02-24T19-30-00/
    ├── meta.json              ← run config + completion status
    ├── iteration-01.jsonl     ← one JSON object per event
    ├── iteration-02.jsonl
    └── ...
```

Each line in a JSONL file is one event with a `type` discriminator and UTC timestamp.

## Event types

| Type | Fields | Description |
|---|---|---|
| `text` | `text` | Plain text from assistant |
| `thinking` | `thinking`, `signature` | Extended thinking block |
| `tool_use` | `name`, `input` | Agent calling a tool |
| `tool_result` | `tool_use_id`, `content` | Tool response |
| `user_message` | `content` | Injected user-turn message |

## Module layout

| File | Purpose |
|---|---|
| `events.py` | Event dataclasses with `to_json_line()` serialization |
| `writer.py` | `IterationWriter` (JSONL file), `RunRecorder` (run directory + meta) |

## Usage

```python
from ralph.traces import RunRecorder, TextEvent

recorder = RunRecorder(project_root)
recorder.write_meta_start(config)

with recorder.open_iteration(1) as writer:
    writer.write_event(TextEvent(text="hello"))

recorder.write_meta_end(results)
```

## Meta.json

Written at run start (config snapshot) and updated at run end:

```json
{
  "run_id": "2026-02-24T19-30-00",
  "started_at": "...",
  "completed_at": "...",
  "prd": "docs/prds/feature/README.md",
  "iterations_requested": 10,
  "iterations_completed": 3,
  "total_duration_s": 45.2,
  "status": "complete"
}
```

Status is one of: `complete`, `max-iterations`, `error`.
