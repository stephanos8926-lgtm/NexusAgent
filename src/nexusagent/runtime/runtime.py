"""Runtime kernel — lifecycle, coordination, and DI container ownership.

The Runtime is the root of the component hierarchy. It owns initialization
and shutdown sequences, creates the RuntimeContext, and manages subsystem
lifecycles.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from nexusagent.runtime.context import RuntimeContext, set_current_context
from nexusagent.runtime.lifecycle import (
    HealthStatus,
    LifecycleMixin,
    LifecycleState,
)

if TYPE_CHECKING:
    from nexusagent.tools.registry.core import ToolRegistry

logger = logging.getLogger("nexusagent.runtime")


class Runtime(LifecycleMixin):
    """Central execution kernel.

    The Runtime is created at application startup and destroyed at shutdown.
    It owns the RuntimeContext and manages subsystem lifecycle.

    Create with:
        runtime = Runtime(config=settings)
        await runtime.initialize()
        # ... use runtime ...
        await runtime.shutdown()
    """

    def __init__(self, config: Any) -> None:
        self._state = LifecycleState.CREATED
        self._context: RuntimeContext | None = None

        # Internal tracking for shutdown isolation
        self._nats_connected = False
        self._db_initialized = False
        self._worker_started = False

        # Seed context with config immediately (before initialize)
        self._context = RuntimeContext(config=config)

    # --- LifecycleMixin ---

    @property
    def state(self) -> LifecycleState:
        return self._state

    @property
    def context(self) -> RuntimeContext:
        """Return the RuntimeContext. Raises RuntimeError if not initialized."""
        if self._context is None:
            raise RuntimeError("Runtime not initialized — no context available")
        return self._context

    async def initialize(self) -> None:
        """Startup sequence: DB → NATS → ToolManager → ready.

        Each step is individually try/caught for graceful degradation.
        """
        self._state = LifecycleState.INITIALIZING
        set_current_context(self._context)
        logger.info("Runtime initializing...")

        try:
            await self._init_database()
        except Exception as e:
            logger.warning("Database init failed (continuing): %s", e)

        try:
            await self._init_nats()
        except Exception as e:
            logger.warning("NATS connect failed (continuing): %s", e)

        try:
            await self._init_tool_manager()
        except Exception as e:
            logger.warning("Tool manager init failed (continuing): %s", e)

        self._state = LifecycleState.RUNNING
        logger.info("Runtime initialized and running.")

    async def shutdown(self) -> None:
        """Graceful shutdown with per-step error isolation.

        Each step is individually try/caught so a failure in one step
        does not prevent subsequent cleanup.
        """
        previous_state = self._state
        self._state = LifecycleState.TERMINATED

        # Step 1: Stop workers
        if self._context and self._context.worker_manager:
            try:
                wm = self._context.worker_manager
                if hasattr(wm, "shutdown"):
                    await wm.shutdown()
            except Exception as e:
                logger.warning("Worker manager shutdown failed (continuing): %s", e)

        # Step 2: Close sessions
        if self._context and self._context.session_manager:
            try:
                sm = self._context.session_manager
                if hasattr(sm, "shutdown"):
                    await sm.shutdown()
            except Exception as e:
                logger.warning("Session manager shutdown failed (continuing): %s", e)

        # Step 3: Close NATS
        if self._context and self._context.bus:
            try:
                await self._context.bus.close()
            except Exception as e:
                logger.warning("NATS bus close failed (continuing): %s", e)

        # Step 4: Close DB
        if self._context and self._context.db_manager:
            try:
                await self._context.db_manager.close()
            except Exception as e:
                logger.warning("DB close failed (continuing): %s", e)

        # Step 5: Clear context
        set_current_context(None)
        self._state = LifecycleState.TERMINATED
        logger.info(
            "Runtime shut down (was %s).", previous_state.value
        )

    def health(self) -> HealthStatus:
        """Return a health snapshot of the Runtime and its subsystems."""
        if self._state == LifecycleState.FAILED:
            return HealthStatus(
                healthy=False,
                failed=True,
                message="Runtime is in FAILED state",
                details={"state": self._state.value},
            )

        details: dict[str, Any] = {
            "state": self._state.value,
            "nats_connected": self._nats_connected,
            "db_initialized": self._db_initialized,
            "worker_started": self._worker_started,
        }

        degraded = (
            not self._nats_connected
            or not self._db_initialized
        )

        return HealthStatus(
            healthy=self._state == LifecycleState.RUNNING and not degraded,
            degraded=degraded and self._state == LifecycleState.RUNNING,
            details=details,
        )

    # --- Internal initialization steps ---

    async def _init_database(self) -> None:
        """Initialize the database connection."""
        from nexusagent.infrastructure.db import get_db_manager

        db_manager = get_db_manager()
        await db_manager.init_db()
        if self._context:
            self._context.db_manager = db_manager
        self._db_initialized = True
        logger.info("Database initialized.")

    async def _init_nats(self) -> None:
        """Connect to the NATS bus."""
        from nexusagent.infrastructure.bus import get_bus

        bus = get_bus()
        await bus.connect()
        if self._context:
            self._context.bus = bus
        self._nats_connected = True
        logger.info("NATS bus connected.")

    async def _init_tool_manager(self) -> None:
        """Initialize the tool manager (registers tools)."""
        from nexusagent.tools.register_all import register_all

        # Core tool registration
        register_all()

        # Import and wire up ToolRegistry with context
        from nexusagent.tools.registry import registry

        if self._context:
            self._context.tool_registry = registry
            self._context.tool_initialized = True

        logger.info("Tool manager initialized.")
