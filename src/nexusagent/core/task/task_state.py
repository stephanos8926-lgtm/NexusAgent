"""TaskState enum, Task dataclass, and StateTransitionValidator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexusagent.core.task.checkpoint import Checkpoint


class TaskState(StrEnum):
    """States of a task in the durable execution state machine."""

    CREATED = "CREATED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"


VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.CREATED: {TaskState.PLANNING, TaskState.FAILED},
    TaskState.PLANNING: {TaskState.EXECUTING, TaskState.FAILED},
    TaskState.EXECUTING: {TaskState.VERIFYING, TaskState.FAILED},
    TaskState.VERIFYING: {TaskState.COMPLETED, TaskState.FAILED},
    TaskState.COMPLETED: set(),  # Terminal state
    TaskState.FAILED: {TaskState.RECOVERING},  # "FAILED cannot become COMPLETED without RECOVERING"
    TaskState.RECOVERING: {TaskState.EXECUTING, TaskState.PLANNING, TaskState.FAILED, TaskState.COMPLETED},
}


class StateTransitionValidator:
    """Enforces legal transitions between TaskStates."""

    @staticmethod
    def is_valid_transition(from_state: TaskState, to_state: TaskState) -> bool:
        """Check if transitioning from `from_state` to `to_state` is legal."""
        if from_state == to_state:
            return True
        return to_state in VALID_TRANSITIONS.get(from_state, set())

    @staticmethod
    def validate(from_state: TaskState, to_state: TaskState) -> None:
        """Validate a transition, raising ValueError if illegal."""
        if not StateTransitionValidator.is_valid_transition(from_state, to_state):
            raise ValueError(f"Invalid state transition from {from_state} to {to_state}")


@dataclass
class Task:
    """Represents a durable execution task."""

    id: str
    objective: str
    owner: str
    state: TaskState = TaskState.CREATED
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def transition_to(self, new_state: TaskState) -> None:
        """Transition task to a new state after validating the transition."""
        StateTransitionValidator.validate(self.state, new_state)
        self.state = new_state
