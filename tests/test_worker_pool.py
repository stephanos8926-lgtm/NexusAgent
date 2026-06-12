"""Tests for WorkerPool spawning and lifecycle."""

import asyncio
from unittest.mock import patch

import pytest

from nexusagent.llm.models import TaskContract
from nexusagent.core.subagent import SubAgentStatus
from nexusagent.core.worker import WorkerPool


@pytest.fixture
def contract() -> TaskContract:
    """A minimal TaskContract for testing."""
    return TaskContract(
        task_id="test-task-1",
        title="Test task",
        description="A test task",
        max_turns=1,
        max_wall_time=10.0,
    )


def test_pool_creation():
    pool = WorkerPool(max_workers=2)
    assert pool.max_workers == 2


async def test_spawn_returns_handle(contract):
    pool = WorkerPool(max_workers=2)

    async def _fake_execute_bounded(self, task, handle):
        return "fake result"

    # Patch _execute_bounded to skip real agent logic.
    # Patch the module-level asyncio.sleep reference used in _run_worker's finally.
    original_sleep = asyncio.sleep

    async def _short_sleep(delay):
        if delay > 1:
            await original_sleep(0)
        else:
            await original_sleep(delay)

    with (
        patch.object(WorkerPool, "_execute_bounded", _fake_execute_bounded),
        patch("nexusagent.core.worker.asyncio.sleep", _short_sleep),
    ):
        handle = await pool.spawn(contract)
        assert handle.worker_id.startswith("worker-")
        assert handle.status in {SubAgentStatus.PENDING, SubAgentStatus.RUNNING}
        # Yield control so the spawned task can run to completion
        for _ in range(20):
            await original_sleep(0.01)
        assert handle.status == SubAgentStatus.COMPLETED


async def test_spawn_and_cancel(contract):
    pool = WorkerPool(max_workers=2)

    async def _long_execute_bounded(self, task, handle):
        # Simulate a long-running task so cancel can fire mid-execution
        await asyncio.sleep(10)
        return "should not reach"

    original_sleep = asyncio.sleep

    async def _short_sleep(delay):
        if delay > 1:
            await original_sleep(0)
        else:
            await original_sleep(delay)

    with (
        patch.object(WorkerPool, "_execute_bounded", _long_execute_bounded),
        patch("nexusagent.core.worker.asyncio.sleep", _short_sleep),
    ):
        handle = await pool.spawn(contract)
        handle.cancel()
        assert handle.status == SubAgentStatus.CANCELLED
