import asyncio
import os

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient

from nexusagent.infrastructure.bus import AgentBus, get_bus
from nexusagent.infrastructure.db import db_manager
from nexusagent.llm.models import ResultSchema, TaskStatus
from nexusagent.server.sdk import sdk
from nexusagent.server.server import app

# Test configuration
TEST_DB_PATH = "/tmp/nexus_e2e_test.db"


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_system():
    """
    Initialize the system for E2E testing.
    Overwrites the db path for testing.
    """
    from nexusagent.infrastructure.config import settings

    settings.server.nats_url = "nats://localhost:4222"
    settings.server.db_path = TEST_DB_PATH

    # Clean up stale test DB from previous runs
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    for suffix in ["-shm", "-wal"]:
        p = TEST_DB_PATH + suffix
        if os.path.exists(p):
            os.remove(p)

    # Reinitialize the singleton DB manager with the test path
    db_manager.reinit(TEST_DB_PATH)

    # Initialize DB
    await db_manager.init_db()

    # Connect to NATS
    _bus = get_bus()
    await _bus.connect()

    # Start the worker (normally started by server lifespan, but we need it for SDK tests)
    from nexusagent.core.worker import worker

    worker_task = asyncio.create_task(worker.start())
    # Allow worker to subscribe and be ready to receive messages
    await asyncio.sleep(0.5)

    yield

    # Cleanup
    worker_task.cancel()
    await _bus.close()
    for suffix in ["", "-shm", "-wal"]:
        p = TEST_DB_PATH + suffix
        if os.path.exists(p):
            os.remove(p)


@pytest.mark.asyncio
async def test_sdk_end_to_end_flow():
    """
    Tests the full flow: SDK Submit -> Worker Processing -> SDK Get Status/Result
    """
    # 1. Submit a task via SDK
    task_data = {
        "description": "Verify E2E system connectivity",
        "priority": 1,
        "metadata": {"test": "e2e"},
    }
    task_id = await sdk.submit_task(task_data)
    assert task_id is not None

    # 2. Poll for completion
    # Note: The worker is running in background.
    max_retries = 30
    completed = False
    for _ in range(max_retries):
        status = await sdk.get_task_status(task_id)
        if status == TaskStatus.COMPLETED or status == TaskStatus.FAILED:
            completed = True
            break
        await asyncio.sleep(1)

    assert completed, f"Task {task_id} did not reach terminal state within timeout"

    # 3. Verify Result via SDK
    result = await sdk.get_result(task_id)
    assert result is not None
    assert isinstance(result, ResultSchema)
    assert result.success is True

    # 4. Verify Result in Database
    async with db_manager.get_session() as session:
        from sqlalchemy import select

        from nexusagent.infrastructure.db import ResultModel, TaskModel

        task_res = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
        task = task_res.scalar_one_or_none()
        assert task is not None
        assert task.status == "completed"

        result_res = await session.execute(
            select(ResultModel).where(ResultModel.task_id == task_id)
        )
        db_result = result_res.scalar_one_or_none()
        assert db_result is not None
        assert db_result.success == 1


# API auth header for E2E tests (all non-health endpoints require X-API-Key)
AUTH_HEADERS = {"X-API-Key": "test-key"}


@pytest.mark.asyncio
async def test_api_end_to_end_flow():
    """
    Tests the full flow: API POST /tasks -> API GET /status -> API GET /result
    """
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Submit task via API
        response = await ac.post(
            "/tasks",
            json={"description": "Verify API E2E flow", "priority": 2},
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        task_id = data["task_id"]
        assert "task_id" in data

        # 2. Poll for status
        max_retries = 30
        completed = False
        for _ in range(max_retries):
            status_res = await ac.get(f"/tasks/{task_id}/status", headers=AUTH_HEADERS)
            if status_res.json()["status"] == "completed":
                completed = True
                break
            await asyncio.sleep(1)

        assert completed, f"API Task {task_id} did not complete"

        # 3. Get Result
        result_res = await ac.get(f"/tasks/{task_id}/result", headers=AUTH_HEADERS)
        assert result_res.status_code == 200
        result_data = result_res.json()
        assert result_data["success"] is True


@pytest.mark.asyncio
async def test_invalid_task_failure():
    """
    Tests failure scenarios.
    Since current system is simple, 'invalid' might be something the agent can't handle.
    We can test if an empty description causes an issue or if we can force a failure.
    """
    # Current Worker handles most things, let's see if it handles extreme metadata or similar.
    # Or we can just check if a non-existent task returns 404 via API.
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/tasks/non-existent-id/result", headers=AUTH_HEADERS)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_multiple_concurrent_tasks():
    """
    Submits multiple tasks simultaneously to verify worker reliability.
    """
    tasks_count = 5
    task_ids = []

    # Submit 5 tasks
    for i in range(tasks_count):
        tid = await sdk.submit_task({"description": f"Concurrent task {i}", "priority": 1})
        task_ids.append(tid)

    # Wait for all to complete
    for tid in task_ids:
        max_retries = 40
        done = False
        for _ in range(max_retries):
            status = await sdk.get_task_status(tid)
            if status == TaskStatus.COMPLETED:
                done = True
                break
            await asyncio.sleep(0.5)
        assert done, f"Concurrent task {tid} failed to complete"

    # Verify all results are present
    for tid in task_ids:
        res = await sdk.get_result(tid)
        assert res is not None
        assert res.success is True
