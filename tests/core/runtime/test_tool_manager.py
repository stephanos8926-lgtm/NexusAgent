"""Tests for the ToolManager."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nexusagent.runtime.context import RuntimeContext
from nexusagent.runtime.lifecycle import LifecycleState
from nexusagent.runtime.tools import ToolManager


class TestToolManager:
    """ToolManager lifecycle and registration."""

    def test_create(self):
        """ToolManager starts in CREATED state."""
        tm = ToolManager()
        assert tm.state == LifecycleState.CREATED
        assert tm.is_registered() is False

    def test_create_with_context(self):
        """ToolManager can be created with a RuntimeContext."""
        ctx = RuntimeContext(config={"test": True})
        tm = ToolManager(context=ctx)
        assert tm._context is ctx

    @patch("nexusagent.tools.register_all.register_all")
    async def test_initialize(self, mock_register):
        """ToolManager.initialize() registers tools and transitions to RUNNING."""
        tm = ToolManager()
        await tm.initialize()
        assert tm.state == LifecycleState.RUNNING
        assert tm.is_registered() is True
        mock_register.assert_called_once()

    @patch("nexusagent.tools.register_all.register_all")
    async def test_initialize_sets_context(self, mock_register):
        """When RuntimeContext is active, tool_initialized is set."""
        ctx = RuntimeContext(config={"test": True})
        tm = ToolManager(context=ctx)
        await tm.initialize()
        assert ctx.tool_initialized is True

    @patch("nexusagent.tools.register_all.register_all")
    async def test_ensure_registered_idempotent(self, mock_register):
        """Calling ensure_registered multiple times only registers once."""
        tm = ToolManager()
        await tm.initialize()
        # Second call should be no-op
        tm.ensure_registered()
        mock_register.assert_called_once()

    @patch("nexusagent.tools.register_all.register_all")
    async def test_shutdown(self, mock_register):
        """ToolManager.shutdown() transitions to TERMINATED."""
        tm = ToolManager()
        await tm.initialize()
        assert tm.state == LifecycleState.RUNNING

        await tm.shutdown()
        assert tm.state == LifecycleState.TERMINATED
        assert tm.is_registered() is True  # registration survives shutdown

    @patch("nexusagent.tools.register_all.register_all")
    async def test_health(self, mock_register):
        """health() returns correct state."""
        tm = ToolManager()
        # Before init — CREATED
        h = tm.health()
        assert h.healthy is False  # not RUNNING yet

        await tm.initialize()
        h = tm.health()
        assert h.healthy is True
        assert h.details["initialized"] is True
