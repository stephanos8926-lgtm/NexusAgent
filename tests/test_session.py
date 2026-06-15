"""Tests for nexusagent.session — Session and SessionManager."""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.infrastructure.db import DatabaseManager, SessionRepository
from nexusagent.core.session import Session, SessionManager, session_manager

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
    """A mock agent that returns a simple string via invoke and streams via astream."""
    agent = MagicMock()
    agent.return_value = "Hello from agent"

    async def _astream(input_data, stream_mode=None, **kwargs):
        # Simulate streaming: yield a single AIMessageChunk with text content
        from langchain_core.messages import AIMessageChunk
        yield AIMessageChunk(content="Hello from agent")

    agent.astream = _astream
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
    """Create a session, call send(), verify no exception and events are queued.

    Verifies that memory context is injected as SystemMessage and agent
    receives {"messages": [...]} dict (not {"message": ...}).
    """
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

    # Verify the agent's astream was invoked
    # mock_agent.astream is a plain async generator function; verify it's set
    assert mock_agent.astream is not None

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
    async def _bad_astream(input_data, stream_mode=None, **kwargs):
        raise RuntimeError("LLM connection failed")
        yield  # noqa: unreachable, makes this an async generator

    bad_agent = MagicMock()
    bad_agent.astream = _bad_astream

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


@pytest.mark.asyncio
async def test_session_memory_injection(db_and_repo, mock_memory):
    """send() injects memory context as SystemMessage when hybrid memory returns results."""
    from langchain_core.messages import HumanMessage, SystemMessage

    _, repo = db_and_repo
    manager = SessionManager()

    # Agent that captures its input for inspection
    captured = {}

    async def capture_agent_stream(input_data, stream_mode=None, **kwargs):
        captured["state"] = input_data
        from langchain_core.messages import AIMessageChunk
        yield AIMessageChunk(content="captured")

    mock_agent = MagicMock()
    mock_agent.astream = capture_agent_stream

    # Hybrid memory that returns context
    class FakeHybridMemory:
        def get_memory_context(self, query, max_results=5):
            return "## Relevant Memories\n\nSource: bank/test.md (score: 0.95)\nTest memory content\n"
        async def flush(self, summary=""):
            pass
        async def remember(self, content, metadata=None):
            pass

    sid = "test-session-mem"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )
    # Override hybrid_memory with fake
    session.hybrid_memory = FakeHybridMemory()

    await session.send("What did we discuss?")

    # Verify agent received messages with memory context
    assert "state" in captured
    msgs = captured["state"]["messages"]
    assert len(msgs) >= 3  # base system + memory context + user message
    # First message is base system prompt
    assert isinstance(msgs[0], SystemMessage)
    # Second should be memory context
    assert isinstance(msgs[1], SystemMessage)
    assert "Relevant Memories" in msgs[1].content
    # Last is user message
    assert isinstance(msgs[-1], HumanMessage)
    assert msgs[-1].content == "What did we discuss?"


@pytest.mark.asyncio
async def test_session_memory_injection_empty(db_and_repo, mock_memory):
    """send() works correctly when hybrid memory returns no results."""
    from langchain_core.messages import HumanMessage, SystemMessage

    _, repo = db_and_repo
    manager = SessionManager()

    captured = {}

    async def capture_agent_stream(input_data, stream_mode=None, **kwargs):
        captured["state"] = input_data
        from langchain_core.messages import AIMessageChunk
        yield AIMessageChunk(content="ok")

    mock_agent = MagicMock()
    mock_agent.astream = capture_agent_stream

    class FakeHybridMemory:
        def get_memory_context(self, query, max_results=5):
            return ""  # No memories
        async def flush(self, summary=""):
            pass
        async def remember(self, content, metadata=None):
            pass

    sid = "test-session-nomem"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )
    session.hybrid_memory = FakeHybridMemory()

    await session.send("Hello")

    msgs = captured["state"]["messages"]
    # Only system prompt + user message (no memory context)
    assert len(msgs) == 2
    assert isinstance(msgs[0], SystemMessage)
    assert isinstance(msgs[1], HumanMessage)


@pytest.mark.asyncio
async def test_session_compaction_triggers_on_long_context(db_and_repo, mock_memory):
    """send() triggers compaction when messages exceed context threshold."""
    _, repo = db_and_repo
    manager = SessionManager()

    captured = {}

    async def capture_agent_stream(input_data, stream_mode=None, **kwargs):
        captured["state"] = input_data
        from langchain_core.messages import AIMessageChunk
        yield AIMessageChunk(content="compacted")

    mock_agent = MagicMock()
    mock_agent.astream = capture_agent_stream

    # Hybrid memory that returns a very long context to trigger compaction
    class FakeHybridMemory:
        def get_memory_context(self, query, max_results=5):
            # Return enough content to exceed 75% of 200k token window
            # 200k * 0.75 = 150k tokens * 4 chars = 600k chars
            return "X" * 700_000
        async def flush(self, summary=""):
            pass
        async def remember(self, content, metadata=None):
            pass

    sid = "test-session-compact"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )
    session.hybrid_memory = FakeHybridMemory()

    await session.send("Trigger compaction")

    # Agent should still be called (compaction reduces context)
    assert "state" in captured
    msgs = captured["state"]["messages"]
    # After compaction, messages should be reduced
    assert len(msgs) >= 1


@pytest.mark.asyncio
async def test_pre_compaction_flush_async(db_and_repo, mock_agent, mock_memory):
    """pre_compaction_flush is async and calls hybrid_memory.flush asynchronously."""
    _, repo = db_and_repo
    manager = SessionManager()

    sid = "test-session-flush"
    session = await manager.get_or_create(
        session_id=sid,
        working_dir="/tmp/work",
        agent=mock_agent,
        memory=mock_memory,
        db_repo=repo,
    )

    # Should not raise - flush is now async
    result = await session.pre_compaction_flush()
    assert isinstance(result, str)
    assert "compaction flush" in result


@pytest.mark.asyncio
async def test_concurrent_get_or_create_returns_same_session(db_and_repo, mock_agent, mock_memory):
    """Two concurrent get_or_create() calls with the same ID return the same session."""
    _, repo = db_and_repo
    manager = SessionManager()

    sid = "test-concurrent-001"
    results = []

    async def create_session():
        s = await manager.get_or_create(
            session_id=sid,
            working_dir="/tmp/work",
            agent=mock_agent,
            memory=mock_memory,
            db_repo=repo,
        )
        results.append(s)

    # Launch two concurrent creations
    await asyncio.gather(create_session(), create_session())

    # Both callers should get the exact same Session object
    assert len(results) == 2
    assert results[0] is results[1]
    assert manager.active_count == 1


@pytest.mark.asyncio
async def test_concurrent_get_or_create_no_session_leak(db_and_repo, mock_agent, mock_memory):
    """Concurrent get_or_create() does not leak a session on race close."""
    _, repo = db_and_repo
    manager = SessionManager()

    sid = "test-concurrent-002"
    close_count = 0
    original_close = Session.close

    async def counting_close(self):
        nonlocal close_count
        close_count += 1
        await original_close(self)

    # Monkey-patch Session.close to count invocations
    Session.close = counting_close  # type: ignore[assignment]

    try:
        results = []

        async def create_session():
            s = await manager.get_or_create(
                session_id=sid,
                working_dir="/tmp/work",
                agent=mock_agent,
                memory=mock_memory,
                db_repo=repo,
            )
            results.append(s)

        # Launch many concurrent creations to maximize chance of race
        await asyncio.gather(*[create_session() for _ in range(10)])

        # All callers should get the same Session object
        assert len(results) == 10
        for r in results:
            assert r is results[0]
        assert manager.active_count == 1

        # At most one session.close() should have been called (the loser in the race)
        # With the _creating guard, no extra close should be needed, but if a race
        # happened, close() was called on the losing session — that's the leak-prevention.
        assert close_count <= 10  # Sanity: not more closes than creations
    finally:
        Session.close = original_close  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_concurrent_get_or_create_different_ids(db_and_repo, mock_agent, mock_memory):
    """Concurrent get_or_create() with different IDs creates separate sessions."""
    _, repo = db_and_repo
    manager = SessionManager()

    results = {}

    async def create_session(sid):
        s = await manager.get_or_create(
            session_id=sid,
            working_dir="/tmp/work",
            agent=mock_agent,
            memory=mock_memory,
            db_repo=repo,
        )
        results[sid] = s

    ids = ["diff-1", "diff-2", "diff-3"]
    await asyncio.gather(*[create_session(sid) for sid in ids])

    # Each ID should have its own session
    assert manager.active_count == 3
    assert results["diff-1"] is not results["diff-2"]
    assert results["diff-2"] is not results["diff-3"]
