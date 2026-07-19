"""Integration tests: Runtime + existing NexusAgent system integration.

Validates that the Runtime kernel integrates correctly with:
  - SessionManager → RuntimeSessionManager
  - WorkerPool → RuntimeWorkerManager
  - ToolRegistry → ToolManager
  - Full lifecycle: init → spawn → create session → shutdown
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.runtime import (
    ManagedSession,
    ManagedWorker,
    RuntimeSessionManager,
    RuntimeWorkerManager,
    ToolManager,
)
from nexusagent.runtime.context import RuntimeContext
from nexusagent.runtime.lifecycle import HealthStatus, LifecycleState
from nexusagent.runtime.runtime import Runtime


# =============================================================================
# Runtime + existing SessionManager integration
# =============================================================================


class TestRuntimeSessionManagerIntegration:
    """RuntimeSessionManager wraps the existing SessionManager with lifecycle."""

    def test_create_with_context(self):
        """RuntimeSessionManager can be created with a RuntimeContext."""
        ctx = RuntimeContext(config={})
        mgr = RuntimeSessionManager(context=ctx)
        assert mgr.state == LifecycleState.CREATED
        assert mgr._context is ctx
        assert mgr.active_count == 0

    def test_create_without_context(self):
        """RuntimeSessionManager works without a RuntimeContext (graceful fallback)."""
        mgr = RuntimeSessionManager()
        assert mgr.state == LifecycleState.CREATED
        assert mgr._context is None

    @patch("nexusagent.core.session.manager.get_session_manager")
    async def test_initialize_wraps_session_manager(self, mock_get_sm):
        """initialize() gets the real SessionManager singleton and transitions to RUNNING."""
        mock_sm = MagicMock()
        mock_get_sm.return_value = mock_sm

        mgr = RuntimeSessionManager()
        await mgr.initialize()

        assert mgr.state == LifecycleState.RUNNING
        mock_get_sm.assert_called_once()
        assert mgr._inner is mock_sm

    @patch("nexusagent.core.session.manager.get_session_manager")
    async def test_get_or_create_wraps_session(self, mock_get_sm):
        """get_or_create() delegates to SessionManager and wraps result in ManagedSession."""
        # Mock the underlying SessionManager
        mock_session = MagicMock()
        mock_session.session_id = "sess-integ-001"
        mock_session.status = "active"
        mock_session.close = AsyncMock()

        mock_sm = MagicMock()
        mock_sm.get_or_create = AsyncMock(return_value=mock_session)
        mock_get_sm.return_value = mock_sm

        ctx = RuntimeContext(config={})
        mgr = RuntimeSessionManager(context=ctx)
        await mgr.initialize()

        # Act
        managed = await mgr.get_or_create(
            session_id="sess-integ-001",
            working_dir="/tmp/integ-test",
            agent=MagicMock(),
            db_repo=MagicMock(),
        )

        # Assert
        assert isinstance(managed, ManagedSession)
        assert managed.session_id == "sess-integ-001"
        assert managed.state == LifecycleState.RUNNING
        assert managed._context is ctx
        mock_sm.get_or_create.assert_awaited_once_with(
            session_id="sess-integ-001",
            working_dir="/tmp/integ-test",
            agent=mock_sm.get_or_create.call_args[1]["agent"],
            db_repo=mock_sm.get_or_create.call_args[1]["db_repo"],
            memory_dir=None,
        )
        assert mgr.active_count == 1

    @patch("nexusagent.core.session.manager.get_session_manager")
    async def test_get_or_create_returns_cached(self, mock_get_sm):
        """get_or_create() returns the same ManagedSession for the same ID."""
        mock_session = MagicMock()
        mock_session.session_id = "sess-cached"
        mock_session.status = "active"
        mock_session.close = AsyncMock()

        mock_sm = MagicMock()
        mock_sm.get_or_create = AsyncMock(return_value=mock_session)
        mock_get_sm.return_value = mock_sm

        mgr = RuntimeSessionManager()
        await mgr.initialize()

        s1 = await mgr.get_or_create(
            session_id="sess-cached",
            working_dir=".",
            agent=MagicMock(),
            db_repo=MagicMock(),
        )
        s2 = await mgr.get_or_create(
            session_id="sess-cached",
            working_dir=".",
            agent=MagicMock(),
            db_repo=MagicMock(),
        )

        assert s1 is s2
        # get_or_create on the mock should only have been called once
        mock_sm.get_or_create.assert_awaited_once()

    @patch("nexusagent.core.session.manager.get_session_manager")
    async def test_get_retrieves_managed_session(self, mock_get_sm):
        """get() returns a previously created ManagedSession."""
        mock_session = MagicMock()
        mock_session.session_id = "sess-get-test"
        mock_session.status = "active"
        mock_session.close = AsyncMock()

        mock_sm = MagicMock()
        mock_sm.get_or_create = AsyncMock(return_value=mock_session)
        mock_get_sm.return_value = mock_sm

        mgr = RuntimeSessionManager()
        await mgr.initialize()

        created = await mgr.get_or_create(
            session_id="sess-get-test",
            working_dir=".",
            agent=MagicMock(),
            db_repo=MagicMock(),
        )
        retrieved = mgr.get("sess-get-test")

        assert retrieved is created
        assert retrieved.session_id == "sess-get-test"

    @patch("nexusagent.core.session.manager.get_session_manager")
    async def test_get_returns_none_for_missing(self, mock_get_sm):
        """get() returns None for an unknown session ID."""
        mgr = RuntimeSessionManager()
        await mgr.initialize()
        assert mgr.get("nonexistent") is None

    @patch("nexusagent.core.session.manager.get_session_manager")
    async def test_shutdown_clears_all_sessions(self, mock_get_sm):
        """shutdown() cancels all managed sessions and clears the session cache."""
        mock_session = MagicMock()
        mock_session.session_id = "sess-shutdown"
        mock_session.status = "active"
        mock_session.close = AsyncMock()

        mock_sm = MagicMock()
        mock_sm.get_or_create = AsyncMock(return_value=mock_session)
        mock_get_sm.return_value = mock_sm

        mgr = RuntimeSessionManager()
        await mgr.initialize()
        await mgr.get_or_create(
            session_id="sess-shutdown",
            working_dir=".",
            agent=MagicMock(),
            db_repo=MagicMock(),
        )

        await mgr.shutdown()

        assert mgr.state == LifecycleState.TERMINATED
        assert mgr.active_count == 0
        mock_session.close.assert_awaited_once()

    @patch("nexusagent.core.session.manager.get_session_manager")
    async def test_health_status(self, mock_get_sm):
        """health() reflects running state and active session count."""
        mock_session = MagicMock()
        mock_session.session_id = "sess-health"
        mock_session.status = "active"
        mock_session.close = AsyncMock()

        mock_sm = MagicMock()
        mock_sm.get_or_create = AsyncMock(return_value=mock_session)
        mock_get_sm.return_value = mock_sm

        mgr = RuntimeSessionManager()
        await mgr.initialize()
        await mgr.get_or_create(
            session_id="sess-health",
            working_dir=".",
            agent=MagicMock(),
            db_repo=MagicMock(),
        )

        h = mgr.health()
        assert isinstance(h, HealthStatus)
        assert h.healthy is True
        assert h.details["active_sessions"] == 1


# =============================================================================
# Runtime + existing WorkerPool integration
# =============================================================================


class TestRuntimeWorkerManagerIntegration:
    """RuntimeWorkerManager wraps the existing WorkerPool with lifecycle."""

    def test_create_with_context(self):
        """RuntimeWorkerManager can be created with a RuntimeContext."""
        ctx = RuntimeContext(config={})
        mgr = RuntimeWorkerManager(context=ctx, max_workers=8)
        assert mgr.state == LifecycleState.CREATED
        assert mgr._context is ctx
        assert mgr._max_workers == 8

    def test_create_default_max_workers(self):
        """RuntimeWorkerManager defaults to 4 max workers."""
        mgr = RuntimeWorkerManager()
        assert mgr._max_workers == 4

    @patch("nexusagent.core.worker.pool.WorkerPool")
    async def test_initialize_creates_pool(self, MockPool):
        """initialize() creates a WorkerPool and sets it on context."""
        mock_pool_instance = MagicMock()
        MockPool.return_value = mock_pool_instance

        ctx = RuntimeContext(config={})
        mgr = RuntimeWorkerManager(context=ctx, max_workers=4)
        await mgr.initialize()

        assert mgr.state == LifecycleState.RUNNING
        assert mgr._pool is mock_pool_instance
        MockPool.assert_called_once_with(max_workers=4)
        assert ctx.worker_manager is mgr

    @patch("nexusagent.core.worker.pool.WorkerPool")
    async def test_spawn_returns_managed_worker(self, MockPool):
        """spawn() delegates to WorkerPool and wraps handle in ManagedWorker."""
        # Create a realistic mock SubAgentHandle
        mock_handle = MagicMock()
        mock_handle.worker_id = "worker-integ-001"
        mock_handle.status.name = "PENDING"
        mock_handle.status = MagicMock()
        mock_handle.status.value = "pending"
        mock_handle.created_at = MagicMock()
        mock_handle.created_at.timestamp.return_value = 1234567890.0
        mock_handle.is_done.return_value = False

        mock_pool = MagicMock()
        mock_pool.spawn = AsyncMock(return_value=mock_handle)
        MockPool.return_value = mock_pool

        ctx = RuntimeContext(config={})
        mgr = RuntimeWorkerManager(context=ctx)
        await mgr.initialize()

        contract = MagicMock()
        managed = await mgr.spawn(contract=contract, depth=0)

        assert isinstance(managed, ManagedWorker)
        assert managed.worker_id == "worker-integ-001"
        assert managed.handle is mock_handle
        mock_pool.spawn.assert_awaited_once_with(contract, depth=0)
        assert mgr.active_count == 1

    @patch("nexusagent.core.worker.pool.WorkerPool")
    async def test_spawn_raises_if_not_initialized(self, MockPool):
        """spawn() raises RuntimeError if initialize() was not called."""
        mgr = RuntimeWorkerManager()
        with pytest.raises(RuntimeError, match="Worker manager not initialized"):
            await mgr.spawn(contract=MagicMock())

    @patch("nexusagent.core.worker.pool.WorkerPool")
    async def test_get_retrieves_managed_worker(self, MockPool):
        """get() returns a previously spawned ManagedWorker by ID."""
        mock_handle = MagicMock()
        mock_handle.worker_id = "worker-get-test"
        mock_handle.status = MagicMock()
        mock_handle.status.value = "pending"
        mock_handle.created_at = MagicMock()
        mock_handle.created_at.timestamp.return_value = 0.0
        mock_handle.is_done.return_value = False

        mock_pool = MagicMock()
        mock_pool.spawn = AsyncMock(return_value=mock_handle)
        MockPool.return_value = mock_pool

        mgr = RuntimeWorkerManager()
        await mgr.initialize()

        created = await mgr.spawn(contract=MagicMock())
        retrieved = mgr.get("worker-get-test")

        assert retrieved is created
        assert retrieved.worker_id == "worker-get-test"

    @patch("nexusagent.core.worker.pool.WorkerPool")
    async def test_get_returns_none_for_missing(self, MockPool):
        """get() returns None for an unknown worker ID."""
        mgr = RuntimeWorkerManager()
        await mgr.initialize()
        assert mgr.get("nonexistent") is None

    @patch("nexusagent.core.worker.pool.WorkerPool")
    async def test_shutdown_cancels_all_workers(self, MockPool):
        """shutdown() cancels all managed workers and clears the cache."""
        mock_handle = MagicMock()
        mock_handle.worker_id = "worker-shutdown"
        mock_handle.status = MagicMock()
        mock_handle.status.value = "running"
        mock_handle.created_at = MagicMock()
        mock_handle.created_at.timestamp.return_value = 0.0
        mock_handle.is_done.return_value = False

        mock_pool = MagicMock()
        mock_pool.spawn = AsyncMock(return_value=mock_handle)
        MockPool.return_value = mock_pool

        mgr = RuntimeWorkerManager()
        await mgr.initialize()
        await mgr.spawn(contract=MagicMock())

        await mgr.shutdown()

        assert mgr.state == LifecycleState.TERMINATED
        assert mgr.active_count == 0
        mock_handle.cancel.assert_called_once()

    @patch("nexusagent.core.worker.pool.WorkerPool")
    async def test_health_status(self, MockPool):
        """health() reflects running state and active worker count."""
        mock_handle = MagicMock()
        mock_handle.worker_id = "worker-health"
        mock_handle.status = MagicMock()
        mock_handle.status.value = "running"
        mock_handle.created_at = MagicMock()
        mock_handle.created_at.timestamp.return_value = 0.0
        mock_handle.is_done.return_value = False

        mock_pool = MagicMock()
        mock_pool.spawn = AsyncMock(return_value=mock_handle)
        MockPool.return_value = mock_pool

        mgr = RuntimeWorkerManager()
        await mgr.initialize()
        await mgr.spawn(contract=MagicMock())

        h = mgr.health()
        assert isinstance(h, HealthStatus)
        assert h.healthy is True
        assert h.details["active_workers"] == 1


# =============================================================================
# Runtime + ToolRegistry integration
# =============================================================================


class TestToolManagerIntegration:
    """ToolManager wraps tool registration with RuntimeContext awareness."""

    def test_create_with_context(self):
        """ToolManager can be created with a RuntimeContext."""
        ctx = RuntimeContext(config={})
        tm = ToolManager(context=ctx)
        assert tm.state == LifecycleState.CREATED
        assert tm._context is ctx
        assert tm.is_registered() is False

    def test_create_without_context(self):
        """ToolManager works without a RuntimeContext (graceful fallback)."""
        tm = ToolManager()
        assert tm._context is None

    @patch("nexusagent.tools.register_all.register_all")
    async def test_initialize_registers_tools(self, mock_register):
        """initialize() calls register_all and transitions to RUNNING."""
        tm = ToolManager()
        await tm.initialize()

        assert tm.state == LifecycleState.RUNNING
        assert tm.is_registered() is True
        mock_register.assert_called_once()

    @patch("nexusagent.tools.register_all.register_all")
    async def test_initialize_with_context_sets_tool_initialized(self, mock_register):
        """initialize() with context sets context.tool_initialized and tool_registry."""
        ctx = RuntimeContext(config={})
        tm = ToolManager(context=ctx)
        await tm.initialize()

        assert tm.state == LifecycleState.RUNNING
        assert ctx.tool_initialized is True
        assert ctx.tool_registry is not None

    @patch("nexusagent.tools.register_all.register_all")
    async def test_ensure_registered_idempotent(self, mock_register):
        """ensure_registered() is idempotent — second call is a no-op."""
        tm = ToolManager()
        await tm.initialize()

        # Call ensure_registered again (bypass initialize by calling directly)
        tm.ensure_registered()

        mock_register.assert_called_once()

    @patch("nexusagent.tools.register_all.register_all")
    async def test_shutdown_is_noop(self, mock_register):
        """shutdown() transitions to TERMINATED without errors."""
        tm = ToolManager()
        await tm.initialize()
        await tm.shutdown()

        assert tm.state == LifecycleState.TERMINATED

    @patch("nexusagent.tools.register_all.register_all")
    async def test_health_after_initialize(self, mock_register):
        """health() reports healthy after initialization."""
        tm = ToolManager()
        await tm.initialize()

        h = tm.health()
        assert isinstance(h, HealthStatus)
        assert h.healthy is True
        assert h.details["initialized"] is True


# =============================================================================
# Full lifecycle — Runtime initialize → spawn → create session → shutdown
# =============================================================================


class TestRuntimeFullLifecycleIntegration:
    """Complete lifecycle: Runtime init → session creation → worker spawn → shutdown.

    Validates every state transition across the entire system.
    """

    @patch("nexusagent.infrastructure.db.get_db_manager")
    @patch("nexusagent.infrastructure.bus.get_bus")
    @patch("nexusagent.tools.register_all.register_all")
    @patch("nexusagent.core.session.manager.get_session_manager")
    @patch("nexusagent.core.worker.pool.WorkerPool")
    async def test_full_lifecycle_state_transitions(
        self,
        MockPool,
        mock_get_sm,
        mock_register,
        mock_get_bus,
        mock_get_db,
    ):
        """Full lifecycle: CREATED → INITIALIZING → RUNNING → TERMINATED."""
        # ── Mock DB ──
        mock_db = MagicMock()
        mock_db.init_db = AsyncMock()
        mock_db.close = AsyncMock()
        mock_get_db.return_value = mock_db

        # ── Mock NATS ──
        mock_bus = MagicMock()
        mock_bus.connect = AsyncMock()
        mock_bus.close = AsyncMock()
        mock_get_bus.return_value = mock_bus

        # ── Mock SessionManager ──
        mock_session = MagicMock()
        mock_session.session_id = "sess-lifecycle"
        mock_session.status = "active"
        mock_session.close = AsyncMock()

        mock_sm = MagicMock()
        mock_sm.get_or_create = AsyncMock(return_value=mock_session)
        mock_get_sm.return_value = mock_sm

        # ── Mock WorkerPool ──
        mock_handle = MagicMock()
        mock_handle.worker_id = "worker-lifecycle"
        mock_handle.status = MagicMock()
        mock_handle.status.value = "running"
        mock_handle.created_at = MagicMock()
        mock_handle.created_at.timestamp.return_value = 0.0
        mock_handle.is_done.return_value = False

        mock_pool = MagicMock()
        mock_pool.spawn = AsyncMock(return_value=mock_handle)
        MockPool.return_value = mock_pool

        # ═══════ Phase 1: CREATED ═══════
        rt = Runtime(config={"lifecycle": True})
        assert rt.state == LifecycleState.CREATED
        assert rt.context is not None
        assert rt._db_initialized is False
        assert rt._nats_connected is False
        assert rt._worker_started is False

        # ═══════ Phase 2: INITIALIZE → RUNNING ═══════
        await rt.initialize()
        assert rt.state == LifecycleState.RUNNING
        assert rt._db_initialized is True
        assert rt._nats_connected is True
        assert rt.context.tool_initialized is True

        # ═══════ Phase 3: Wire up session & worker managers ═══════
        # Simulate what the CLI/server does: set managers on context
        session_mgr = RuntimeSessionManager(context=rt.context)
        await session_mgr.initialize()
        rt.context.session_manager = session_mgr

        worker_mgr = RuntimeWorkerManager(context=rt.context)
        await worker_mgr.initialize()
        rt.context.worker_manager = worker_mgr

        # ═══════ Phase 4: Create session ═══════
        managed_session = await session_mgr.get_or_create(
            session_id="sess-lifecycle",
            working_dir="/tmp/lifecycle",
            agent=MagicMock(),
            db_repo=MagicMock(),
        )

        assert isinstance(managed_session, ManagedSession)
        assert managed_session.session_id == "sess-lifecycle"
        assert managed_session.state == LifecycleState.RUNNING
        assert session_mgr.active_count == 1

        # ═══════ Phase 5: Spawn worker ═══════
        contract = MagicMock()
        contract.max_depth = 3
        managed_worker = await worker_mgr.spawn(contract=contract, depth=0)

        assert isinstance(managed_worker, ManagedWorker)
        assert managed_worker.worker_id == "worker-lifecycle"
        assert worker_mgr.active_count == 1

        # ═══════ Phase 6: Verify Runtime health ═══════
        h = rt.health()
        assert isinstance(h, HealthStatus)
        assert h.healthy is True
        assert h.details["state"] == "running"
        assert h.details["nats_connected"] is True
        assert h.details["db_initialized"] is True

        # ═══════ Phase 7: SHUTDOWN ═══════
        await rt.shutdown()
        assert rt.state == LifecycleState.TERMINATED
        assert rt.context.tool_initialized is True  # survives shutdown
        assert rt._db_initialized is True
        assert rt._nats_connected is True

    @patch("nexusagent.infrastructure.db.get_db_manager")
    @patch("nexusagent.infrastructure.bus.get_bus")
    @patch("nexusagent.tools.register_all.register_all")
    @patch("nexusagent.core.session.manager.get_session_manager")
    @patch("nexusagent.core.worker.pool.WorkerPool")
    async def test_shutdown_with_active_session_and_worker(
        self,
        MockPool,
        mock_get_sm,
        mock_register,
        mock_get_bus,
        mock_get_db,
    ):
        """Shutdown gracefully handles active sessions and workers."""
        # ── All mocks ──
        mock_db = MagicMock()
        mock_db.init_db = AsyncMock()
        mock_db.close = AsyncMock()
        mock_get_db.return_value = mock_db

        mock_bus = MagicMock()
        mock_bus.connect = AsyncMock()
        mock_bus.close = AsyncMock()
        mock_get_bus.return_value = mock_bus

        mock_session = MagicMock()
        mock_session.session_id = "sess-active"
        mock_session.status = "active"
        mock_session.close = AsyncMock()

        mock_sm = MagicMock()
        mock_sm.get_or_create = AsyncMock(return_value=mock_session)
        mock_get_sm.return_value = mock_sm

        mock_handle = MagicMock()
        mock_handle.worker_id = "worker-active"
        mock_handle.status = MagicMock()
        mock_handle.status.value = "running"
        mock_handle.created_at = MagicMock()
        mock_handle.created_at.timestamp.return_value = 0.0
        mock_handle.is_done.return_value = False

        mock_pool = MagicMock()
        mock_pool.spawn = AsyncMock(return_value=mock_handle)
        MockPool.return_value = mock_pool

        # ── Setup Runtime ──
        rt = Runtime(config={})
        await rt.initialize()

        # Wire managers
        session_mgr = RuntimeSessionManager(context=rt.context)
        await session_mgr.initialize()
        rt.context.session_manager = session_mgr

        worker_mgr = RuntimeWorkerManager(context=rt.context)
        await worker_mgr.initialize()
        rt.context.worker_manager = worker_mgr

        # Create session + spawn worker
        await session_mgr.get_or_create(
            session_id="sess-active",
            working_dir=".",
            agent=MagicMock(),
            db_repo=MagicMock(),
        )
        await worker_mgr.spawn(contract=MagicMock())

        assert session_mgr.active_count == 1
        assert worker_mgr.active_count == 1

        # ── Shutdown Runtime — should cascade to managers ──
        await rt.shutdown()

        assert rt.state == LifecycleState.TERMINATED
        mock_db.close.assert_awaited_once()
        mock_bus.close.assert_awaited_once()

    @patch("nexusagent.infrastructure.db.get_db_manager")
    @patch("nexusagent.infrastructure.bus.get_bus")
    @patch("nexusagent.tools.register_all.register_all")
    async def test_runtime_context_session_id_propagation(
        self,
        mock_register,
        mock_get_bus,
        mock_get_db,
    ):
        """RuntimeContext.current_session_id is set during session operations."""
        mock_db = MagicMock()
        mock_db.init_db = AsyncMock()
        mock_db.close = AsyncMock()
        mock_get_db.return_value = mock_db

        mock_bus = MagicMock()
        mock_bus.connect = AsyncMock()
        mock_bus.close = AsyncMock()
        mock_get_bus.return_value = mock_bus

        # Mock session with send support
        mock_session = MagicMock()
        mock_session.session_id = "sess-propagation"
        mock_session.status = "active"
        mock_session.close = AsyncMock()
        mock_session.send = AsyncMock()

        # Wire up session manager
        with patch(
            "nexusagent.core.session.manager.get_session_manager"
        ) as mock_get_sm:
            mock_sm = MagicMock()
            mock_sm.get_or_create = AsyncMock(return_value=mock_session)
            mock_get_sm.return_value = mock_sm

            rt = Runtime(config={})
            await rt.initialize()

            sm = RuntimeSessionManager(context=rt.context)
            await sm.initialize()
            rt.context.session_manager = sm

            managed = await sm.get_or_create(
                session_id="sess-propagation",
                working_dir=".",
                agent=MagicMock(),
                db_repo=MagicMock(),
            )

            # Send a message — should set current_session_id
            assert rt.context.current_session_id is None
            await managed.send("Hello")
            assert rt.context.current_session_id == "sess-propagation"
            mock_session.send.assert_awaited_once_with("Hello", images=None)

            # Verify it's set via managed.send, then cleared on next session
            await rt.shutdown()