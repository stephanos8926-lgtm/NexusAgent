"""ORM models and TaskStore implementation for SQLite database persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.future import select

from nexusagent.core.task.checkpoint import Checkpoint
from nexusagent.core.task.task_state import Task, TaskState
from nexusagent.infrastructure.db import Base, get_db_manager

if TYPE_CHECKING:
    from nexusagent.infrastructure.db.manager import DatabaseManager

# Ensure our new tables exist. Let's define the SQLAlchemy models first.


class DurableTaskModel(Base):
    """ORM model for the `durable_tasks` table."""

    __tablename__ = "durable_tasks"

    id = Column(String, primary_key=True)
    objective = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    state = Column(String, nullable=False, default="CREATED")
    parent = Column(String, nullable=True)
    children_json = Column(String, nullable=False, default="[]")
    checkpoints_json = Column(String, nullable=False, default="[]")
    artifacts_json = Column(String, nullable=False, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class DurableCheckpointModel(Base):
    """ORM model for the `durable_checkpoints` table."""

    __tablename__ = "durable_checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=False, index=True)
    current_node = Column(String, nullable=False)
    completed_actions_json = Column(String, nullable=False, default="[]")
    files_changed_json = Column(String, nullable=False, default="[]")
    tool_results_json = Column(String, nullable=False, default="[]")
    next_action = Column(String, nullable=False, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class TaskStore:
    """TaskStore manages SQLite persistence for Tasks and Checkpoints using SQLAlchemy."""

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        """Initialize TaskStore. Uses the default DatabaseManager if none provided."""
        self.db_manager = db_manager or get_db_manager()

    async def init_tables(self) -> None:
        """Initialize tables if they don't exist yet."""
        async with self.db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def save_task(self, task: Task) -> None:
        """Save/update a task in the database."""
        await self.init_tables()
        async with self.db_manager.get_session() as session:
            stmt = select(DurableTaskModel).where(DurableTaskModel.id == task.id)
            result = await session.execute(stmt)
            db_task = result.scalar_one_or_none()

            checkpoints_data = [cp.to_dict() for cp in task.checkpoints]

            if db_task:
                db_task.state = task.state.value
                db_task.objective = task.objective
                db_task.owner = task.owner
                db_task.parent = task.parent
                db_task.children_json = json.dumps(task.children)
                db_task.checkpoints_json = json.dumps(checkpoints_data)
                db_task.artifacts_json = json.dumps(task.artifacts)
                db_task.updated_at = datetime.now(UTC)
            else:
                db_task = DurableTaskModel(
                    id=task.id,
                    objective=task.objective,
                    owner=task.owner,
                    state=task.state.value,
                    parent=task.parent,
                    children_json=json.dumps(task.children),
                    checkpoints_json=json.dumps(checkpoints_data),
                    artifacts_json=json.dumps(task.artifacts),
                )
                session.add(db_task)

    async def load_task(self, task_id: str) -> Task | None:
        """Load a task by ID from the database."""
        await self.init_tables()
        async with self.db_manager.get_session() as session:
            stmt = select(DurableTaskModel).where(DurableTaskModel.id == task_id)
            result = await session.execute(stmt)
            db_task = result.scalar_one_or_none()
            if not db_task:
                return None

            try:
                state = TaskState(db_task.state)
            except ValueError:
                state = TaskState.CREATED

            children = json.loads(db_task.children_json)
            artifacts = json.loads(db_task.artifacts_json)
            checkpoints_data = json.loads(db_task.checkpoints_json)
            checkpoints = [Checkpoint.from_dict(cp) for cp in checkpoints_data]

            return Task(
                id=db_task.id,
                objective=db_task.objective,
                owner=db_task.owner,
                state=state,
                parent=db_task.parent,
                children=children,
                checkpoints=checkpoints,
                artifacts=artifacts,
            )

    async def list_tasks(self, state_filter: TaskState | None = None) -> list[Task]:
        """List tasks, optionally filtered by state."""
        await self.init_tables()
        async with self.db_manager.get_session() as session:
            stmt = select(DurableTaskModel)
            if state_filter:
                stmt = stmt.where(DurableTaskModel.state == state_filter.value)
            result = await session.execute(stmt)
            db_tasks = result.scalars().all()

            tasks = []
            for db_task in db_tasks:
                try:
                    state = TaskState(db_task.state)
                except ValueError:
                    state = TaskState.CREATED

                children = json.loads(db_task.children_json)
                artifacts = json.loads(db_task.artifacts_json)
                checkpoints_data = json.loads(db_task.checkpoints_json)
                checkpoints = [Checkpoint.from_dict(cp) for cp in checkpoints_data]

                tasks.append(
                    Task(
                        id=db_task.id,
                        objective=db_task.objective,
                        owner=db_task.owner,
                        state=state,
                        parent=db_task.parent,
                        children=children,
                        checkpoints=checkpoints,
                        artifacts=artifacts,
                    )
                )
            return tasks

    async def save_checkpoint(self, task_id: str, checkpoint: Checkpoint) -> None:
        """Save a new checkpoint for a given task."""
        await self.init_tables()
        async with self.db_manager.get_session() as session:
            db_checkpoint = DurableCheckpointModel(
                task_id=task_id,
                current_node=checkpoint.current_node,
                completed_actions_json=json.dumps(checkpoint.completed_actions),
                files_changed_json=json.dumps(checkpoint.files_changed),
                tool_results_json=json.dumps(checkpoint.tool_results),
                next_action=checkpoint.next_action,
            )
            session.add(db_checkpoint)

            # Also update task's internal checkpoints list
            stmt = select(DurableTaskModel).where(DurableTaskModel.id == task_id)
            result = await session.execute(stmt)
            db_task = result.scalar_one_or_none()
            if db_task:
                checkpoints_data = json.loads(db_task.checkpoints_json)
                checkpoints_data.append(checkpoint.to_dict())
                db_task.checkpoints_json = json.dumps(checkpoints_data)
                db_task.updated_at = datetime.now(UTC)

    async def load_latest_checkpoint(self, task_id: str) -> Checkpoint | None:
        """Load the latest checkpoint for a given task."""
        await self.init_tables()
        async with self.db_manager.get_session() as session:
            stmt = (
                select(DurableCheckpointModel)
                .where(DurableCheckpointModel.task_id == task_id)
                .order_by(DurableCheckpointModel.id.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            db_checkpoint = result.scalar_one_or_none()
            if not db_checkpoint:
                return None

            return Checkpoint(
                current_node=db_checkpoint.current_node,
                completed_actions=json.loads(db_checkpoint.completed_actions_json),
                files_changed=json.loads(db_checkpoint.files_changed_json),
                tool_results=json.loads(db_checkpoint.tool_results_json),
                next_action=db_checkpoint.next_action,
            )


# Module-level singleton (lazy, injectable)
_task_store_instance: TaskStore | None = None


def get_task_store() -> TaskStore:
    """Get the global TaskStore singleton."""
    global _task_store_instance
    if _task_store_instance is None:
        _task_store_instance = TaskStore()
    return _task_store_instance


def set_task_store(instance: TaskStore) -> None:
    """Override the global TaskStore singleton (primarily for testing)."""
    global _task_store_instance
    _task_store_instance = instance
