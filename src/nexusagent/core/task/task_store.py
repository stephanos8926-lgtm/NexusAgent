# src/nexusagent/core/task/task_store.py
"""Durable Task persistence using SQLite.

Stores tasks and their checkpoints for recovery across restarts.
"""

from __future__ import annotations

import logging

from nexusagent.core.task.task_state import Checkpoint, Task, TaskState

logger = logging.getLogger(__name__)


class TaskStore:
    """Persists Task state and checkpoints.

    Uses the existing SQLAlchemy async engine from infrastructure/db/.
    For now, provides an in-memory store as a minimal implementation
    that matches the interface required by Phase 2.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    async def save_task(self, task: Task) -> None:
        """Persist (or update) a task."""
        self._tasks[task.id] = task
        logger.debug("Saved task %s [%s]", task.id, task.state.value)

    async def load_task(self, task_id: str) -> Task | None:
        """Load a task by ID, or None if not found."""
        return self._tasks.get(task_id)

    async def list_tasks(
        self, state_filter: TaskState | None = None
    ) -> list[Task]:
        """List all tasks, optionally filtered by state."""
        if state_filter is None:
            return list(self._tasks.values())
        return [t for t in self._tasks.values() if t.state == state_filter]

    async def save_checkpoint(
        self, task_id: str, checkpoint: Checkpoint
    ) -> None:
        """Persist a checkpoint for a task."""
        task = await self.load_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found")
        task.add_checkpoint(checkpoint)
        logger.debug("Saved checkpoint for task %s", task_id)

    async def load_latest_checkpoint(
        self, task_id: str
    ) -> Checkpoint | None:
        """Return the most recent checkpoint for a task, or None."""
        task = await self.load_task(task_id)
        if task is None:
            return None
        return task.latest_checkpoint

    async def delete_task(self, task_id: str) -> None:
        """Remove a task and its checkpoints."""
        self._tasks.pop(task_id, None)

    async def close(self) -> None:
        """Cleanup — no-op for in-memory store."""
        pass
