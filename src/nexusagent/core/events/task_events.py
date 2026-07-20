"""Task lifecycle events.

Defines TaskEvent and its subtypes for task lifecycle tracking:
- task.created: A new task is submitted
- task.started: A worker begins executing
- task.completed: Execution finishes successfully
- task.failed: Execution terminates with error
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexusagent.core.events.base import SystemEvent, EventType


class TaskEventType(Enum):
    """Task event types as defined in the architecture."""
    CREATED = "created"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskEvent(SystemEvent):
    """Event emitted during task lifecycle transitions.
    
    Category: task
    NATS subjects: nexus.task.created, nexus.task.started, nexus.task.completed, nexus.task.failed
    
    Payload contains task-specific data:
    - task_id: The unique task identifier
    - objective: Task description/objective
    - owner: Who owns this task (worker_id, user, etc.)
    - state: Current state of the task
    - parent_task: Parent task ID if this is a subtask
    - error: Error message for failed events
    - checkpoint: Checkpoint data for recovery
    """
    
    category: EventType = EventType.TASK
    
    # Convenience factory methods for each event type
    @classmethod
    def created(
        cls,
        source: str,
        task_id: str,
        objective: str,
        owner: str = "",
        parent_task: str | None = None,
        **extra: Any,
    ) -> "TaskEvent":
        """Create a task.created event."""
        return cls(
            source=source,
            type="created",
            payload={
                "task_id": task_id,
                "objective": objective,
                "owner": owner,
                "parent_task": parent_task,
                **extra,
            },
        )
    
    @classmethod
    def started(
        cls,
        source: str,
        task_id: str,
        owner: str = "",
        **extra: Any,
    ) -> "TaskEvent":
        """Create a task.started event."""
        return cls(
            source=source,
            type="started",
            payload={
                "task_id": task_id,
                "owner": owner,
                **extra,
            },
        )
    
    @classmethod
    def completed(
        cls,
        source: str,
        task_id: str,
        owner: str = "",
        result: Any = None,
        **extra: Any,
    ) -> "TaskEvent":
        """Create a task.completed event."""
        return cls(
            source=source,
            type="completed",
            payload={
                "task_id": task_id,
                "owner": owner,
                "result": result,
                **extra,
            },
        )
    
    @classmethod
    def failed(
        cls,
        source: str,
        task_id: str,
        owner: str = "",
        error: str = "",
        **extra: Any,
    ) -> "TaskEvent":
        """Create a task.failed event."""
        return cls(
            source=source,
            type="failed",
            payload={
                "task_id": task_id,
                "owner": owner,
                "error": error,
                **extra,
            },
        )
    
    @property
    def task_id(self) -> str | None:
        """Extract task_id from payload."""
        return self.payload.get("task_id")
    
    @property
    def error(self) -> str | None:
        """Extract error from payload (for failed events)."""
        return self.payload.get("error")
    
    @property
    def result(self) -> Any:
        """Extract result from payload (for completed events)."""
        return self.payload.get("result")
