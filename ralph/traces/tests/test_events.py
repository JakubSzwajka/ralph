"""Tests for trace event schema."""
from __future__ import annotations

import json

from ralph.traces import (
    TextEvent,
    ThinkingEvent,
    ToolResultEvent,
    ToolUseEvent,
    UserMessageEvent,
)


class TestTextEvent:
    def test_to_json_line_has_type_text(self) -> None:
        assert json.loads(TextEvent(text="hello").to_json_line())["type"] == "text"

    def test_preserves_text(self) -> None:
        assert json.loads(TextEvent(text="world").to_json_line())["text"] == "world"

    def test_has_timestamp(self) -> None:
        assert json.loads(TextEvent(text="x").to_json_line())["timestamp"]

    def test_is_single_line(self) -> None:
        assert "\n" not in TextEvent(text="single").to_json_line()


class TestThinkingEvent:
    def test_type(self) -> None:
        assert json.loads(ThinkingEvent(thinking="t", signature="s").to_json_line())["type"] == "thinking"

    def test_fields(self) -> None:
        obj = json.loads(ThinkingEvent(thinking="deep", signature="abc").to_json_line())
        assert obj["thinking"] == "deep"
        assert obj["signature"] == "abc"


class TestToolUseEvent:
    def test_type(self) -> None:
        assert json.loads(ToolUseEvent(name="Bash", input="ls").to_json_line())["type"] == "tool_use"

    def test_fields(self) -> None:
        obj = json.loads(ToolUseEvent(name="Read", input="{'file': 'x'}").to_json_line())
        assert obj["name"] == "Read"


class TestToolResultEvent:
    def test_type(self) -> None:
        assert json.loads(ToolResultEvent(tool_use_id="id1", content="out").to_json_line())["type"] == "tool_result"


class TestUserMessageEvent:
    def test_type(self) -> None:
        assert json.loads(UserMessageEvent(content="hi").to_json_line())["type"] == "user_message"
