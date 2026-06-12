"""Tests for TaskReaper — zombie task detection and reaping."""
import asyncio
import os
import tempfile
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from nexusagent.infrastructure.db import TaskModel, db_manager
from nexusagent.task_reaper import TaskReaper


@pytest.fixture
async def test_db():
    """Create a temporary database and override the global db_manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        original_url = db_manager.db_url
        db_manager.reinit(db_url=f"sqlite+aiosqlite:///{db_path}")
        await db_manager.init_db()
        yield db_manager
        db_manager.reinit(db_url=original_url)


@pytest.mark.asyncio
async def test_reaper_marks_stale_tasks(test_db):
    """A PROCESSING task with an old updated_at should be reaped to FAILED."""
    # Create a task in PROCESSING with a timestamp far in the past
    old_time = datetime.now(UTC) - timedelta(hours=2)
    async with test_db.get_session() as session:
        task = TaskModel(
            id="stale-task-1",
            description="A stale task",
            priority=1,
            status="processing",
            updated_at=old_time,
        )
        session.add(task)

    # Run reaper with a max_age of 1 hour
    reaper = TaskReaper(max_age_seconds=3600, check_interval=60.0)
    await reaper._reap_once()

    # Verify the task is now FAILED
    async with test_db.get_session() as session:
        result = await session.execute(
            select(TaskModel).where(TaskModel.id == "stale-task-1")
        )
        task = result.scalar_one_or_none()
        assert task is not None
        assert task.status == "failed"


@pytest.mark.asyncio
async def test_reaper_leaves_recent_tasks(test_db):
    """A PROCESSING task with a recent updated_at should NOT be reaped."""
    # Create a task in PROCESSING with a recent timestamp
    recent_time = datetime.now(UTC) - timedelta(minutes=5)
    async with test_db.get_session() as session:
        task = TaskModel(
            id="fresh-task-1",
            description="A fresh task",
            priority=1,
            status="processing",
            updated_at=recent_time,
        )
        session.add(task)

    # Run reaper with a max_age of 1 hour
    reaper = TaskReaper(max_age_seconds=3600, check_interval=60.0)
    await reaper._reap_once()

    # Verify the task is still PROCESSING
    async with test_db.get_session() as session:
        result = await session.execute(
            select(TaskModel).where(TaskModel.id == "fresh-task-1")
        )
        task = result.scalar_one_or_none()
        assert task is not None
        assert task.status == "processing"


@pytest.mark.asyncio
async def test_reaper_leaves_non_processing_tasks(test_db):
    """Tasks not in PROCESSING state should not be reaped even if stale."""
    old_time = datetime.now(UTC) - timedelta(hours=2)
    async with test_db.get_session() as session:
        task = TaskModel(
            id="completed-task-1",
            description="A completed task",
            priority=1,
            status="completed",
            updated_at=old_time,
        )
        session.add(task)

    reaper = TaskReaper(max_age_seconds=3600, check_interval=60.0)
    await reaper._reap_once()

    async with test_db.get_session() as session:
        result = await session.execute(
            select(TaskModel).where(TaskModel.id == "completed-task-1")
        )
        task = result.scalar_one_or_none()
        assert task is not None
        assert task.status == "completed"


@pytest.mark.asyncio
async def test_reaper_stop():
    """Reaper should stop when stop() is called."""
    reaper = TaskReaper(max_age_seconds=3600, check_interval=0.1)
    task = asyncio.create_task(reaper.start())
    await asyncio.sleep(0.05)
    reaper.stop()
    await asyncio.wait_for(task, timeout=2.0)
