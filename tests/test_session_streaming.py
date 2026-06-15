"""Tests for session streaming — verify astream() emits response_chunk events."""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessageChunk

from nexusagent.infrastructure.db import DatabaseManager, SessionRepository
from nexusagent.core.session import Session, SessionManager


@pytest.fixture
async def db_and_repo():
    """Create a temporary DatabaseManager + SessionRepository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db_manager = DatabaseManager(db_url=f"sqlite+aiosqlite:///{db_path}")
        await db_manager.init_db()
        repo = SessionRepository(db_manager)
        yield db_manager, repo


@pytest.fixture
def mock_memory():
    """A mock memory with async recall/remember."""
    mem = AsyncMock()
    mem.recall = AsyncMock(return_value=[])
    mem.remember = AsyncMock(return_value="mem-123")
    return mem


def _make_streaming_agent(chunks: list[str]):
    """Create a mock agent that yields AIMessageChunks via astream()."""
    agent = MagicMock()

    async def _astream(input_data, stream_mode=None, **kwargs):
        for chunk_text in chunks:
            yield AIMessageChunk(content=chunk_text)

    agent.astream = _astream
    return agent


@pytest.mark.asyncio
async def test_session_streaming_emits_chunks(db_and_repo, mock_memory):
    """send() should emit one response_chunk per token from astream()."""
    _, repo = db_and_repo
    manager = SessionManager()

    chunks = ["Hello ", "world", "!"]
    agent = _make_streaming_agent(chunks)

    sid = "test-stream-001"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=agent,
        memory=mock_memory,
        db_repo=repo,
    )

    await session.send("Test streaming")

    # Drain all events
    events = []
    while not session._event_queue.empty():
        events.append(session._event_queue.get_nowait())

    # Should have response_chunk events for each token
    chunk_events = [e for e in events if e.get("type") == "response_chunk"]
    assert len(chunk_events) == 3, f"Expected 3 chunk events, got {len(chunk_events)}"
    assert chunk_events[0]["content"] == "Hello "
    assert chunk_events[1]["content"] == "world"
    assert chunk_events[2]["content"] == "!"

    # Should have a final response event
    response_events = [e for e in events if e.get("type") == "response"]
    assert len(response_events) == 1
    assert response_events[0]["content"] == "Hello world!"


@pytest.mark.asyncio
async def test_session_streaming_tool_call_events(db_and_repo, mock_memory):
    """send() should emit tool_call events from tool_call_chunks in astream()."""
    _, repo = db_and_repo
    manager = SessionManager()

    agent = MagicMock()

    async def _astream(input_data, stream_mode=None, **kwargs):
        # Simulate a tool call chunk
        yield AIMessageChunk(
            content="",
            tool_call_chunks=[
                {"index": 0, "id": "call-1", "name": "read_file", "args": '{"path": "test.py"}'},
            ],
        )
        # Simulate text response
        yield AIMessageChunk(content="Done")

    agent.astream = _astream

    sid = "test-stream-002"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=agent,
        memory=mock_memory,
        db_repo=repo,
    )

    await session.send("Read a file")

    events = []
    while not session._event_queue.empty():
        events.append(session._event_queue.get_nowait())

    # Should have tool_call event
    tool_events = [e for e in events if e.get("type") == "tool_call"]
    assert len(tool_events) == 1
    assert tool_events[0]["tool"] == "read_file"
    assert tool_events[0]["call_id"] == "call-1"

    # Should have response_chunk for text
    chunk_events = [e for e in events if e.get("type") == "response_chunk"]
    assert len(chunk_events) == 1
    assert chunk_events[0]["content"] == "Done"


@pytest.mark.asyncio
async def test_session_streaming_empty_response(db_and_repo, mock_memory):
    """send() with no tokens should still emit a response event."""
    _, repo = db_and_repo
    manager = SessionManager()

    agent = _make_streaming_agent([])

    sid = "test-stream-003"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=agent,
        memory=mock_memory,
        db_repo=repo,
    )

    await session.send("Empty")

    events = []
    while not session._event_queue.empty():
        events.append(session._event_queue.get_nowait())

    response_events = [e for e in events if e.get("type") == "response"]
    assert len(response_events) == 1
    assert response_events[0]["content"] == ""


@pytest.mark.asyncio
async def test_session_streaming_error_during_stream(db_and_repo, mock_memory):
    """send() should emit ErrorEvent if astream() raises mid-stream."""
    _, repo = db_and_repo
    manager = SessionManager()

    agent = MagicMock()

    async def _bad_astream(input_data, stream_mode=None, **kwargs):
        yield AIMessageChunk(content="Partial")
        raise RuntimeError("Connection lost")

    agent.astream = _bad_astream

    sid = "test-stream-004"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=agent,
        memory=mock_memory,
        db_repo=repo,
    )

    await session.send("Trigger error")

    events = []
    while not session._event_queue.empty():
        events.append(session._event_queue.get_nowait())

    # Should have partial chunk
    chunk_events = [e for e in events if e.get("type") == "response_chunk"]
    assert len(chunk_events) == 1
    assert chunk_events[0]["content"] == "Partial"

    # Should have error event
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) == 1
    assert "Connection lost" in error_events[0]["message"]
