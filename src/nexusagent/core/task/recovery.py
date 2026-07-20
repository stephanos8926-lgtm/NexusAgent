"""Recovery logic for failed durable tasks."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from nexusagent.core.task.checkpoint import Checkpoint
from nexusagent.core.task.task_state import Task, TaskState
from nexusagent.core.task.task_store import get_task_store

if TYPE_CHECKING:
    from nexusagent.core.task.task_store import TaskStore

logger = logging.getLogger(__name__)


class PermanentFailureError(Exception):
    """Raised when a task exceeds retry limits and must escalate."""


class RecoveryManager:
    """Manages the recovery of failed tasks with exponential backoff and rollbacks."""

    def __init__(self, task_store: TaskStore | None = None) -> None:
        """Initialize the RecoveryManager."""
        self.task_store = task_store or get_task_store()

    async def recover_task(
        self,
        task_id: str,
        execute_fn: Callable[[Task, Checkpoint | None], Any],
        max_attempts: int = 3,
        delays: list[float] | None = None,
        on_failed_event: Callable[[str, str], Any] | None = None,
    ) -> Any:
        """Perform recovery logic:

        1. FAILED to RECOVERING transition.
        2. Attempt exponential backoff retry.
        3. Rollback to last clean checkpoint.
        4. Escalate to POL on permanent failure (emit task.failed event).
        """
        actual_delays = delays if delays is not None else [2.0, 4.0, 8.0]
        task = await self.task_store.load_task(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found in store.")

        # Ensure task transitions to FAILED first if not already
        if task.state != TaskState.FAILED:
            task.transition_to(TaskState.FAILED)
            await self.task_store.save_task(task)

        # Transition to RECOVERING
        task.transition_to(TaskState.RECOVERING)
        await self.task_store.save_task(task)

        checkpoint = await self.task_store.load_latest_checkpoint(task_id)
        attempt = 0

        while attempt < max_attempts:
            delay = actual_delays[min(attempt, len(actual_delays) - 1)]
            logger.warning(
                f"Task {task_id} recovery attempt {attempt + 1}/{max_attempts}. "
                f"Waiting {delay}s before retrying..."
            )
            await asyncio.sleep(delay)

            try:
                # Transition to EXECUTING to retry
                task.transition_to(TaskState.EXECUTING)
                await self.task_store.save_task(task)

                # Attempt execution
                result = await execute_fn(task, checkpoint)

                # Transition through VERIFYING to COMPLETED on success
                task.transition_to(TaskState.VERIFYING)
                await self.task_store.save_task(task)

                task.transition_to(TaskState.COMPLETED)
                await self.task_store.save_task(task)
                return result

            except Exception as e:
                logger.error(f"Recovery attempt {attempt + 1} failed with error: {e}")
                # Transition back to FAILED/RECOVERING
                task.transition_to(TaskState.FAILED)
                await self.task_store.save_task(task)
                task.transition_to(TaskState.RECOVERING)
                await self.task_store.save_task(task)
                attempt += 1

        # If we got here, permanent failure
        task.transition_to(TaskState.FAILED)
        await self.task_store.save_task(task)

        # Escalate to POL (emit task.failed event)
        msg = f"Task {task_id} permanently failed after {max_attempts} recovery attempts."
        if on_failed_event:
            try:
                await on_failed_event(task_id, msg)
            except Exception as event_err:
                logger.error(f"Failed to emit task.failed event: {event_err}")

        raise PermanentFailureError(msg)
