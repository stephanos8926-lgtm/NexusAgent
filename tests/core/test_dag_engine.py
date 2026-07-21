# tests/core/test_dag_engine.py
"""Unit and integration tests for the Phase 6 DAG Execution Engine system."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nexusagent.core.dag import DAG, DAGNode
from nexusagent.core.dag_engine import DAGEngine
from nexusagent.core.subagent import SubAgentHandle, SubAgentStatus
from nexusagent.core.task.task_state import TaskState
from nexusagent.core.task.task_store import TaskStore
from nexusagent.core.worker.pool import WorkerPool
from nexusagent.llm.models import TaskContract


class MockSubAgentHandle(SubAgentHandle):
    """A simulated handle for testing worker executions in DAG Engine."""

    def __init__(
        self,
        worker_id: str,
        contract: TaskContract,
        completion_delay: float = 0.02,
        result: str | Exception = "success",
    ) -> None:
        super().__init__(worker_id, contract)
        self.completion_delay = completion_delay
        self._mock_result = result

    async def wait(self, timeout: float | None = None) -> Any:
        await asyncio.sleep(self.completion_delay)
        if self._status == SubAgentStatus.CANCELLED:
            raise asyncio.CancelledError("Cancelled")
        if isinstance(self._mock_result, Exception):
            self._mark_failed(str(self._mock_result))
            raise self._mock_result
        self._mark_completed(self._mock_result)
        return self.result


@pytest.fixture
def sample_dag() -> DAG:
    """A sample DAG with 4 nodes:
    n1 (no parents) -> n2 & n3 (depend on n1) -> n4 (depends on n2 & n3).
    """
    n1 = DAGNode(node_id="n1", objective="Step 1: Init")
    n2 = DAGNode(node_id="n2", objective="Step 2: Sub A", dependencies=["n1"])
    n3 = DAGNode(node_id="n3", objective="Step 3: Sub B", dependencies=["n1"])
    n4 = DAGNode(node_id="n4", objective="Step 4: Combine", dependencies=["n2", "n3"])

    return DAG(
        graph_id="g-sample-1",
        nodes=[n1, n2, n3, n4],
    )


@pytest.mark.asyncio
async def test_dag_engine_execution_order_and_concurrency(sample_dag: DAG) -> None:
    """Verify that DAGEngine executes nodes in strict dependency order and concurrently when independent."""
    store = TaskStore()
    pool = MagicMock(spec=WorkerPool)

    execution_order = []
    current_running = 0
    max_running = 0
    lock = asyncio.Lock()

    async def mock_spawn(contract: TaskContract, depth: int = 0) -> SubAgentHandle:
        nonlocal current_running, max_running
        async with lock:
            execution_order.append(contract.task_id)
            current_running += 1
            max_running = max(max_running, current_running)

        # Completion delay to allow concurrent branches to overlap
        handle = MockSubAgentHandle(
            worker_id=f"worker-{contract.task_id}",
            contract=contract,
            completion_delay=0.03,
            result=f"Result of {contract.task_id}",
        )
        handle._mark_running()

        original_wait = handle.wait

        # Release running count after execution completes
        async def wrap_wait(timeout=None):
            nonlocal current_running
            try:
                res = await original_wait(timeout)
                return res
            finally:
                async with lock:
                    current_running -= 1

        # Patch handle's wait to decrease count when finished without infinite recursion
        handle.wait = wrap_wait
        return handle

    pool.spawn = mock_spawn

    engine = DAGEngine(pool=pool, store=store)

    results = await engine.execute(sample_dag)

    # 1. Assert execution order
    assert execution_order[0] == "n1"
    assert set(execution_order[1:3]) == {"n2", "n3"}
    assert execution_order[3] == "n4"

    # 2. Assert concurrent sibling branch execution
    # n2 and n3 should run concurrently, so max_running should be at least 2
    assert max_running >= 2

    # 3. Assert results are captured
    assert results["n1"] == "Result of n1"
    assert results["n2"] == "Result of n2"
    assert results["n3"] == "Result of n3"
    assert results["n4"] == "Result of n4"

    # 4. Assert durable states in TaskStore are COMPLETED
    for node in sample_dag.nodes:
        durable_task = await store.load_task(node.node_id)
        assert durable_task is not None
        assert durable_task.state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_dag_engine_node_failure_recovery_retry(sample_dag: DAG) -> None:
    """Verify node partial-failure retry recovery handling."""
    store = TaskStore()
    pool = MagicMock(spec=WorkerPool)

    failures: dict[str, int] = {"n1": 1}  # n1 fails once, then succeeds

    async def mock_spawn(contract: TaskContract, depth: int = 0) -> SubAgentHandle:
        nid = contract.task_id
        if failures.get(nid, 0) > 0:
            failures[nid] -= 1
            res = RuntimeError("Transient Error")
        else:
            res = f"Success {nid}"

        handle = MockSubAgentHandle(
            worker_id=f"worker-{nid}",
            contract=contract,
            completion_delay=0.01,
            result=res,
        )
        handle._mark_running()
        return handle

    pool.spawn = mock_spawn

    # Set n1 with retries=1
    sample_dag.nodes[0].retries = 1

    engine = DAGEngine(pool=pool, store=store)
    results = await engine.execute(sample_dag)

    # All nodes must eventually complete successfully
    assert results["n1"] == "Success n1"
    assert results["n4"] == "Success n4"

    n1_task = await store.load_task("n1")
    assert n1_task is not None
    assert n1_task.state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_dag_engine_unrecoverable_failure_escalation(sample_dag: DAG) -> None:
    """Verify permanent failure halts graph and escalates."""
    store = TaskStore()
    pool = MagicMock(spec=WorkerPool)

    async def mock_spawn(contract: TaskContract, depth: int = 0) -> SubAgentHandle:
        # n1 fails permanently
        res = RuntimeError("Fatal Error") if contract.task_id == "n1" else "Success"
        handle = MockSubAgentHandle(
            worker_id=f"worker-{contract.task_id}",
            contract=contract,
            completion_delay=0.01,
            result=res,
        )
        handle._mark_running()
        return handle

    pool.spawn = mock_spawn

    # n1 has retries=0
    sample_dag.nodes[0].retries = 0

    engine = DAGEngine(pool=pool, store=store)

    with pytest.raises(RuntimeError, match=r"DAG execution aborted due to failures: \{'n1'\}"):
        await engine.execute(sample_dag)

    # Verify n1 state is FAILED in TaskStore
    n1_task = await store.load_task("n1")
    assert n1_task is not None
    assert n1_task.state == TaskState.FAILED


@pytest.mark.asyncio
async def test_dag_engine_event_emission(sample_dag: DAG) -> None:
    """Verify that all graph and node state-transition events are emitted."""
    store = TaskStore()
    pool = MagicMock(spec=WorkerPool)

    async def mock_spawn(contract: TaskContract, depth: int = 0) -> SubAgentHandle:
        handle = MockSubAgentHandle(
            worker_id=f"worker-{contract.task_id}",
            contract=contract,
            completion_delay=0.005,
            result="Success",
        )
        handle._mark_running()
        return handle

    pool.spawn = mock_spawn

    engine = DAGEngine(pool=pool, store=store)

    emitted_events = []

    def mock_emit(event: Any) -> None:
        emitted_events.append(event)

    with patch("nexusagent.core.dag_engine.emit_event_sync", side_effect=mock_emit):
        await engine.execute(sample_dag)

    # Get event types in order
    event_types = [e.type for e in emitted_events]

    # Verify key lifecycle events are emitted
    assert "graph.created" in event_types
    assert "graph.validated" in event_types
    assert "graph.started" in event_types
    assert "node.ready" in event_types
    assert "node.started" in event_types
    assert "node.completed" in event_types
    assert "graph.completed" in event_types

    # Ensure n1 completed before n2 ready
    n1_completed_idx = event_types.index("node.completed")
    n2_ready_idx = event_types.index("node.ready", n1_completed_idx)
    assert n1_completed_idx < n2_ready_idx
