"""Dependency injection container for the NexusAgent runtime.

RuntimeContext is the explicit container through which all shared dependencies
are passed. It replaces 20+ module-level singletons with a typed, frozen
dataclass that is created at Runtime initialization and passed to components.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


# ContextVar-based accessor — fallback for during the transition period.
# Components should receive RuntimeContext explicitly whenever possible.
_runtime_context_var: contextvars.ContextVar[RuntimeContext | None] = (
    contextvars.ContextVar("runtime_context", default=None)
)


@dataclass
class RuntimeContext:
    """Explicit dependency injection container.

    Created at Runtime initialization and passed to all managed components.
    Read-only after construction (frozen dataclass pattern — treat as immutable).

    Migrated global state:
      - current_session_id: replaces core.agent._current_session ContextVar
      - workspace_memory_dir: replaces core.agent._ws_memory_dir ContextVar
      - workspace_root: replaces tools.fs_base._workspace_root_var ContextVar
      - policy_context: replaces tools.registry.policy._policy_context ContextVar
      - tool_initialized: replaces core.agent._tools_registered module bool
      - hook_manager: replaces hooks.__init__._manager singleton
      - (session_manager, worker_manager: owned by Runtime, not context)
    """

    # System identity
    config: Any  # ConfigSchema — avoid circular import at runtime

    # Tool system (set by ToolManager)
    tool_registry: Any | None = None  # ToolRegistry
    tool_roles: dict[str, list[str]] | None = None
    tool_initialized: bool = False

    # Capabilities carried by RuntimeContext
    capabilities: list[str] = field(default_factory=list)

    # Session identity (migrated from core.agent ContextVars)
    current_session_id: str | None = None
    workspace_memory_dir: str | None = None

    # Workspace path jail (migrated from tools.fs_base ContextVar)
    workspace_root: Path | None = None

    # Tool policy (migrated from tools.registry.policy ContextVar)
    # NOTE: Owned by ManagedSession lifecycle — set on init, cleared on shutdown
    policy_context: dict[str, Any] | None = None

    # Sub-system references (set by Runtime)
    bus: Any | None = None  # AgentBus
    db_manager: Any | None = None  # DBManager
    hook_manager: Any | None = None  # HookManager

    # Session/worker managers — owned by Runtime, stored here for convenience
    session_manager: Any | None = None
    worker_manager: Any | None = None

    # Arbitrary extra state for extensions (not frozen after all)
    extra: dict[str, Any] = field(default_factory=dict)


def current_context() -> RuntimeContext | None:
    """Return the active RuntimeContext, or None if no Runtime is active.

    This is a fallback accessor for the transition period. Components that
    are created by the Runtime receive the context explicitly at construction.
    """
    return _runtime_context_var.get()


def set_current_context(ctx: RuntimeContext | None) -> None:
    """Set the active RuntimeContext for the current task.

    Called by Runtime during initialize() and shutdown().
    Components should NOT call this directly — receive context via constructor.
    """
    _runtime_context_var.set(ctx)
