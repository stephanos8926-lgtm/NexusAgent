"""Task repository — CRUD operations on the ``tasks`` and ``results`` tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from .models import ResultModel, TaskModel

if TYPE_CHECKING:
    from .manager import DatabaseManager


class TaskRepository:
    """CRUD operations on tasks and results."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the repository with a database manager instance.

        Args:
            db_manager: The ``DatabaseManager`` providing session factories.
        """
        self.db_manager = db_manager

    async def create_task(
        self, task_id: str, description: str, priority: int, metadata: dict
    ) -> None:
        """Create a new task record (idempotent — skips if ID already exists).

        Args:
            task_id: Unique task identifier.
            description: Human-readable task description.
            priority: Task priority (lower = higher priority).
            metadata: Arbitrary JSON-serializable metadata dict.
        """
        async with self.db_manager.get_session() as session:
            # Check if task already exists (idempotent)
            existing = await session.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            )
            if existing.scalar_one_or_none():
                return  # Already exists, skip
            task = TaskModel(
                id=task_id,
                description=description,
                priority=priority,
                metadata_json=metadata,
            )
            session.add(task)

    async def update_task_status(self, task_id: str, status: str) -> None:
        """Update the status field of a task.

        Args:
            task_id: The task UUID to update.
            status: The new status string (e.g. ``"pending"``, ``"processing"``, ``"completed"``).
        """
        async with self.db_manager.get_session() as session:
            stmt = (
                update(TaskModel).where(TaskModel.id == task_id).values(status=status)
            )
            await session.execute(stmt)

    async def get_task_status(self, task_id: str) -> str | None:
        """Retrieve only the status field of a task.

        Args:
            task_id: The task UUID to look up.

        Returns:
            The status string, or None if the task doesn't exist.
        """
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            )
            task = result.scalar_one_or_none()
            return task.status if task else None

    async def get_task(self, task_id: str) -> dict | None:
        """Get a full task record by ID."""
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                return None
            return {
                "id": task.id,
                "description": task.description,
                "priority": task.priority,
                "status": task.status,
                "metadata": task.metadata_json,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }

    async def save_result(
        self,
        task_id: str,
        success: bool,
        data: str | None,
        error: str | None,
        duration: float | None,
    ) -> None:
        """Persist a task execution result.

        Args:
            task_id: The task UUID the result belongs to.
            success: Whether the task completed successfully.
            data: The result data (as a string) on success.
            error: The error message on failure.
            duration: Wall-clock execution time in seconds.
        """
        async with self.db_manager.get_session() as session:
            result = ResultModel(
                task_id=task_id,
                success=1 if success else 0,
                data=data,
                error=error,
                duration=duration,
            )
            session.add(result)

    async def list_tasks(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List tasks with optional status filter and pagination."""
        # Clamp limit to prevent resource exhaustion (max 200 per page)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        async with self.db_manager.get_session() as session:
            query = select(TaskModel).order_by(TaskModel.created_at.desc())
            if status:
                query = query.where(TaskModel.status == status)
            query = query.limit(limit).offset(offset)
            result = await session.execute(query)
            tasks = result.scalars().all()
            return [
                {
                    "id": t.id,
                    "description": t.description,
                    "priority": t.priority,
                    "status": t.status,
                    "metadata": t.metadata_json,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in tasks
            ]

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task. Returns True if cancelled, False if not found or terminal."""
        from nexusagent.llm.models import TaskStatus

        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                return False
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            task.status = TaskStatus.CANCELLED
            return True

    async def retry_task(self, task_id: str) -> str | None:
        """Retry a failed task. Returns task ID or None if not eligible."""
        from nexusagent.llm.models import TaskStatus

        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task or task.status != TaskStatus.FAILED:
                return None
            task.status = TaskStatus.PENDING
            return task_id
