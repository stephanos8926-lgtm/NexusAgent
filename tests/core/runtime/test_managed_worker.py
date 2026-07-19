"""Tests for ManagedWorker and RuntimeWorkerManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.runtime.context import RuntimeContext
from nexusagent.runtime.lifecycle import LifecycleState
from nexusagent.runtime.worker import ManagedWorker, RuntimeWorkerManager, WorkerMetadata


class TestManagedWorker:
    """ManagedWorker lifecycle and delegation."""

    @pytest.fixture
    def mock_handle(self):
        h = MagicMock()
        h.worker_id = "wkr-test"
        h.status.name = "PENDING"
        h.is_done = MagicMock(return_value=False)
        h.cancel = MagicMock()
        h.wait = AsyncMock(return_value={"result": "ok"})
        h.result = None
        h.error = None
        return h

    def test_create(self, mock_handle):
        mw = ManagedWorker(handle=mock_handle)
        assert mw.worker_id == "wkr-test"
        assert mw.handle is mock_handle

    async def test_initialize(self, mock_handle):
        mw = ManagedWorker(handle=mock_handle)
        await mw.initialize()
        assert mw.state is not None

    async def test_shutdown_cancels_handle(self, mock_handle):
        mw = ManagedWorker(handle=mock_handle)
        await mw.shutdown()
        mock_handle.cancel.assert_called_once()
        assert mw.state == LifecycleState.TERMINATED

    async def test_wait_delegates(self, mock_handle):
        mw = ManagedWorker(handle=mock_handle)
        result = await mw.wait()
        assert result == {"result": "ok"}
        mock_handle.wait.assert_awaited_once()

    async def test_cancel(self, mock_handle):
        mw = ManagedWorker(handle=mock_handle)
        mw.cancel()
        mock_handle.cancel.assert_called_once()
        assert mw.state == LifecycleState.TERMINATED

    def test_is_done_delegates(self, mock_handle):
        mw = ManagedWorker(handle=mock_handle)
        assert mw.is_done() is False
        mock_handle.is_done.assert_called_once()

    def test_health(self, mock_handle):
        mw = ManagedWorker(handle=mock_handle)
        h = mw.health()
        assert isinstance(h.healthy, bool)


class TestRuntimeWorkerManager:
    """RuntimeWorkerManager lifecycle."""

    @pytest.fixture
    def mock_context(self):
        return RuntimeContext(config={"test": True})

    async def test_initialize(self, mock_context):
        rwm = RuntimeWorkerManager(context=mock_context)
        assert rwm.state == LifecycleState.CREATED
        await rwm.initialize()
        assert rwm.state == LifecycleState.RUNNING
        assert mock_context.worker_manager is rwm

    async def test_shutdown(self, mock_context):
        rwm = RuntimeWorkerManager(context=mock_context)
        await rwm.initialize()
        await rwm.shutdown()
        assert rwm.state == LifecycleState.TERMINATED

    async def test_active_count(self, mock_context):
        rwm = RuntimeWorkerManager(context=mock_context)
        assert rwm.active_count == 0

    async def test_spawn_before_init_raises(self, mock_context):
        rwm = RuntimeWorkerManager(context=mock_context)
        with pytest.raises(RuntimeError, match="not initialized"):
            await rwm.spawn(None)
