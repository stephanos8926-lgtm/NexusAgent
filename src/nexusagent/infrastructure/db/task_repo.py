"""Task repository — CRUD operations on the ``tasks`` and ``results`` tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from .base import Base  # noqa: F401 — re-exported for consumer convenience
from .models import ResultModel, TaskModel

if TYPE_CHECKING:
    from .manager import DatabaseManager


class TaskRepository:
    """CRUD operations on tasks and results."""

    def __init__(self, db_manager: "DatabaseManager") -> None:
        self.db_manager = db_manager

    async def create_task(
        self, task_id: str, description: str, priority: int, metadata: dict
    ) -> None:
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
        async with self.db_manager.get_session() as session:
            stmt = (
                update(TaskModel).where(TaskModel.id == task_id).values(status=status)
            )
            await session.execute(stmt)

    async def get_task_status(self, task_id: str) -> str | None:
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
        from nexusagent.llm.models import TaskStatus  # noqa: E402 — avoid circular import

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
        from nexusagent.llm.models import TaskStatus  # noqa: E402 — avoid circular import

        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(TaskModel).where(TaskModel.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task or task.status != TaskStatus.FAILED:
                return None
            task.status = TaskStatus.PENDING
            return task_id
