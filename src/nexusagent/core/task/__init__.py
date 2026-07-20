# src/nexusagent/core/task/__init__.py
"""Task execution model — Phase 2 of the 12-phase migration.

Provides the durable task state machine with checkpoint persistence
and recovery paths. Every unit of work in the system is a Task.
"""

from .recovery import RecoveryManager, RecoveryStrategy
from .task_state import Checkpoint, StateTransitionValidator, Task, TaskState
from .task_store import TaskStore

__all__ = [
    "Checkpoint",
    "RecoveryManager",
    "RecoveryStrategy",
    "StateTransitionValidator",
    "Task",
    "TaskState",
    "TaskStore",
]
