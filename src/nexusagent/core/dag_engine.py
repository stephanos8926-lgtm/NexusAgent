# src/nexusagent/core/dag_engine.py
"""Phase 6 — DAG Execution Engine for NexusAgent.

Transforms validated task plans (DAGs) into executable dependency graphs,
orchestrating parallel execution, state tracking, node retries, and events.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nexusagent.core.dag import DAG, DAGNode, DAGValidationError
from nexusagent.core.events import SystemEvent, emit_event_sync
from nexusagent.core.events.base import EventType
from nexusagent.core.task.recovery import RecoveryManager
from nexusagent.core.task.task_state import StateTransitionValidator, Task, TaskState
from nexusagent.core.task.task_store import TaskStore, get_task_store
from nexusagent.core.worker.pool import WorkerPool, get_worker_pool
from nexusagent.llm.models import TaskContract

logger = logging.getLogger(__name__)


class DAGEngineEvent(SystemEvent):
    """Event class for DAG and node execution lifecycle transitions."""

    category = EventType.TASK


class DAGEngine:
    """DAG Execution Engine.

    Coordinates execution of task DAGs, managing dependencies,
    concurrency, events, and failure recovery.
    """

    def __init__(
        self,
        pool: WorkerPool | None = None,
        store: TaskStore | None = None,
    ) -> None:
        self.pool = pool or get_worker_pool()
        self.store = store or get_task_store()
        self._loop_event = asyncio.Event()

    def _emit_dag_event(self, event_type: str, source: str, payload: dict[str, Any]) -> None:
        """Emit a DAG event synchronously via the EventEmitter."""
        try:
            event = DAGEngineEvent(
                source=source,
                type=event_type,
                payload=payload,
            )
            emit_event_sync(event)
        except Exception as e:
            logger.warning(f"Failed to emit DAG event '{event_type}': {e}")

    async def execute(self, dag: DAG) -> dict[str, Any]:
        """Execute a validated DAG plan to completion.

        Enforces topological execution order, supports concurrent execution
        of independent tasks, and manages failures/retries.

        Returns:
            A dictionary containing execution results mapped by node_id.
        """
        # Step 1: Create and validate the graph
        self._emit_dag_event(
            "graph.created", "dag_engine", {"graph_id": dag.graph_id, "nodes_count": len(dag.nodes)}
        )

        try:
            dag.validate_graph()
            self._emit_dag_event("graph.validated", "dag_engine", {"graph_id": dag.graph_id})
        except DAGValidationError as exc:
            self._emit_dag_event(
                "graph.failed", "dag_engine", {"graph_id": dag.graph_id, "error": str(exc)}
            )
            raise

        # Step 2: Initialize Graph State
        self._emit_dag_event("graph.started", "dag_engine", {"graph_id": dag.graph_id})

        # Pre-populate all nodes in the TaskStore as CREATED
        for node in dag.nodes:
            durable_task = Task(
                id=node.node_id,
                objective=node.objective,
                owner="dag_engine",
                state=TaskState.CREATED,
            )
            await self.store.save_task(durable_task)

        # Build dependency mapping
        # parents[node_id] = {dep_node_id, ...}
        # children[node_id] = [child_node_id, ...]
        parents: dict[str, set[str]] = {n.node_id: set() for n in dag.nodes}
        children: dict[str, list[str]] = {n.node_id: [] for n in dag.nodes}

        for node in dag.nodes:
            for dep in node.dependencies:
                parents[node.node_id].add(dep)
                children[dep].append(node.node_id)

        for edge in dag.edges:
            parents[edge.to_node_id].add(edge.from_node_id)
            children[edge.from_node_id].append(edge.to_node_id)

        # Queue tracking
        completed_nodes: set[str] = set()
        failed_nodes: set[str] = set()
        running_nodes: set[str] = set()
        dispatched_nodes: set[str] = set()
        retry_counts: dict[str, int] = {n.node_id: 0 for n in dag.nodes}

        results: dict[str, Any] = {}
        errors: dict[str, str] = {}
        handles: dict[str, Any] = {}

        node_map = {n.node_id: n for n in dag.nodes}

        logger.info(f"Starting execution of DAG '{dag.graph_id}' with {len(dag.nodes)} nodes...")

        # Step 3: Main Scheduler Loop
        while len(completed_nodes) + len(failed_nodes) < len(dag.nodes):
            # POL Interruption Check: Query the TaskStore for running nodes to see if they were set to FAILED externally (e.g., by POL)
            for nid in list(running_nodes):
                durable_task = await self.store.load_task(nid)
                if durable_task and durable_task.state == TaskState.FAILED:
                    logger.warning(
                        f"[DAGEngine] Node {nid} was set to FAILED externally (e.g. by POL control plane)"
                    )
                    failed_nodes.add(nid)
                    running_nodes.discard(nid)
                    errors[nid] = "Cancelled/Failed by external POL control plane signal"

            # POL Direct Intervension/Cancellation Check
            from nexusagent.core.pol import get_pol_control_plane

            pol = get_pol_control_plane()
            for intv in pol.list_interventions(status_filter="pending"):
                if intv.get("task_id") in running_nodes:
                    if intv.get("action") == "cancel" or (
                        intv.get("priority") == "high"
                        and "cancel" in str(intv.get("reason")).lower()
                    ):
                        logger.warning(f"[DAGEngine] Interrupted by POL intervention {intv['id']}")
                        for rnid, rhandle in list(handles.items()):
                            if rnid in running_nodes:
                                try:
                                    rhandle.cancel()
                                except Exception as re:
                                    logger.warning(f"Failed to cancel running node '{rnid}': {re}")
                        raise RuntimeError(f"DAG execution interrupted by POL: {intv['reason']}")

            if failed_nodes:
                # Cancel all remaining running handles
                for nid, handle in list(handles.items()):
                    if nid in running_nodes:
                        try:
                            handle.cancel()
                        except Exception as e:
                            logger.warning(f"Failed to cancel running node '{nid}': {e}")

                self._emit_dag_event(
                    "graph.failed",
                    "dag_engine",
                    {
                        "graph_id": dag.graph_id,
                        "error": f"Graph failed due to node failures: {failed_nodes}",
                    },
                )
                raise RuntimeError(
                    f"DAG execution aborted due to failures: {failed_nodes}. Errors: {errors}"
                )

            self._loop_event.clear()

            # Find ready nodes: not yet dispatched and all parent dependencies are completed
            ready_nodes = [
                nid
                for nid in node_map
                if nid not in dispatched_nodes and parents[nid].issubset(completed_nodes)
            ]

            # Emit execution blocked for pending nodes that are waiting
            for nid in node_map:
                if nid not in dispatched_nodes and nid not in ready_nodes:
                    waiting_on = parents[nid] - completed_nodes
                    self._emit_dag_event(
                        "execution.blocked",
                        "dag_engine",
                        {
                            "node_id": nid,
                            "graph_id": dag.graph_id,
                            "reason": f"Waiting on dependencies: {waiting_on}",
                        },
                    )

            if not ready_nodes and not running_nodes:
                self._emit_dag_event(
                    "graph.failed",
                    "dag_engine",
                    {
                        "graph_id": dag.graph_id,
                        "error": "Deadlock detected - no ready nodes and nothing running",
                    },
                )
                raise RuntimeError("DAG deadlock: no tasks are ready and nothing is running.")

            # Dispatch ready nodes concurrently
            for nid in ready_nodes:
                dispatched_nodes.add(nid)
                running_nodes.add(nid)
                node = node_map[nid]

                # Emit ready event
                self._emit_dag_event(
                    "node.ready", "dag_engine", {"node_id": nid, "graph_id": dag.graph_id}
                )

                # Emit worker assignment requested
                self._emit_dag_event(
                    "worker.assignment.requested",
                    "dag_engine",
                    {"node_id": nid, "graph_id": dag.graph_id},
                )

                # Transition TaskState to PLANNING in TaskStore
                durable_task = await self.store.load_task(nid)
                if durable_task:
                    if StateTransitionValidator.is_valid_transition(
                        durable_task.state, TaskState.PLANNING
                    ):
                        durable_task.transition_to(TaskState.PLANNING)
                        await self.store.save_task(durable_task)

                # Create TaskContract for WorkerPool
                contract = TaskContract(
                    task_id=node.node_id,
                    title=node.objective,
                    description=node.objective,
                    priority=node.priority,
                    max_wall_time=node.timeout,
                    acceptance_criteria=node.verification_requirements or [],
                    metadata={
                        "graph_id": dag.graph_id,
                        **(node.payload or {}),
                    },
                )

                logger.info(f"Dispatching node '{nid}': {node.objective}")

                # Spawn worker
                handle = await self.pool.spawn(contract)
                handles[nid] = handle

                # Emit worker assignment completed
                self._emit_dag_event(
                    "worker.assignment.completed",
                    "dag_engine",
                    {"node_id": nid, "graph_id": dag.graph_id, "worker_id": handle.worker_id},
                )

                # Emit node started
                self._emit_dag_event(
                    "node.started",
                    "dag_engine",
                    {"node_id": nid, "graph_id": dag.graph_id, "worker_id": handle.worker_id},
                )

                # Transition state to EXECUTING in TaskStore
                if durable_task:
                    if StateTransitionValidator.is_valid_transition(
                        durable_task.state, TaskState.EXECUTING
                    ):
                        durable_task.transition_to(TaskState.EXECUTING)
                        await self.store.save_task(durable_task)

                # Run monitoring in the background
                asyncio.create_task(
                    self._monitor_node(
                        node,
                        handle,
                        dag.graph_id,
                        retry_counts,
                        dispatched_nodes,
                        running_nodes,
                        completed_nodes,
                        failed_nodes,
                        results,
                        errors,
                    )
                )

            # Wait for any status change event to loop and check next dependencies
            if len(completed_nodes) + len(failed_nodes) < len(dag.nodes):
                await self._loop_event.wait()

        # Check final graph outcome
        if failed_nodes:
            self._emit_dag_event(
                "graph.failed",
                "dag_engine",
                {"graph_id": dag.graph_id, "error": f"Failed nodes: {failed_nodes}"},
            )
            raise RuntimeError(f"DAG execution failed on nodes: {failed_nodes}")

        self._emit_dag_event(
            "graph.completed", "dag_engine", {"graph_id": dag.graph_id, "results": results}
        )
        return results

    async def _monitor_node(
        self,
        node: DAGNode,
        handle: Any,
        graph_id: str,
        retry_counts: dict[str, int],
        dispatched_nodes: set[str],
        running_nodes: set[str],
        completed_nodes: set[str],
        failed_nodes: set[str],
        results: dict[str, Any],
        errors: dict[str, str],
    ) -> None:
        """Asynchronously monitor node execution, managing retries and recovery."""
        nid = node.node_id
        try:
            result = await handle.wait()

            # Transition task in TaskStore to VERIFYING and then COMPLETED
            durable_task = await self.store.load_task(nid)
            if durable_task:
                if StateTransitionValidator.is_valid_transition(
                    durable_task.state, TaskState.VERIFYING
                ):
                    durable_task.transition_to(TaskState.VERIFYING)
                    await self.store.save_task(durable_task)
                if StateTransitionValidator.is_valid_transition(
                    durable_task.state, TaskState.COMPLETED
                ):
                    durable_task.transition_to(TaskState.COMPLETED)
                    await self.store.save_task(durable_task)

            # Node completed successfully
            results[nid] = result
            completed_nodes.add(nid)
            running_nodes.discard(nid)

            self._emit_dag_event(
                "node.completed",
                "dag_engine",
                {"node_id": nid, "graph_id": graph_id, "result": result},
            )

        except Exception as exc:
            # Check if we should retry
            retries_used = retry_counts[nid]
            if retries_used < node.retries:
                retry_counts[nid] += 1
                logger.warning(
                    f"Node '{nid}' failed with error: {exc}. Retrying ({retry_counts[nid]}/{node.retries})..."
                )

                # Update TaskStore to FAILED and RECOVERING
                durable_task = await self.store.load_task(nid)
                if durable_task:
                    try:
                        durable_task.transition_to(TaskState.FAILED)
                        await self.store.save_task(durable_task)
                    except ValueError:
                        durable_task.state = TaskState.FAILED
                        await self.store.save_task(durable_task)

                # Initialize RecoveryManager to decide rollback / backoff delay
                recovery_mgr = RecoveryManager(
                    max_retries=node.retries,
                    base_delay=1.0,
                )
                if durable_task:
                    await recovery_mgr.attempt_recovery(durable_task)

                self._emit_dag_event(
                    "node.recovered",
                    "dag_engine",
                    {"node_id": nid, "graph_id": graph_id, "retry_count": retry_counts[nid]},
                )

                # Reset to ready for retry by clearing dispatched status
                dispatched_nodes.discard(nid)
                running_nodes.discard(nid)
            else:
                # Permanent failure, escalate
                logger.error(f"Node '{nid}' permanently failed after {retries_used} retries: {exc}")
                errors[nid] = str(exc)
                failed_nodes.add(nid)
                running_nodes.discard(nid)

                # Update TaskStore to FAILED
                durable_task = await self.store.load_task(nid)
                if durable_task:
                    try:
                        durable_task.transition_to(TaskState.FAILED)
                        await self.store.save_task(durable_task)
                    except ValueError:
                        durable_task.state = TaskState.FAILED
                        await self.store.save_task(durable_task)

                self._emit_dag_event(
                    "node.failed",
                    "dag_engine",
                    {"node_id": nid, "graph_id": graph_id, "error": str(exc), "escalated": True},
                )

        # Notify scheduler loop
        self._loop_event.set()
