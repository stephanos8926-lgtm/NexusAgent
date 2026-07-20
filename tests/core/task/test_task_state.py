# tests/core/task/test_task_state.py
"""Tests for the Task state machine."""

from __future__ import annotations

import pytest

from nexusagent.core.task.task_state import (
    Checkpoint,
    StateTransitionError,
    StateTransitionValidator,
    Task,
    TaskState,
)


class TestStateTransitionValidator:
    """Valid transitions must pass; invalid must raise."""

    def test_created_to_planning(self):
        StateTransitionValidator.validate(TaskState.CREATED, TaskState.PLANNING)

    def test_planning_to_executing(self):
        StateTransitionValidator.validate(TaskState.PLANNING, TaskState.EXECUTING)

    def test_executing_to_verifying(self):
        StateTransitionValidator.validate(TaskState.EXECUTING, TaskState.VERIFYING)

    def test_verifying_to_completed(self):
        StateTransitionValidator.validate(TaskState.VERIFYING, TaskState.COMPLETED)

    def test_any_to_failed(self):
        for state in TaskState:
            if state == TaskState.COMPLETED:
                continue  # Terminal — cannot fail from completed
            try:
                StateTransitionValidator.validate(state, TaskState.FAILED)
            except StateTransitionError:
                if state not in (TaskState.CREATED, TaskState.PLANNING,
                                 TaskState.EXECUTING, TaskState.VERIFYING,
                                 TaskState.FAILED, TaskState.RECOVERING):
                    pytest.fail(f"Unexpected failure for {state} → FAILED")

    def test_completed_is_terminal(self):
        with pytest.raises(StateTransitionError):
            StateTransitionValidator.validate(TaskState.COMPLETED, TaskState.EXECUTING)

    def test_skip_state_invalid(self):
        with pytest.raises(StateTransitionError):
            StateTransitionValidator.validate(TaskState.CREATED, TaskState.COMPLETED)

    def test_failed_to_recovering(self):
        StateTransitionValidator.validate(TaskState.FAILED, TaskState.RECOVERING)

    def test_recovering_to_executing(self):
        StateTransitionValidator.validate(TaskState.RECOVERING, TaskState.EXECUTING)


class TestTask:
    """Task dataclass behavior."""

    def test_default_state_is_created(self):
        task = Task(objective="test")
        assert task.state == TaskState.CREATED

    def test_transition_updates_state(self):
        task = Task(objective="test")
        task.transition_to(TaskState.PLANNING)
        assert task.state == TaskState.PLANNING

    def test_invalid_transition_raises(self):
        task = Task(objective="test")
        with pytest.raises(StateTransitionError):
            task.transition_to(TaskState.COMPLETED)  # Skip states

    def test_add_checkpoint(self):
        task = Task(objective="test")
        cp = Checkpoint(current_node="node1", completed_actions=["step1"])
        task.add_checkpoint(cp)
        assert len(task.checkpoints) == 1
        assert task.latest_checkpoint is cp

    def test_latest_checkpoint_none(self):
        task = Task(objective="test")
        assert task.latest_checkpoint is None

    def test_to_dict_roundtrip(self):
        task = Task(
            id="abc123",
            objective="do the thing",
            owner="worker1",
            state=TaskState.EXECUTING,
        )
        cp = Checkpoint(current_node="main", completed_actions=["step1"])
        task.add_checkpoint(cp)

        data = task.to_dict()
        restored = Task.from_dict(data)

        assert restored.id == "abc123"
        assert restored.objective == "do the thing"
        assert restored.owner == "worker1"
        assert restored.state == TaskState.EXECUTING
        assert len(restored.checkpoints) == 1
        assert restored.latest_checkpoint.current_node == "main"

    def test_to_dict_defaults(self):
        task = Task(objective="minimal")
        data = task.to_dict()
        restored = Task.from_dict(data)
        assert restored.objective == "minimal"
        assert restored.state == TaskState.CREATED
        assert restored.checkpoints == []


class TestCheckpoint:
    """Checkpoint serialization."""

    def test_to_dict(self):
        cp = Checkpoint(
            current_node="step2",
            completed_actions=["a", "b"],
            files_changed=["f1.py"],
            tool_results=[{"tool": "read", "status": "ok"}],
            next_action="verify",
        )
        d = cp.to_dict()
        assert d["current_node"] == "step2"
        assert d["completed_actions"] == ["a", "b"]
        assert d["next_action"] == "verify"

    def test_roundtrip(self):
        original = Checkpoint(current_node="x", completed_actions=["y"])
        restored = Checkpoint.from_dict(original.to_dict())
        assert restored.current_node == "x"
        assert restored.completed_actions == ["y"]
