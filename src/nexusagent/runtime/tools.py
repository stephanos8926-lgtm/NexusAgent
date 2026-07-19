"""ToolManager — wraps tool registration with lifecycle awareness.

Provides explicit lifecycle for tool registration, wrapping the existing
module-level _ensure_tools_registered() pattern in a managed component
that can use RuntimeContext when available.
"""

from __future__ import annotations

import logging
import threading

from nexusagent.runtime.context import RuntimeContext
from nexusagent.runtime.lifecycle import (
    HealthStatus,
    LifecycleMixin,
    LifecycleState,
)

logger = logging.getLogger("nexusagent.runtime.tools")


class ToolManager(LifecycleMixin):
    """Managed tool registration with RuntimeContext support.

    Wraps _ensure_tools_registered() with lifecycle awareness.
    When a RuntimeContext is active, sets context.tool_initialized = True
    instead of the module-level bool.
    """

    def __init__(self, context: RuntimeContext | None = None) -> None:
        self._state = LifecycleState.CREATED
        self._context = context
        self._lock = threading.RLock()
        self._initialized = False

    # --- LifecycleMixin ---

    @property
    def state(self) -> LifecycleState:
        return self._state

    async def initialize(self) -> None:
        """Register all tools and transition to RUNNING."""
        self._state = LifecycleState.INITIALIZING
        try:
            self.ensure_registered()
        except Exception as e:
            self._state = LifecycleState.FAILED
            logger.error("ToolManager initialize failed: %s", e)
            raise
        self._state = LifecycleState.RUNNING

    async def shutdown(self) -> None:
        """No-op for tools (tools don't need shutdown)."""
        self._state = LifecycleState.TERMINATED

    def health(self) -> HealthStatus:
        return HealthStatus(
            healthy=self._state == LifecycleState.RUNNING,
            details={
                "state": self._state.value,
                "initialized": self._initialized,
            },
        )

    # --- Public API ---

    def ensure_registered(self) -> None:
        """Register all tools (lazy, thread-safe).

        Thread-safe via RLock — concurrent calls serialize.
        Uses double-checked locking pattern.

        When RuntimeContext is active, sets context.tool_initialized = True
        instead of the module-level bool in core.agent.
        """
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return  # Double-check after acquiring lock

            from nexusagent.tools.register_all import register_all

            register_all()
            self._initialized = True

            if self._context is not None:
                self._context.tool_initialized = True
                from nexusagent.tools.registry import registry

                self._context.tool_registry = registry

    def is_registered(self) -> bool:
        """Check if tools are registered."""
        return self._initialized
