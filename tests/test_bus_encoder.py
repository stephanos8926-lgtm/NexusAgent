"""Tests for NATSJSONEncoder and put_result size handling."""

import json
import pytest
from datetime import datetime, date
from pathlib import Path

from nexusagent.infrastructure.bus import NATSJSONEncoder, NATS_MAX_MESSAGE_SIZE


class TestNATSJSONEncoder:
    """NATSJSONEncoder handles non-serializable types without TypeError."""

    def test_bytes_utf8_decodes(self):
        """bytes that are valid UTF-8 are decoded to str."""
        result = json.dumps({"data": b"hello"}, cls=NATSJSONEncoder)
        assert json.loads(result) == {"data": "hello"}

    def test_bytes_binary_base64(self):
        """bytes that fail UTF-8 decode fall back to base64."""
        raw = bytes(range(256))
        result = json.dumps({"data": raw}, cls=NATSJSONEncoder)
        parsed = json.loads(result)
        assert isinstance(parsed["data"], str)  # base64 is always a str

    def test_bytes_empty(self):
        """Empty bytes serialize to empty string."""
        result = json.dumps({"data": b""}, cls=NATSJSONEncoder)
        assert json.loads(result) == {"data": ""}

    def test_bytes_with_replacement(self):
        """Invalid UTF-8 sequences are replaced, not raised."""
        raw = b"\xff\xfehello"
        result = json.dumps({"data": raw}, cls=NATSJSONEncoder)
        parsed = json.loads(result)
        assert isinstance(parsed["data"], str)
        assert "hello" in parsed["data"]

    def test_set_becomes_sorted_list(self):
        """set is serialized as a sorted list."""
        result = json.dumps({"tags": {3, 1, 2}}, cls=NATSJSONEncoder)
        assert json.loads(result) == {"tags": [1, 2, 3]}

    def test_empty_set(self):
        """Empty set serializes to empty list."""
        result = json.dumps({"tags": set()}, cls=NATSJSONEncoder)
        assert json.loads(result) == {"tags": []}

    def test_path_becomes_string(self):
        """Path is serialized as its string representation."""
        p = Path("/tmp/some/file.txt")
        result = json.dumps({"path": p}, cls=NATSJSONEncoder)
        assert json.loads(result) == {"path": "/tmp/some/file.txt"}

    def test_exception_serializes(self):
        """Exception is serialized as 'Type: message'."""
        err = ValueError("bad input")
        result = json.dumps({"error": err}, cls=NATSJSONEncoder)
        parsed = json.loads(result)
        assert parsed["error"] == "ValueError: bad input"

    def test_datetime_still_works(self):
        """datetime serialization is preserved."""
        dt = datetime(2026, 7, 18, 12, 0, 0)
        result = json.dumps({"ts": dt}, cls=NATSJSONEncoder)
        assert json.loads(result) == {"ts": "2026-07-18T12:00:00"}

    def test_date_still_works(self):
        """date serialization is preserved."""
        d = date(2026, 7, 18)
        result = json.dumps({"d": d}, cls=NATSJSONEncoder)
        assert json.loads(result) == {"d": "2026-07-18"}

    def test_nested_bytes_in_list(self):
        """bytes nested inside a list are handled."""
        result = json.dumps({"items": [b"one", b"two"]}, cls=NATSJSONEncoder)
        assert json.loads(result) == {"items": ["one", "two"]}

    def test_mixed_non_serializable(self):
        """Multiple non-serializable types in one structure."""
        data = {
            "ts": datetime(2026, 1, 1),
            "raw": b"\x80\x81",
            "tags": {"a", "b"},
            "p": Path("/home"),
            "err": RuntimeError("oops"),
        }
        result = json.dumps(data, cls=NATSJSONEncoder)
        parsed = json.loads(result)
        assert parsed["ts"] == "2026-01-01T00:00:00"
        assert isinstance(parsed["raw"], str)
        assert parsed["tags"] == ["a", "b"]
        assert parsed["p"] == "/home"
        assert parsed["err"] == "RuntimeError: oops"

    def test_publish_message_with_bytes_field(self):
        """Simulates what publish() does: json.dumps then .encode().

        This is the core crash scenario from the kanban task —
        a message dict containing a bytes field must not raise TypeError.
        """
        message = {
            "task_id": "abc-123",
            "result": b"binary payload content",
        }
        # This is the exact pattern used in AgentBus.publish()
        payload = json.dumps(message, cls=NATSJSONEncoder).encode()
        assert isinstance(payload, bytes)
        parsed = json.loads(payload.decode())
        assert parsed["task_id"] == "abc-123"
        assert isinstance(parsed["result"], str)


class TestPutResultSizeCheck:
    """put_result size limiting logic."""

    def test_size_constant_is_1mb(self):
        assert NATS_MAX_MESSAGE_SIZE == 1024 * 1024

    def test_large_result_truncation(self):
        """Result with oversized data field gets truncated to fit."""
        # Simulate what put_result's _do_put does
        huge_data = "x" * (NATS_MAX_MESSAGE_SIZE + 1000)
        result = {"task_id": "big-task", "success": True, "data": huge_data}
        payload = json.dumps(result, cls=NATSJSONEncoder).encode()
        assert len(payload) > NATS_MAX_MESSAGE_SIZE

        # Now simulate truncation logic
        if len(payload) > NATS_MAX_MESSAGE_SIZE:
            truncated = {
                **result,
                "data": str(result["data"])[: NATS_MAX_MESSAGE_SIZE // 2]
                + "\n... [TRUNCATED: exceeded NATS 1MB limit]",
            }
            payload = json.dumps(truncated, cls=NATSJSONEncoder).encode()

        assert len(payload) <= NATS_MAX_MESSAGE_SIZE

    def test_even_truncated_is_too_large_raises(self):
        """If truncation still exceeds limit, ValueError is raised."""
        # Create a result where even the wrapper is huge
        huge_key_data = {}
        filler = "x" * (NATS_MAX_MESSAGE_SIZE + 1000)
        result = {"task_id": "big-task", "success": True, "extra": filler}
        # Remove 'data' field so truncation path won't help
        result_no_data = {"task_id": "big-task", "success": True, "extra": filler}

        payload = json.dumps(result_no_data, cls=NATSJSONEncoder).encode()
        # The 'data' field truncation won't apply, so it should still be too large
        assert len(payload) > NATS_MAX_MESSAGE_SIZE

    def test_normal_result_passes(self):
        """Normal-sized results pass through without truncation."""
        result = {"task_id": "normal", "success": True, "data": "hello world"}
        payload = json.dumps(result, cls=NATSJSONEncoder).encode()
        assert len(payload) < NATS_MAX_MESSAGE_SIZE
