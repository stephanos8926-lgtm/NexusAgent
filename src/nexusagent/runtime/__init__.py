"""NexusAgent Runtime — lifecycle, DI, and execution boundaries.

The runtime package provides the foundation layer for all NexusAgent components:
- Lifecycle state machine (CREATED → INITIALIZING → RUNNING → ... → TERMINATED)
- Dependency injection container (RuntimeContext)
- Runtime kernel (initialize/shutdown orchestration)
- Managed adapters for Session, Worker, and Tool components
"""

# Lazy imports — submodules are created per-step and add themselves here.
# This allows importing the package even when submodules don't exist yet.

from nexusagent.runtime.context import (
    RuntimeContext,
    current_context,
    set_current_context,
)
from nexusagent.runtime.lifecycle import (
    HealthStatus,
    LifecycleMixin,
    LifecycleState,
)
from nexusagent.runtime.session import (
    ManagedSession,
    RuntimeSessionManager,
    SessionMetadata,
)
from nexusagent.runtime.tools import ToolManager
from nexusagent.runtime.worker import (
    ManagedWorker,
    RuntimeWorkerManager,
    WorkerMetadata,
)

__all__: list[str] = [
    "HealthStatus",
    "LifecycleMixin",
    "LifecycleState",
    "ManagedSession",
    "ManagedWorker",
    "RuntimeContext",
    "RuntimeSessionManager",
    "RuntimeWorkerManager",
    "SessionMetadata",
    "ToolManager",
    "WorkerMetadata",
    "current_context",
    "set_current_context",
]
