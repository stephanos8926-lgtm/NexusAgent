# src/nexusagent/core/task/__init__.py
"""Task execution model — Phase 2 of the 12-phase migration.

Provides the durable task state machine with checkpoint persistence
and recovery paths. Every unit of work in the system is a Task.
"""

from .task_state import TaskState, Task, Checkpoint, StateTransitionValidator
from .task_store import TaskStore
from .recovery import RecoveryManager, RecoveryStrategy

__all__ = [
    "TaskState",
    "Task",
    "Checkpoint",
    "StateTransitionValidator",
    "TaskStore",
    "RecoveryManager",
    "RecoveryStrategy",
]