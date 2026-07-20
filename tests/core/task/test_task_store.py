# tests/core/task/test_task_store.py
"""Tests for the Task persistence layer."""

from __future__ import annotations

import pytest

from nexusagent.core.task.task_state import Checkpoint, Task, TaskState
from nexusagent.core.task.task_store import TaskStore


class TestTaskStore:
    """TaskStore CRUD operations."""

    @pytest.fixture
    def store(self):
        return TaskStore()

    @pytest.fixture
    def sample_task(self):
        return Task(objective="test task", owner="worker1")

    async def test_save_and_load(self, store, sample_task):
        await store.save_task(sample_task)
        loaded = await store.load_task(sample_task.id)
        assert loaded is not None
        assert loaded.id == sample_task.id
        assert loaded.objective == "test task"

    async def test_load_missing(self, store):
        loaded = await store.load_task("nonexistent")
        assert loaded is None

    async def test_list_all(self, store):
        t1 = Task(objective="a")
        t2 = Task(objective="b")
        await store.save_task(t1)
        await store.save_task(t2)
        tasks = await store.list_tasks()
        assert len(tasks) == 2

    async def test_list_by_state(self, store):
        t1 = Task(objective="running", state=TaskState.EXECUTING)
        t2 = Task(objective="planned", state=TaskState.PLANNING)
        await store.save_task(t1)
        await store.save_task(t2)
        executing = await store.list_tasks(state_filter=TaskState.EXECUTING)
        assert len(executing) == 1
        assert executing[0].objective == "running"

    async def test_save_checkpoint(self, store, sample_task):
        await store.save_task(sample_task)
        cp = Checkpoint(current_node="main", completed_actions=["step1"])
        await store.save_checkpoint(sample_task.id, cp)
        loaded = await store.load_task(sample_task.id)
        assert loaded is not None
        assert len(loaded.checkpoints) == 1

    async def test_save_checkpoint_missing_task(self, store):
        cp = Checkpoint(current_node="main")
        with pytest.raises(KeyError):
            await store.save_checkpoint("nonexistent", cp)

    async def test_load_latest_checkpoint(self, store, sample_task):
        await store.save_task(sample_task)
        cp1 = Checkpoint(current_node="step1")
        cp2 = Checkpoint(current_node="step2")
        await store.save_checkpoint(sample_task.id, cp1)
        await store.save_checkpoint(sample_task.id, cp2)
        latest = await store.load_latest_checkpoint(sample_task.id)
        assert latest is not None
        assert latest.current_node == "step2"

    async def test_load_latest_checkpoint_no_task(self, store):
        latest = await store.load_latest_checkpoint("nonexistent")
        assert latest is None

    async def test_delete_task(self, store, sample_task):
        await store.save_task(sample_task)
        await store.delete_task(sample_task.id)
        loaded = await store.load_task(sample_task.id)
        assert loaded is None

    async def test_update_task(self, store, sample_task):
        await store.save_task(sample_task)
        sample_task.transition_to(TaskState.PLANNING)
        await store.save_task(sample_task)
        loaded = await store.load_task(sample_task.id)
        assert loaded is not None
        assert loaded.state == TaskState.PLANNING
