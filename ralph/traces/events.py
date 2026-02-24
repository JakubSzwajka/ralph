"""Event schema for agent trace recording."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclasses.dataclass
class TextEvent:
    type: str = dataclasses.field(default="text", init=False)
    text: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self))


@dataclasses.dataclass
class ThinkingEvent:
    type: str = dataclasses.field(default="thinking", init=False)
    thinking: str = ""
    signature: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self))


@dataclasses.dataclass
class ToolUseEvent:
    type: str = dataclasses.field(default="tool_use", init=False)
    name: str = ""
    input: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self))


@dataclasses.dataclass
class ToolResultEvent:
    type: str = dataclasses.field(default="tool_result", init=False)
    tool_use_id: str = ""
    content: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self))


@dataclasses.dataclass
class UserMessageEvent:
    type: str = dataclasses.field(default="user_message", init=False)
    content: str = ""
    timestamp: str = dataclasses.field(default_factory=_now_iso)

    def to_json_line(self) -> str:
        return json.dumps(dataclasses.asdict(self))


AnyEvent = TextEvent | ThinkingEvent | ToolUseEvent | ToolResultEvent | UserMessageEvent
