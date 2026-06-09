"""Tests for nexusagent.session — Session and SessionManager."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.db import DatabaseManager, SessionRepository
from nexusagent.session import SessionManager, session_manager

# ── Fixtures ───────────────────────────────────────────────────────────


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
def mock_agent():
    """A mock agent that returns a simple string."""
    agent = MagicMock()
    agent.return_value = "Hello from agent"
    return agent


@pytest.fixture
def mock_memory():
    """A mock memory with async recall/remember."""
    mem = AsyncMock()
    mem.recall = AsyncMock(return_value=[])
    mem.remember = AsyncMock(return_value="mem-123")
    return mem


# ── Tests: SessionManager ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_session_creation(db_and_repo, mock_agent, mock_memory):
    """Create a session via manager, verify ID and status."""
    _, repo = db_and_repo
    manager = SessionManager()

    sid = "test-session-001"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )

    assert session is not None
    assert session.session_id == sid
    assert session.status == "active"
    assert session.working_dir == "/tmp/work"

    # Verify it's cached
    assert manager.get(sid) is session
    assert manager.active_count == 1


@pytest.mark.asyncio
async def test_session_send_and_events(db_and_repo, mock_agent, mock_memory):
    """Create a session, call send(), verify no exception and events are queued."""
    _, repo = db_and_repo
    manager = SessionManager()

    sid = "test-session-002"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )

    # send() should not raise
    await session.send("Hello, agent!")

    # Verify the agent was called
    mock_agent.assert_called_once()

    # Verify events were queued (at least one)
    assert session._event_queue.qsize() >= 1

    # Drain the queue and check for a response event
    events = []
    while not session._event_queue.empty():
        events.append(session._event_queue.get_nowait())

    # Should have a response event
    response_events = [e for e in events if e.get("type") == "response"]
    assert len(response_events) >= 1
    assert response_events[0]["content"] == "Hello from agent"


@pytest.mark.asyncio
async def test_session_close(db_and_repo, mock_agent, mock_memory):
    """Create a session, close it, verify status='closed'."""
    _, repo = db_and_repo
    manager = SessionManager()

    sid = "test-session-003"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )

    assert session.status == "active"

    await manager.close(sid)

    assert session.status == "closed"
    assert manager.get(sid) is None
    assert manager.active_count == 0


@pytest.mark.asyncio
async def test_session_manager_mark_idle(db_and_repo, mock_agent, mock_memory):
    """Mark a session idle and verify status transition."""
    _, repo = db_and_repo
    manager = SessionManager()

    sid = "test-session-004"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )

    assert session.status == "active"
    await manager.mark_idle(sid)
    assert session.status == "idle"


@pytest.mark.asyncio
async def test_session_manager_get_existing(db_and_repo, mock_agent, mock_memory):
    """get_or_create returns the same session for the same ID."""
    _, repo = db_and_repo
    manager = SessionManager()

    sid = "test-session-005"
    s1 = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )
    s2 = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )

    assert s1 is s2
    assert manager.active_count == 1


@pytest.mark.asyncio
async def test_session_send_error_handling(db_and_repo, mock_memory):
    """send() should emit ErrorEvent when agent raises."""
    _, repo = db_and_repo
    manager = SessionManager()

    # Agent that raises
    bad_agent = MagicMock(side_effect=RuntimeError("LLM connection failed"))

    sid = "test-session-006"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=bad_agent,
        memory=mock_memory,
        db_repo=repo,
    )

    # Should not raise
    await session.send("trigger error")

    # Drain queue — should have an error event
    events = []
    while not session._event_queue.empty():
        events.append(session._event_queue.get_nowait())

    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) >= 1
    assert "LLM connection failed" in error_events[0]["message"]


@pytest.mark.asyncio
async def test_session_singleton():
    """The module-level session_manager is a SessionManager instance."""
    assert isinstance(session_manager, SessionManager)
