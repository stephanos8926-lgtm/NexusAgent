# SPDX-License-Identifier: MIT

# src/nexusagent/core/task/recovery.py
"""Recovery logic for failed tasks.

Provides retry (exponential backoff), rollback (last checkpoint),
and escalate (permanent failure) strategies.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from enum import Enum
from typing import Any

from nexusagent.core.task.task_state import StateTransitionError, Task, TaskState

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Available recovery strategies for failed tasks."""

    RETRY = "retry"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"


class RecoveryManager:
    """Manages recovery for failed tasks.

    Follows a priority chain: retry → rollback → escalate.
    """

    def __init__(
        self,
        store: Any = None,
        max_retries: int = 3,
        base_delay: float = 2.0,
        on_escalate: Callable[[Task], None] | None = None,
    ) -> None:
        self._store = store
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._retry_counts: dict[str, int] = {}
        self._on_escalate = on_escalate

    async def recover_task(
        self,
        task_id: str,
        execute_fn: Callable[[Task, Any], Any],
        on_failed_event: Callable[[str, str], Any] | None = None,
    ) -> Any:
        """Load and attempt recovery of a failed task by re-executing it with RETRY/ROLLBACK."""
        if self._store is None:
            raise ValueError("Store must be configured on RecoveryManager for recover_task")

        task = await self._store.load_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found in store")

        checkpoint = await self._store.load_latest_checkpoint(task_id)
        strategy = await self.attempt_recovery(task)

        if strategy in (RecoveryStrategy.RETRY, RecoveryStrategy.ROLLBACK):
            try:
                # Execute the task resumption
                result = await execute_fn(task, checkpoint)
                self.reset_retry_count(task_id)

                # Transition to completed
                try:
                    task.transition_to(TaskState.VERIFYING)
                    task.transition_to(TaskState.COMPLETED)
                except Exception:
                    task.state = TaskState.COMPLETED
                await self._store.save_task(task)
                return result
            except Exception as exc:
                # Classify exception
                from nexusagent.core.observability.failures import FailureClassifier, FailureType

                failure_type = FailureClassifier.classify(exc)
                logger.error(
                    "Failure occurred during recovery execution of task %s (type: %s): %s",
                    task_id,
                    failure_type.value,
                    exc,
                )

                if failure_type == FailureType.SECURITY:
                    if on_failed_event:
                        await on_failed_event(task_id, f"Security error: {exc}")
                    raise
                elif failure_type == FailureType.DETERMINISTIC:
                    if on_failed_event:
                        await on_failed_event(task_id, f"Deterministic error: {exc}")
                    raise
                else:
                    # Transient errors can be retried further or raised
                    raise
        else:
            # ESCALATE
            if on_failed_event:
                await on_failed_event(task_id, "Recovery escalated")
            raise RuntimeError(f"Task {task_id} recovery escalated to permanent failure")

    async def attempt_recovery(self, task: Task) -> RecoveryStrategy:
        """Attempt to recover a failed task.

        Returns the strategy used: RETRY, ROLLBACK, or ESCALATE.
        """
        strategy = self._choose_strategy(task)
        logger.info(
            "Recovery for task %s: %s (retry %d/%d)",
            task.id,
            strategy.value,
            self._retry_counts.get(task.id, 0),
            self._max_retries,
        )

        try:
            task.transition_to(TaskState.RECOVERING)
        except StateTransitionError:
            logger.error("Task %s cannot transition to RECOVERING", task.id)
            return RecoveryStrategy.ESCALATE

        if strategy == RecoveryStrategy.RETRY:
            delay = self._base_delay * (2 ** (self._retry_counts.get(task.id, 0) - 1))
            await asyncio.sleep(delay)
            try:
                task.transition_to(TaskState.EXECUTING)
            except StateTransitionError:
                return RecoveryStrategy.ESCALATE
        elif strategy == RecoveryStrategy.ROLLBACK:
            # Rollback — attempt to return to EXECUTING from latest checkpoint
            if task.latest_checkpoint is not None:
                logger.info(
                    "Rolling back task %s to node %s",
                    task.id,
                    task.latest_checkpoint.current_node,
                )
            try:
                task.transition_to(TaskState.EXECUTING)
            except StateTransitionError:
                return RecoveryStrategy.ESCALATE
        else:
            # ESCALATE
            if self._on_escalate:
                self._on_escalate(task)
            logger.warning("Task %s escalated to POL", task.id)
            return RecoveryStrategy.ESCALATE

        return strategy

    def _choose_strategy(self, task: Task) -> RecoveryStrategy:
        """Choose recovery strategy based on retry count."""
        retries = self._retry_counts.get(task.id, 0)
        if retries < self._max_retries:
            self._retry_counts[task.id] = retries + 1
            return RecoveryStrategy.RETRY
        if task.latest_checkpoint is not None:
            return RecoveryStrategy.ROLLBACK
        return RecoveryStrategy.ESCALATE

    def reset_retry_count(self, task_id: str) -> None:
        """Reset retry tracking for a task (after successful execution)."""
        self._retry_counts.pop(task_id, None)
