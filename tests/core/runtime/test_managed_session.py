"""Tests for ManagedSession and RuntimeSessionManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.runtime.context import RuntimeContext
from nexusagent.runtime.lifecycle import LifecycleState
from nexusagent.runtime.session import ManagedSession, RuntimeSessionManager


class TestManagedSession:
    """ManagedSession lifecycle and delegation."""

    @pytest.fixture
    def mock_session(self):
        s = MagicMock()
        s.session_id = "sess-test"
        s.status = "active"
        s.send = AsyncMock()
        s.close = AsyncMock()
        s.event_stream = MagicMock(return_value=AsyncMock())
        return s

    def test_create(self, mock_session):
        ms = ManagedSession(session=mock_session)
        assert ms.state == LifecycleState.CREATED
        assert ms.session_id == "sess-test"
        assert ms.session is mock_session

    async def test_initialize(self, mock_session):
        ms = ManagedSession(session=mock_session)
        await ms.initialize()
        assert ms.state == LifecycleState.RUNNING

    async def test_initialize_sets_policy_context(self, mock_session):
        ctx = RuntimeContext(config={"test": True})
        mock_session.policy = {"role": "admin"}
        ms = ManagedSession(session=mock_session, context=ctx)
        await ms.initialize()
        assert ctx.policy_context == {"role": "admin"}

    async def test_shutdown(self, mock_session):
        ms = ManagedSession(session=mock_session)
        await ms.initialize()
        await ms.shutdown()
        assert ms.state == LifecycleState.TERMINATED
        mock_session.close.assert_awaited_once()

    async def test_shutdown_clears_policy_context(self, mock_session):
        ctx = RuntimeContext(config={"test": True})
        mock_session.policy = {"role": "admin"}
        ms = ManagedSession(session=mock_session, context=ctx)
        await ms.initialize()
        assert ctx.policy_context == {"role": "admin"}

        await ms.shutdown()
        assert ctx.policy_context is None

    async def test_send_delegates(self, mock_session):
        ms = ManagedSession(session=mock_session)
        await ms.initialize()
        await ms.send("hello")
        mock_session.send.assert_awaited_once_with("hello", images=None)

    async def test_send_sets_current_session_id(self, mock_session):
        ctx = RuntimeContext(config={"test": True})
        ms = ManagedSession(session=mock_session, context=ctx)
        await ms.initialize()
        await ms.send("hello")
        assert ctx.current_session_id == "sess-test"

    async def test_close_delegates(self, mock_session):
        ms = ManagedSession(session=mock_session)
        await ms.initialize()
        await ms.close()
        mock_session.close.assert_awaited_once()

    def test_health(self, mock_session):
        ms = ManagedSession(session=mock_session)
        h = ms.health()
        assert h.healthy is False  # CREATED, not RUNNING

    async def test_health_running(self, mock_session):
        ms = ManagedSession(session=mock_session)
        await ms.initialize()
        h = ms.health()
        assert h.healthy is True


class TestRuntimeSessionManager:
    """RuntimeSessionManager lifecycle and session management."""

    @pytest.fixture
    def mock_context(self):
        return RuntimeContext(config={"test": True})

    @pytest.fixture
    def mock_session_manager(self):
        """Mock SessionManager's get_or_create."""
        sm = MagicMock()
        sm.get_or_create = AsyncMock()
        return sm

    async def test_initialize(self, mock_context):
        rsm = RuntimeSessionManager(context=mock_context)
        assert rsm.state == LifecycleState.CREATED
        await rsm.initialize()
        assert rsm.state == LifecycleState.RUNNING

    async def test_shutdown(self, mock_context):
        rsm = RuntimeSessionManager(context=mock_context)
        await rsm.initialize()
        await rsm.shutdown()
        assert rsm.state == LifecycleState.TERMINATED

    async def test_active_count(self, mock_context):
        rsm = RuntimeSessionManager(context=mock_context)
        assert rsm.active_count == 0
