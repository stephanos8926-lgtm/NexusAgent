import logging
import uuid
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

from nexusagent.infrastructure.config import settings

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
    metadata_json = Column(JSON, default=dict)


class ResultModel(Base):
    __tablename__ = "results"
    task_id = Column(String, primary_key=True)
    success = Column(Integer, default=0)
    data = Column(String, nullable=True)
    error = Column(String, nullable=True)
    completed_at = Column(DateTime, default=lambda: datetime.now(UTC))
    duration = Column(Float, nullable=True)


class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    working_dir = Column(String, nullable=False, default=".")
    memory_id = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    tool_name = Column(String, nullable=True)
    tool_args = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


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
        # Ensure parent directory exists for file-based SQLite DBs
        if "sqlite" in url:
            from pathlib import Path as _Path
            db_file = url.split("///")[-1] if "///" in url else ""
            if db_file and not db_file.startswith(":memory:"):
                _Path(db_file).parent.mkdir(parents=True, exist_ok=True)
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
        # Ensure parent directory exists for file-based SQLite DBs
        if "sqlite" in url:
            from pathlib import Path as _Path
            db_file = url.split("///")[-1] if "///" in url else ""
            if db_file and not db_file.startswith(":memory:"):
                _Path(db_file).parent.mkdir(parents=True, exist_ok=True)

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
        from nexusagent.llm.models import TaskStatus

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
        from nexusagent.llm.models import TaskStatus

        async with self.db_manager.get_session() as session:
            result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
            task = result.scalar_one_or_none()
            if not task or task.status != TaskStatus.FAILED:
                return None
            task.status = TaskStatus.PENDING
            return task_id


class SessionRepository:
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    async def create_session(self, working_dir: str = ".", memory_id: str | None = None) -> str:
        session_id = str(uuid.uuid4())
        async with self.db_manager.get_session() as session:
            sess = SessionModel(
                id=session_id,
                working_dir=working_dir,
                memory_id=memory_id,
            )
            session.add(sess)
        return session_id

    async def get_session(self, session_id: str) -> dict | None:
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            s = result.scalar_one_or_none()
            if not s:
                return None
            return {
                "id": s.id,
                "working_dir": s.working_dir,
                "memory_id": s.memory_id,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }

    async def update_status(self, session_id: str, status: str) -> None:
        async with self.db_manager.get_session() as session:
            stmt = update(SessionModel).where(SessionModel.id == session_id).values(status=status)
            await session.execute(stmt)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: str | None = None,
        tool_args: dict | None = None,
    ) -> str:
        msg_id = str(uuid.uuid4())
        async with self.db_manager.get_session() as session:
            msg = MessageModel(
                id=msg_id,
                session_id=session_id,
                role=role,
                content=content,
                tool_name=tool_name,
                tool_args=tool_args,
            )
            session.add(msg)
        return msg_id

    async def get_messages(self, session_id: str, limit: int = 100) -> list[dict]:
        async with self.db_manager.get_session() as session:
            query = (
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.created_at.asc())
                .limit(limit)
            )
            result = await session.execute(query)
            messages = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "session_id": m.session_id,
                    "role": m.role,
                    "content": m.content,
                    "tool_name": m.tool_name,
                    "tool_args": m.tool_args,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ]

    async def list_sessions(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List sessions with optional status filter and pagination."""
        async with self.db_manager.get_session() as session:
            query = select(SessionModel).order_by(SessionModel.updated_at.desc())
            if status:
                query = query.where(SessionModel.status == status)
            query = query.limit(limit).offset(offset)
            result = await session.execute(query)
            sessions = result.scalars().all()
            return [
                {
                    "id": s.id,
                    "working_dir": s.working_dir,
                    "memory_id": s.memory_id,
                    "status": s.status,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in sessions
            ]

    async def rename_session(self, session_id: str, new_id: str) -> bool:
        """Rename a session. Returns True if renamed, False if not found or new_id taken."""
        async with self.db_manager.get_session() as session:
            # Check target doesn't exist
            existing = await session.execute(
                select(SessionModel).where(SessionModel.id == new_id)
            )
            if existing.scalar_one_or_none():
                return False
            # Rename
            stmt = update(SessionModel).where(SessionModel.id == session_id).values(id=new_id)
            result = await session.execute(stmt)
            return result.rowcount > 0

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages. Returns True if deleted."""
        async with self.db_manager.get_session() as session:
            # Delete messages first (FK-like cleanup, no actual FK constraint)
            await session.execute(
                text("DELETE FROM messages WHERE session_id = :sid"),
                {"sid": session_id},
            )
            result = await session.execute(
                text("DELETE FROM sessions WHERE id = :sid"),
                {"sid": session_id},
            )
            return result.rowcount > 0

    async def fork_session(self, source_id: str, new_working_dir: str | None = None) -> str | None:
        """Fork a session: copy messages to a new session ID. Returns new session ID or None."""
        async with self.db_manager.get_session() as session:
            src = await session.execute(
                select(SessionModel).where(SessionModel.id == source_id)
            )
            src_sess = src.scalar_one_or_none()
            if not src_sess:
                return None

            new_id = str(uuid.uuid4())
            new_sess = SessionModel(
                id=new_id,
                working_dir=new_working_dir or src_sess.working_dir,
                memory_id=src_sess.memory_id,
                status="active",
            )
            session.add(new_sess)

            # Copy messages
            msgs = await session.execute(
                select(MessageModel)
                .where(MessageModel.session_id == source_id)
                .order_by(MessageModel.created_at.asc())
            )
            for msg in msgs.scalars().all():
                new_msg = MessageModel(
                    id=str(uuid.uuid4()),
                    session_id=new_id,
                    role=msg.role,
                    content=msg.content,
                    tool_name=msg.tool_name,
                    tool_args=msg.tool_args,
                )
                session.add(new_msg)

            return new_id


db_manager = DatabaseManager()
task_repo = TaskRepository(db_manager)
session_repo = SessionRepository(db_manager)
