"""Tests for the Runtime kernel."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.runtime.context import RuntimeContext, current_context
from nexusagent.runtime.lifecycle import HealthStatus, LifecycleState
from nexusagent.runtime.runtime import Runtime


class TestRuntime:
    """Runtime initialization and shutdown."""

    def test_create(self):
        """Runtime can be created in CREATED state."""
        rt = Runtime(config={"test": True})
        assert rt.state == LifecycleState.CREATED
        assert rt.context is not None
        assert rt.context.config == {"test": True}

    def test_context_available_before_init(self):
        """RuntimeContext is available immediately after construction."""
        rt = Runtime(config={"early": True})
        assert rt.context.config["early"] is True

    @patch("nexusagent.infrastructure.db.get_db_manager")
    @patch("nexusagent.infrastructure.bus.get_bus")
    @patch("nexusagent.tools.register_all.register_all")
    async def test_initialize_transitions(
        self, mock_register, mock_get_bus, mock_get_db
    ):
        """initialize() transitions CREATED → INITIALIZING → RUNNING."""
        mock_db = MagicMock()
        mock_db.init_db = AsyncMock()
        mock_get_db.return_value = mock_db

        mock_bus = MagicMock()
        mock_bus.connect = AsyncMock()
        mock_get_bus.return_value = mock_bus

        rt = Runtime(config={"test": True})
        assert rt.state == LifecycleState.CREATED

        await rt.initialize()

        assert rt.state == LifecycleState.RUNNING
        assert rt._db_initialized is True
        assert rt._nats_connected is True
        assert rt.context.tool_initialized is True
        mock_db.init_db.assert_awaited_once()
        mock_bus.connect.assert_awaited_once()

    @patch("nexusagent.infrastructure.db.get_db_manager")
    @patch("nexusagent.infrastructure.bus.get_bus")
    @patch("nexusagent.tools.register_all.register_all")
    async def test_shutdown_transitions(
        self, mock_register, mock_get_bus, mock_get_db
    ):
        """shutdown() transitions from RUNNING → TERMINATED."""
        mock_db = MagicMock()
        mock_db.init_db = AsyncMock()
        mock_db.close = AsyncMock()
        mock_get_db.return_value = mock_db

        mock_bus = MagicMock()
        mock_bus.connect = AsyncMock()
        mock_bus.close = AsyncMock()
        mock_get_bus.return_value = mock_bus

        rt = Runtime(config={"test": True})
        await rt.initialize()
        assert rt.state == LifecycleState.RUNNING

        await rt.shutdown()
        assert rt.state == LifecycleState.TERMINATED

    @patch("nexusagent.infrastructure.db.get_db_manager")
    @patch("nexusagent.infrastructure.bus.get_bus")
    @patch("nexusagent.tools.register_all.register_all")
    async def test_context_available_during_runtime(
        self, mock_register, mock_get_bus, mock_get_db
    ):
        """RuntimeContext is accessible during runtime."""
        mock_db = MagicMock()
        mock_db.init_db = AsyncMock()
        mock_get_db.return_value = mock_db

        mock_bus = MagicMock()
        mock_bus.connect = AsyncMock()
        mock_get_bus.return_value = mock_bus

        rt = Runtime(config={"test": True})
        await rt.initialize()

        ctx = rt.context
        assert isinstance(ctx, RuntimeContext)
        assert ctx.tool_initialized is True

    @patch("nexusagent.infrastructure.db.get_db_manager")
    @patch("nexusagent.infrastructure.bus.get_bus")
    @patch("nexusagent.tools.register_all.register_all")
    async def test_health_during_runtime(
        self, mock_register, mock_get_bus, mock_get_db
    ):
        """health() returns healthy=True when runtime is RUNNING."""
        mock_db = MagicMock()
        mock_db.init_db = AsyncMock()
        mock_get_db.return_value = mock_db

        mock_bus = MagicMock()
        mock_bus.connect = AsyncMock()
        mock_get_bus.return_value = mock_bus

        rt = Runtime(config={"test": True})
        await rt.initialize()

        h = rt.health()
        assert isinstance(h, HealthStatus)
        assert h.healthy is True

    @patch("nexusagent.infrastructure.db.get_db_manager")
    @patch("nexusagent.infrastructure.bus.get_bus")
    @patch("nexusagent.tools.register_all.register_all")
    async def test_shutdown_error_isolation(
        self, mock_register, mock_get_bus, mock_get_db
    ):
        """Shutdown continues even if one step fails."""
        mock_db = MagicMock()
        mock_db.init_db = AsyncMock()
        mock_db.close = AsyncMock(side_effect=Exception("DB close failed"))
        mock_get_db.return_value = mock_db

        mock_bus = MagicMock()
        mock_bus.connect = AsyncMock()
        mock_bus.close = AsyncMock(side_effect=Exception("Bus close failed"))
        mock_get_bus.return_value = mock_bus

        rt = Runtime(config={"test": True})
        await rt.initialize()

        # Shutdown should not raise
        await rt.shutdown()
        assert rt.state == LifecycleState.TERMINATED

    @patch("nexusagent.infrastructure.db.get_db_manager")
    @patch("nexusagent.infrastructure.bus.get_bus")
    @patch("nexusagent.tools.register_all.register_all")
    async def test_current_context_var(
        self, mock_register, mock_get_bus, mock_get_db
    ):
        """current_context() returns Runtime's context after initialize."""
        mock_db = MagicMock()
        mock_db.init_db = AsyncMock()
        mock_get_db.return_value = mock_db

        mock_bus = MagicMock()
        mock_bus.connect = AsyncMock()
        mock_get_bus.return_value = mock_bus

        rt = Runtime(config={"test": True})
        assert current_context() is None

        await rt.initialize()
        ctx = current_context()
        assert ctx is not None
        assert ctx is rt.context

        await rt.shutdown()
        assert current_context() is None
