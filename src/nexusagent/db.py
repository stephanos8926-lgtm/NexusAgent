import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from nexusagent.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class TaskModel(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True)
    description = Column(String, nullable=False)
    priority = Column(Integer, default=1)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    metadata_json = Column(JSON, default={})


class ResultModel(Base):
    __tablename__ = "results"
    task_id = Column(String, primary_key=True)
    success = Column(Integer, default=0)
    data = Column(String, nullable=True)
    error = Column(String, nullable=True)
    completed_at = Column(DateTime, default=lambda: datetime.now(UTC))
    duration = Column(Float, nullable=True)


class DatabaseManager:
    def __init__(self, db_url: str | None = None) -> None:
        # Always resolve from settings at creation time
        url = db_url or settings.server.db_path
        if not url.startswith("sqlite+aiosqlite://"):
            if url.startswith("sqlite://"):
                url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
            elif not url.startswith("://"):
                url = f"sqlite+aiosqlite:///{url}"
        self.db_url = url
        self.engine = create_async_engine(self.db_url, echo=False, future=True)
        self.async_session = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    def reinit(self, db_url: str | None = None) -> None:
        """Reinitialize with a new DB URL (used by tests)."""
        url = db_url or settings.server.db_path
        if not url.startswith("sqlite+aiosqlite://"):
            if url.startswith("sqlite://"):
                url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
            elif not url.startswith("://"):
                url = f"sqlite+aiosqlite:///{url}"
        self.db_url = url
        self.engine = create_async_engine(self.db_url, echo=False, future=True)
        self.async_session = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Database initialized at {self.db_url}")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def execute(self, query: str, params: dict | None = None) -> Any:
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            return result


class TaskRepository:
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    async def create_task(
        self, task_id: str, description: str, priority: int, metadata: dict
    ) -> None:
        async with self.db_manager.get_session() as session:
            # Check if task already exists (idempotent)
            existing = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
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
            stmt = update(TaskModel).where(TaskModel.id == task_id).values(status=status)
            await session.execute(stmt)

    async def get_task_status(self, task_id: str) -> str | None:
        async with self.db_manager.get_session() as session:
            result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
            task = result.scalar_one_or_none()
            return task.status if task else None

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
        """Cancel a task. Returns True if cancelled, False if not found or already terminal."""
        from nexusagent.models import TaskStatus

        async with self.db_manager.get_session() as session:
            result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                return False
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                return False
            task.status = TaskStatus.FAILED
            return True

    async def retry_task(self, task_id: str) -> str | None:
        """Retry a failed task. Returns task ID or None if not eligible."""
        from nexusagent.models import TaskStatus

        async with self.db_manager.get_session() as session:
            result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
            task = result.scalar_one_or_none()
            if not task or task.status != TaskStatus.FAILED:
                return None
            task.status = TaskStatus.PENDING
            return task_id


db_manager = DatabaseManager()
task_repo = TaskRepository(db_manager)
