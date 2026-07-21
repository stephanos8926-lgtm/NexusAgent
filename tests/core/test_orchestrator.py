# tests/core/test_orchestrator.py
"""Unit and integration tests for the Phase 5 Orchestrator system."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from nexusagent.core.orchestrator import Orchestrator
from nexusagent.core.planner import Plan, TaskNode
from nexusagent.core.subagent import SubAgentHandle, SubAgentStatus
from nexusagent.core.task.task_state import TaskState
from nexusagent.core.task.task_store import TaskStore
from nexusagent.core.worker.pool import WorkerPool
from nexusagent.llm.models import TaskContract


class MockSubAgentHandle(SubAgentHandle):
    """A simulated handle for testing worker executions."""

    def __init__(
        self,
        worker_id: str,
        contract: TaskContract,
        completion_delay: float = 0.05,
        result: str = "success",
    ) -> None:
        super().__init__(worker_id, contract)
        self.completion_delay = completion_delay
        self._mock_result = result

    async def wait(self, timeout: float | None = None) -> Any:
        await asyncio.sleep(self.completion_delay)
        if self._status == SubAgentStatus.CANCELLED:
            raise asyncio.CancelledError("Cancelled")
        if self._mock_result == "fail":
            self._mark_failed("Simulated failure")
            raise RuntimeError("Simulated failure")
        self._mark_completed(self._mock_result)
        return self.result


@pytest.fixture
def sample_plan() -> Plan:
    """A sample DAG plan with 4 nodes:

    t1 (no parent) -> t2 & t3 (depend on t1) -> t4 (depends on t2 & t3).
    """
    t1 = TaskNode(id="t1", objective="Initialize Project Structure")
    t2 = TaskNode(id="t2", objective="Build prime calculation math engine")
    t3 = TaskNode(id="t3", objective="Create CLI interactive prompt")
    t4 = TaskNode(id="t4", objective="Verify whole application")

    return Plan(
        goal="Build Prime Calculator app",
        tasks=[t1, t2, t3, t4],
        dependencies=[
            ("t2", "t1"),
            ("t3", "t1"),
            ("t4", "t2"),
            ("t4", "t3"),
        ],
    )


@pytest.mark.asyncio
async def test_orchestrator_initialization_and_dag_execution_order(sample_plan: Plan) -> None:
    """Verify that Orchestrator dispatches tasks in strict dependency order."""
    store = TaskStore()
    pool = MagicMock(spec=WorkerPool)

    execution_order = []

    async def mock_spawn(contract: TaskContract, depth: int = 0) -> SubAgentHandle:
        # Record dispatch order
        execution_order.append(contract.task_id)
        # Create a mock handle
        handle = MockSubAgentHandle(
            worker_id=f"worker-{contract.task_id}",
            contract=contract,
            completion_delay=0.02,
            result=f"Result of {contract.task_id}",
        )
        handle._mark_running()
        return handle

    pool.spawn = mock_spawn

    orchestrator = Orchestrator(plan=sample_plan, pool=pool, store=store)

    # Execute the plan
    results = await orchestrator.execute()

    # 1. Verify t1 starts first, before t2 or t3, and t4 starts last
    assert execution_order[0] == "t1"
    assert set(execution_order[1:3]) == {"t2", "t3"}
    assert execution_order[3] == "t4"

    # 2. Verify all results are captured
    assert results["t1"] == "Result of t1"
    assert results["t2"] == "Result of t2"
    assert results["t3"] == "Result of t3"
    assert results["t4"] == "Result of t4"

    # 3. Verify final states of all tasks in store are COMPLETED
    for node in sample_plan.tasks:
        durable_task = await store.load_task(node.id)
        assert durable_task is not None
        assert durable_task.state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_orchestrator_failure_aborts_downstream(sample_plan: Plan) -> None:
    """Verify that a task failure cancels active tasks and aborts orchestration."""
    store = TaskStore()
    pool = MagicMock(spec=WorkerPool)

    async def mock_spawn(contract: TaskContract, depth: int = 0) -> SubAgentHandle:
        # Fail t1
        res = "fail" if contract.task_id == "t1" else "success"
        handle = MockSubAgentHandle(
            worker_id=f"worker-{contract.task_id}",
            contract=contract,
            completion_delay=0.01,
            result=res,
        )
        handle._mark_running()
        return handle

    pool.spawn = mock_spawn

    orchestrator = Orchestrator(plan=sample_plan, pool=pool, store=store)

    # Expect RuntimeError on failure propagation
    with pytest.raises(RuntimeError, match="Orchestration aborted due to task failures"):
        await orchestrator.execute()

    # Verify t1 is FAILED in store
    t1_task = await store.load_task("t1")
    assert t1_task is not None
    assert t1_task.state == TaskState.FAILED


@pytest.mark.asyncio
async def test_event_driven_external_notification(sample_plan: Plan) -> None:
    """Verify orchestrator triggers next steps immediately when notify_completed is called."""
    store = TaskStore()
    pool = MagicMock(spec=WorkerPool)

    # Use a dummy spawn that returns a PENDING handle which won't complete on its own
    async def mock_spawn(contract: TaskContract, depth: int = 0) -> SubAgentHandle:
        handle = MockSubAgentHandle(
            worker_id=f"worker-{contract.task_id}",
            contract=contract,
            completion_delay=10.0,  # very long delay
            result="success",
        )
        handle._mark_running()
        return handle

    pool.spawn = mock_spawn

    orchestrator = Orchestrator(plan=sample_plan, pool=pool, store=store)

    # Start execution as a background task
    exec_task = asyncio.create_task(orchestrator.execute())

    # Give it a tiny moment to initialize and spawn t1
    await asyncio.sleep(0.01)

    assert "t1" in orchestrator.dispatched_tasks
    assert "t2" not in orchestrator.dispatched_tasks

    # Externally notify orchestrator of t1 completion
    await orchestrator.notify_completed("t1", "Manual T1 success")

    # Give it a moment to dispatch t2 and t3
    await asyncio.sleep(0.01)
    assert "t2" in orchestrator.dispatched_tasks
    assert "t3" in orchestrator.dispatched_tasks
    assert "t4" not in orchestrator.dispatched_tasks

    # Notify t2 and t3 completion
    await orchestrator.notify_completed("t2", "Manual T2 success")
    await orchestrator.notify_completed("t3", "Manual T3 success")

    # Give it a moment to dispatch t4
    await asyncio.sleep(0.01)
    assert "t4" in orchestrator.dispatched_tasks

    # Notify t4 completion
    await orchestrator.notify_completed("t4", "Manual T4 success")

    # The background execution should finish and return
    results = await exec_task
    assert results["t1"] == "Manual T1 success"
    assert results["t4"] == "Manual T4 success"
