"""Tests for task state, task dataclass, and state transitions validation."""

import pytest

from nexusagent.core.task.task_state import (
    StateTransitionValidator,
    Task,
    TaskState,
    StateTransitionError,
)


def _is_valid_transition(from_state: TaskState, to_state: TaskState) -> bool:
    try:
        StateTransitionValidator.validate(from_state, to_state)
        return True
    except StateTransitionError:
        return False


def test_task_state_values():
    """Verify all required task states exist and have correct values."""
    assert TaskState.CREATED.value == "CREATED"
    assert TaskState.PLANNING.value == "PLANNING"
    assert TaskState.EXECUTING.value == "EXECUTING"
    assert TaskState.VERIFYING.value == "VERIFYING"
    assert TaskState.COMPLETED.value == "COMPLETED"
    assert TaskState.FAILED.value == "FAILED"
    assert TaskState.RECOVERING.value == "RECOVERING"


def test_task_initialization():
    """Verify Task is initialized with default state and empty defaults."""
    task = Task(id="test-1", objective="Clean up room", owner="Jules")
    assert task.id == "test-1"
    assert task.objective == "Clean up room"
    assert task.owner == "Jules"
    assert task.state == TaskState.CREATED
    assert task.parent_task is None
    assert task.child_tasks == []
    assert task.checkpoints == []
    assert task.artifacts == {}


def test_valid_state_transitions():
    """Verify state transitions that are valid."""
    # CREATED -> PLANNING
    assert _is_valid_transition(TaskState.CREATED, TaskState.PLANNING)
    # CREATED -> FAILED
    assert _is_valid_transition(TaskState.CREATED, TaskState.FAILED)
    # PLANNING -> EXECUTING
    assert _is_valid_transition(TaskState.PLANNING, TaskState.EXECUTING)
    # EXECUTING -> VERIFYING
    assert _is_valid_transition(TaskState.EXECUTING, TaskState.VERIFYING)
    # VERIFYING -> COMPLETED
    assert _is_valid_transition(TaskState.VERIFYING, TaskState.COMPLETED)
    # FAILED -> RECOVERING
    assert _is_valid_transition(TaskState.FAILED, TaskState.RECOVERING)
    # RECOVERING -> EXECUTING
    assert _is_valid_transition(TaskState.RECOVERING, TaskState.EXECUTING)


def test_invalid_state_transitions():
    """Verify that illegal transitions raise StateTransitionErrors."""
    # EXECUTING -> CREATED is invalid
    assert not _is_valid_transition(TaskState.EXECUTING, TaskState.CREATED)
    # FAILED -> COMPLETED directly is invalid
    assert not _is_valid_transition(TaskState.FAILED, TaskState.COMPLETED)
    # COMPLETED -> EXECUTING is invalid
    assert not _is_valid_transition(TaskState.COMPLETED, TaskState.EXECUTING)

    task = Task(id="test-2", objective="Test", owner="Jules")
    with pytest.raises(StateTransitionError, match="Invalid transition"):
        task.transition_to(TaskState.EXECUTING)
