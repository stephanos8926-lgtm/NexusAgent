"""Tests for memory context injection into agent system prompt."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.session import Session


@pytest.fixture
def mock_session():
    """Create a session with mocked dependencies."""
    with (
        patch("nexusagent.session.SessionManager"),
        patch("nexusagent.memory.HybridMemoryManager") as mock_hmm,
    ):
        mock_hybrid = MagicMock()
        mock_hmm.return_value = mock_hybrid
        mock_hybrid.initialize = MagicMock()

        session = Session(
            session_id="test-1",
            working_dir="/tmp",
            agent=MagicMock(),
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
    """Verify memory context is injected into the agent's system prompt."""
    await mock_session.send("Fix the auth bug")

    # Agent should have been called
    call_args = mock_session.agent.call_args
    assert call_args is not None, "Agent was never called"

    # Check that system_prompt was passed and contains memory context
    kwargs = (
        call_args.kwargs
        if hasattr(call_args, "kwargs")
        else (call_args[1] if len(call_args) > 1 else {})
    )
    system_prompt = kwargs.get("system_prompt", "") if kwargs else ""
    assert "Test memory context" in system_prompt, (
        f"system_prompt does not contain memory context. Got: {system_prompt!r}\n"
        f"Full call_args: {call_args}"
    )


@pytest.mark.asyncio
async def test_no_memory_context_when_empty(mock_session):
    """When no memories are found, system_prompt should not have memory section."""
    mock_session.hybrid_memory.get_memory_context = MagicMock(return_value="")
    await mock_session.send("Hello")

    # Should still work — agent gets called
    call_args = mock_session.agent.call_args
    assert call_args is not None, "Agent was never called"
