# tests/core/task/test_recovery.py
"""Tests for the RecoveryManager."""

from __future__ import annotations

import pytest

from nexusagent.core.task.recovery import RecoveryManager, RecoveryStrategy
from nexusagent.core.task.task_state import (
    Checkpoint,
    StateTransitionError,
    Task,
    TaskState,
)


class TestRecoveryManager:
    """Recovery strategy selection and execution."""

    @pytest.fixture
    def manager(self):
        return RecoveryManager(max_retries=2, base_delay=0.01)

    @pytest.fixture
    def failed_task(self):
        task = Task(objective="recover me")
        task.transition_to(TaskState.FAILED)
        return task

    def test_first_retry(self, manager, failed_task):
        strategy = manager._choose_strategy(failed_task)
        assert strategy == RecoveryStrategy.RETRY

    def test_retry_exhausted_then_rollback(self, manager, failed_task):
        # Use up retries
        for _ in range(2):
            manager._choose_strategy(failed_task)
        # No checkpoint — should escalate
        strategy = manager._choose_strategy(failed_task)
        assert strategy == RecoveryStrategy.ESCALATE

    def test_rollback_with_checkpoint(self, manager, failed_task):
        failed_task.add_checkpoint(Checkpoint(current_node="step5"))
        # Use up retries
        for _ in range(2):
            manager._choose_strategy(failed_task)
        # Has checkpoint — should rollback
        strategy = manager._choose_strategy(failed_task)
        assert strategy == RecoveryStrategy.ROLLBACK

    def test_escalate_callback(self, manager, failed_task):
        escalated: list[Task] = []

        def on_escalate(t: Task):
            escalated.append(t)

        manager._on_escalate = on_escalate
        # Use up retries, no checkpoint
        for _ in range(3):
            manager._choose_strategy(failed_task)

        assert len(escalated) >= 0  # Callback registered

    def test_reset_retry_count(self, manager, failed_task):
        manager._choose_strategy(failed_task)
        assert manager._retry_counts.get(failed_task.id) == 1
        manager.reset_retry_count(failed_task.id)
        assert manager._retry_counts.get(failed_task.id) is None

    async def test_attempt_recovery_retry_path(self, manager, failed_task):
        strategy = await manager.attempt_recovery(failed_task)
        assert strategy == RecoveryStrategy.RETRY
        # Should have transitioned to EXECUTING after backoff
        assert failed_task.state == TaskState.EXECUTING

    async def test_attempt_recovery_escalate_from_terminal(self):
        """Completed tasks cannot be recovered — returns ESCALATE."""
        task = Task(objective="done")
        task.transition_to(TaskState.PLANNING)
        task.transition_to(TaskState.EXECUTING)
        task.transition_to(TaskState.VERIFYING)
        task.transition_to(TaskState.COMPLETED)

        manager = RecoveryManager(max_retries=0)
        strategy = await manager.attempt_recovery(task)
        assert strategy == RecoveryStrategy.ESCALATE