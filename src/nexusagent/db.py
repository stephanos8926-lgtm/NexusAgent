# src/nexusagent/db.py
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, String, Integer, DateTime, Float, JSON
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import select, update

from nexusagent.config import settings

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    """Base class for SQLAlchemy models to resolve Mypy typing issues."""
    pass

class TaskModel(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    description = Column(String, nullable=False)
    priority = Column(Integer, default=1)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_json = Column(JSON, default={})

class ResultModel(Base):
    __tablename__ = "results"
    
    task_id = Column(String, primary_key=True)
    success = Column(Integer, default=0) # 1 for true, 0 for false
    data = Column(String, nullable=True)
    error = Column(String, nullable=True)
    completed_at = Column(DateTime, default=datetime.utcnow)
    duration = Column(Float, nullable=True)

class DatabaseManager:
    def __init__(self) -> None:
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{settings.server.db_path}",
            echo=False
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine, 
            expire_on_commit=False, 
            class_=AsyncSession
        )

    async def init_db(self) -> None:
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"Database initialized at {settings.server.db_path}")

    async def get_session(self) -> AsyncSession:
        return self.session_factory()

class TaskRepository:
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    async def create_task(self, task_id: str, description: str, priority: int, metadata: dict) -> None:
        async with self.db_manager.get_session() as session:
            task = TaskModel(
                id=task_id, 
                description=description, 
                priority=priority, 
                metadata_json=metadata
            )
            session.add(task)
            await session.commit()

    async def update_task_status(self, task_id: str, status: str) -> None:
        async with self.db_manager.get_session() as session:
            stmt = update(TaskModel).where(TaskModel.id == task_id).values(status=status)
            await session.execute(stmt)
            await session.commit()

    async def get_task_status(self, task_id: str) -> Optional[str]:
        async with self.db_manager.get_session() as session:
            result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
            task = result.scalar_one_or_none()
            return task.status if task else None

    async def save_result(self, task_id: str, success: bool, data: Optional[str], error: Optional[str], duration: Optional[float]) -> None:
        async with self.db_manager.get_session() as session:
            result = ResultModel(
                task_id=task_id,
                success=1 if success else 0,
                data=data,
                error=error,
                duration=duration
            )
            session.add(result)
            await session.commit()

# Global instances
db_manager = DatabaseManager()
task_repo = TaskRepository(db_manager)
