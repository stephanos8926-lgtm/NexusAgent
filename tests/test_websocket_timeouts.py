# SPDX-License-Identifier: MIT

"""Tests for WebSocket timeout and bounded loop behavior."""

import logging

import pytest
from fastapi import WebSocketDisconnect

from nexusagent.server.websocket import _WRAPPED_TIMEOUT, _recv_with_timeout


class FakeWebSocket:
    def __init__(self, responses):
        self._responses = list(responses)
        self.closed = False
        self.sent = []
        self.headers = {}
        self.query_params = {}

    async def receive_text(self):
        if not self._responses:
            raise TimeoutError()
        return self._responses.pop(0)

    async def send_json(self, payload):
        self.sent.append(payload)

    async def close(self, code=None, reason=None):
        self.closed = True


@pytest.mark.asyncio
async def test_recv_with_timeout_returns_text():
    ws = FakeWebSocket(["hello"])
    result = await _recv_with_timeout(ws, timeout=0.1)
    assert result == "hello"


@pytest.mark.asyncio
async def test_recv_with_timeout_returns_none_on_timeout():
    ws = FakeWebSocket([])
    result = await _recv_with_timeout(ws, timeout=0.05)
    assert result is None


@pytest.mark.asyncio
async def test_recv_with_timeout_returns_disconnect_sentinel_on_exception():
    class ExplodingWS:
        async def receive_text(self):
            raise RuntimeError("boom")

    result = await _recv_with_timeout(ExplodingWS(), timeout=0.05)
    assert result == "__DISCONNECT__"


def test_wrapped_timeout_positive():
    assert _WRAPPED_TIMEOUT > 0


class DisconnectWS:
    async def receive_text(self):
        raise WebSocketDisconnect()


class ErrorWS:
    async def receive_text(self):
        raise RuntimeError("unexpected error")


@pytest.mark.asyncio
async def test_recv_with_timeout_distinguishes_disconnect_from_error(caplog):
    """WebSocketDisconnect should return __DISCONNECT__, other errors logged."""
    # WebSocketDisconnect -> __DISCONNECT__
    result = await _recv_with_timeout(DisconnectWS(), timeout=0.05)
    assert result == "__DISCONNECT__"

    # Other errors -> __DISCONNECT__ but logged
    with caplog.at_level(logging.ERROR):
        result = await _recv_with_timeout(ErrorWS(), timeout=0.05)
        assert result == "__DISCONNECT__"
        assert "WebSocket receive error" in caplog.text
