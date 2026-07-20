# src/nexusagent/core/task/task_state.py
"""Task state machine — durable execution model for NexusAgent.

Defines the lifecycle of every unit of work in the system.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskState(Enum):
    """Valid states for a Task."""

    CREATED = "CREATED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"


# ── Legal State Transitions ──────────────────────────────────────────────────

_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.CREATED: {TaskState.PLANNING, TaskState.FAILED},
    TaskState.PLANNING: {TaskState.EXECUTING, TaskState.FAILED},
    TaskState.EXECUTING: {TaskState.VERIFYING, TaskState.FAILED},
    TaskState.VERIFYING: {TaskState.COMPLETED, TaskState.FAILED},
    TaskState.COMPLETED: set(),  # Terminal state
    TaskState.FAILED: {TaskState.RECOVERING},
    TaskState.RECOVERING: {TaskState.EXECUTING, TaskState.FAILED},
}


class StateTransitionError(ValueError):
    """Raised when an invalid state transition is attempted."""


class StateTransitionValidator:
    """Enforces legal TaskState transitions."""

    @staticmethod
    def validate(from_state: TaskState, to_state: TaskState) -> None:
        """Raise StateTransitionError if transition is not allowed."""
        allowed = _TRANSITIONS.get(from_state)
        if allowed is None:
            raise StateTransitionError(f"Unknown source state: {from_state}")
        if to_state not in allowed:
            raise StateTransitionError(
                f"Invalid transition: {from_state.value} → {to_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )


@dataclass
class Checkpoint:
    """Snapshot of execution state at a point in time."""

    current_node: str
    completed_actions: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_node": self.current_node,
            "completed_actions": self.completed_actions,
            "files_changed": self.files_changed,
            "tool_results": self.tool_results,
            "next_action": self.next_action,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        return cls(
            current_node=data["current_node"],
            completed_actions=data.get("completed_actions", []),
            files_changed=data.get("files_changed", []),
            tool_results=data.get("tool_results", []),
            next_action=data.get("next_action", ""),
        )


@dataclass
class Task:
    """A durable unit of work in the NexusAgent system."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    objective: str = ""
    owner: str = ""
    state: TaskState = TaskState.CREATED
    parent_task: str | None = None
    child_tasks: list[str] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def transition_to(self, new_state: TaskState) -> None:
        """Transition to new_state, validating first."""
        StateTransitionValidator.validate(self.state, new_state)
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)

    def add_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Add a checkpoint and record the state."""
        self.checkpoints.append(checkpoint)
        self.updated_at = datetime.now(timezone.utc)

    @property
    def latest_checkpoint(self) -> Checkpoint | None:
        """Return the most recent checkpoint, or None."""
        return self.checkpoints[-1] if self.checkpoints else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objective": self.objective,
            "owner": self.owner,
            "state": self.state.value,
            "parent_task": self.parent_task,
            "child_tasks": self.child_tasks,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "artifacts": self.artifacts,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            id=data["id"],
            objective=data.get("objective", ""),
            owner=data.get("owner", ""),
            state=TaskState(data["state"]),
            parent_task=data.get("parent_task"),
            child_tasks=data.get("child_tasks", []),
            checkpoints=[Checkpoint.from_dict(c) for c in data.get("checkpoints", [])],
            artifacts=data.get("artifacts", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )