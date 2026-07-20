"""Tests for task state, task dataclass, and state transitions validation."""

import pytest

from nexusagent.core.task.task_state import StateTransitionValidator, Task, TaskState


def test_task_state_values():
    """Verify all required task states exist and have correct values."""
    assert TaskState.CREATED == "CREATED"
    assert TaskState.PLANNING == "PLANNING"
    assert TaskState.EXECUTING == "EXECUTING"
    assert TaskState.VERIFYING == "VERIFYING"
    assert TaskState.COMPLETED == "COMPLETED"
    assert TaskState.FAILED == "FAILED"
    assert TaskState.RECOVERING == "RECOVERING"


def test_task_initialization():
    """Verify Task is initialized with default state and empty defaults."""
    task = Task(id="test-1", objective="Clean up room", owner="Jules")
    assert task.id == "test-1"
    assert task.objective == "Clean up room"
    assert task.owner == "Jules"
    assert task.state == TaskState.CREATED
    assert task.parent is None
    assert task.children == []
    assert task.checkpoints == []
    assert task.artifacts == {}


def test_valid_state_transitions():
    """Verify state transitions that are valid."""
    # CREATED -> PLANNING
    assert StateTransitionValidator.is_valid_transition(TaskState.CREATED, TaskState.PLANNING)
    # CREATED -> FAILED
    assert StateTransitionValidator.is_valid_transition(TaskState.CREATED, TaskState.FAILED)
    # PLANNING -> EXECUTING
    assert StateTransitionValidator.is_valid_transition(TaskState.PLANNING, TaskState.EXECUTING)
    # EXECUTING -> VERIFYING
    assert StateTransitionValidator.is_valid_transition(TaskState.EXECUTING, TaskState.VERIFYING)
    # VERIFYING -> COMPLETED
    assert StateTransitionValidator.is_valid_transition(TaskState.VERIFYING, TaskState.COMPLETED)
    # FAILED -> RECOVERING
    assert StateTransitionValidator.is_valid_transition(TaskState.FAILED, TaskState.RECOVERING)
    # RECOVERING -> EXECUTING
    assert StateTransitionValidator.is_valid_transition(TaskState.RECOVERING, TaskState.EXECUTING)
    # RECOVERING -> PLANNING
    assert StateTransitionValidator.is_valid_transition(TaskState.RECOVERING, TaskState.PLANNING)
    # RECOVERING -> FAILED
    assert StateTransitionValidator.is_valid_transition(TaskState.RECOVERING, TaskState.FAILED)
    # RECOVERING -> COMPLETED
    assert StateTransitionValidator.is_valid_transition(TaskState.RECOVERING, TaskState.COMPLETED)


def test_invalid_state_transitions():
    """Verify that illegal transitions raise ValueErrors."""
    # EXECUTING -> CREATED is invalid
    assert not StateTransitionValidator.is_valid_transition(TaskState.EXECUTING, TaskState.CREATED)
    # FAILED -> COMPLETED directly is invalid
    assert not StateTransitionValidator.is_valid_transition(TaskState.FAILED, TaskState.COMPLETED)
    # COMPLETED -> EXECUTING is invalid
    assert not StateTransitionValidator.is_valid_transition(TaskState.COMPLETED, TaskState.EXECUTING)

    task = Task(id="test-2", objective="Test", owner="Jules")
    with pytest.raises(ValueError, match="Invalid state transition"):
        task.transition_to(TaskState.EXECUTING)


def test_same_state_transition():
    """Verify that transitioning to the same state is always allowed/noop."""
    assert StateTransitionValidator.is_valid_transition(TaskState.CREATED, TaskState.CREATED)
    assert StateTransitionValidator.is_valid_transition(TaskState.EXECUTING, TaskState.EXECUTING)
