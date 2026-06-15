"""Tests for memory context injection into agent system prompt."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.core.session import Session


@pytest.fixture
def mock_session():
    """Create a session with mocked dependencies."""
    with (
        patch("nexusagent.core.session.SessionManager"),
        patch("nexusagent.memory.HybridMemoryManager") as mock_hmm,
    ):
        mock_hybrid = MagicMock()
        mock_hmm.return_value = mock_hybrid
        mock_hybrid.initialize = MagicMock()

        agent = MagicMock()

        async def _astream(input_data, stream_mode=None, **kwargs):
            # Store the input for assertions
            agent._astream_input = input_data
            from langchain_core.messages import AIMessageChunk
            yield AIMessageChunk(content="test response")

        agent.astream = _astream

        session = Session(
            session_id="test-1",
            working_dir="/tmp",
            agent=agent,
            memory=MagicMock(),
            db_repo=MagicMock(),
        )
        session.db_repo.add_message = AsyncMock()
        session.db_repo.update_status = AsyncMock()
        session.memory.recall = AsyncMock(return_value=[])
        session.memory.remember = AsyncMock()
        session.hybrid_memory.get_memory_context = MagicMock(return_value="## Test memory context")
        return session


@pytest.mark.asyncio
async def test_memory_context_in_system_prompt(mock_session):
    """Verify memory context is injected as a SystemMessage in the messages list."""
    from langchain_core.messages import SystemMessage

    await mock_session.send("Fix the auth bug")

    # Agent should have been called with {"messages": [...]}
    assert hasattr(mock_session.agent, '_astream_input'), "Agent astream was never called"
    state = mock_session.agent._astream_input
    assert "messages" in state, f"Expected 'messages' key in state, got: {list(state.keys())}"
    msgs = state["messages"]
    # Find a SystemMessage with memory context
    memory_msgs = [m for m in msgs if isinstance(m, SystemMessage) and "Test memory context" in m.content]
    assert len(memory_msgs) >= 1, (
        f"No SystemMessage with memory context found. Messages: {[type(m).__name__ for m in msgs]}"
    )


@pytest.mark.asyncio
async def test_no_memory_context_when_empty(mock_session):
    """When no memories are found, messages should only have base system prompt + user message."""
    from langchain_core.messages import HumanMessage, SystemMessage

    mock_session.hybrid_memory.get_memory_context = MagicMock(return_value="")
    await mock_session.send("Hello")

    # Should still work — agent gets called via astream
    assert hasattr(mock_session.agent, '_astream_input'), "Agent astream was never called"
    state = mock_session.agent._astream_input
    msgs = state["messages"]
    # Only base SystemMessage + HumanMessage (no memory SystemMessage)
    system_msgs = [m for m in msgs if isinstance(m, SystemMessage)]
    assert len(system_msgs) == 1, f"Expected 1 SystemMessage, got {len(system_msgs)}"
    assert isinstance(msgs[-1], HumanMessage)
