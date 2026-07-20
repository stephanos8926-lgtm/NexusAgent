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
        max_retries: int = 3,
        base_delay: float = 2.0,
        on_escalate: Callable[[Task], None] | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._retry_counts: dict[str, int] = {}
        self._on_escalate = on_escalate

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
            delay = self._base_delay * (2 ** (self._retry_counts.get(task.id, 0)))
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
