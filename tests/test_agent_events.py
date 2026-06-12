"""Tests for agent event types in models.py."""

import json

from nexusagent.llm.models import (
    ApprovalRequestEvent,
    ErrorEvent,
    ResponseEvent,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
)


def test_thinking_event():
    event = ThinkingEvent(content="Hmm, let me think...")
    assert event.type == "thinking"
    assert event.content == "Hmm, let me think..."


def test_thinking_event_default():
    event = ThinkingEvent()
    assert event.type == "thinking"
    assert event.content == ""


def test_tool_call_event():
    event = ToolCallEvent(tool="read_file", args={"path": "/tmp/f.txt"}, call_id="call-1")
    assert event.type == "tool_call"
    assert event.tool == "read_file"
    assert event.args == {"path": "/tmp/f.txt"}
    assert event.call_id == "call-1"


def test_tool_call_event_default_call_id():
    event = ToolCallEvent(tool="shell", args={"cmd": "ls"})
    assert event.call_id == ""


def test_tool_result_event():
    event = ToolResultEvent(call_id="call-1", output="file contents", success=True)
    assert event.type == "tool_result"
    assert event.call_id == "call-1"
    assert event.output == "file contents"
    assert event.success is True


def test_tool_result_event_defaults():
    event = ToolResultEvent(call_id="call-2")
    assert event.output == ""
    assert event.success is True


def test_approval_request_event():
    event = ApprovalRequestEvent(
        tool="shell",
        args={"cmd": "rm -rf /"},
        call_id="call-3",
        reason="Destructive command",
    )
    assert event.type == "approval_request"
    assert event.tool == "shell"
    assert event.args == {"cmd": "rm -rf /"}
    assert event.call_id == "call-3"
    assert event.reason == "Destructive command"


def test_approval_request_event_defaults():
    event = ApprovalRequestEvent(tool="shell", args={"cmd": "ls"})
    assert event.call_id == ""
    assert event.reason == ""


def test_response_event():
    event = ResponseEvent(content="Here is the answer.")
    assert event.type == "response"
    assert event.content == "Here is the answer."


def test_response_event_default():
    event = ResponseEvent()
    assert event.content == ""


def test_error_event():
    event = ErrorEvent(message="Something went wrong")
    assert event.type == "error"
    assert event.message == "Something went wrong"


def test_error_event_default():
    event = ErrorEvent()
    assert event.message == ""


def test_event_serialization():
    """Verify model_dump() produces valid JSON-serializable dicts for each event type."""
    events = [
        ThinkingEvent(content="pondering"),
        ToolCallEvent(tool="grep", args={"pattern": "foo"}, call_id="c1"),
        ToolResultEvent(call_id="c1", output="match found", success=True),
        ApprovalRequestEvent(tool="shell", args={"cmd": "reboot"}, reason="dangerous"),
        ResponseEvent(content="done"),
        ErrorEvent(message="oops"),
    ]
    for event in events:
        dumped = event.model_dump()
        # Must be JSON-serializable
        json_str = json.dumps(dumped)
        assert isinstance(json_str, str)
        # Round-trip check
        restored = json.loads(json_str)
        assert restored["type"] == dumped["type"]
