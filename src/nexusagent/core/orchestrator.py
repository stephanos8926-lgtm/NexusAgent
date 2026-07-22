# src/nexusagent/core/orchestrator.py
"""Phase 5 — Orchestrator for NexusAgent.

Reads task DAGs, dispatches tasks in dependency order, handles event-driven
completion notifications, and integrates with the durable TaskState machine
and EventStore.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nexusagent.core.events import TaskEvent, emit_event_sync
from nexusagent.core.planner import Plan, validate_plan
from nexusagent.core.subagent import SubAgentHandle
from nexusagent.core.task.task_state import Task, TaskState
from nexusagent.core.task.task_store import TaskStore, get_task_store
from nexusagent.core.worker.pool import WorkerPool, get_worker_pool
from nexusagent.llm.models import TaskContract

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrates multi-task execution DAGs based on dependency graphs.

    Coordinates TaskState transitions, spawns sub-agents via WorkerPool,
    monitors completion, and propagates completed events to unblock downstream tasks.
    """

    def __init__(
        self,
        plan: Plan,
        pool: WorkerPool | None = None,
        store: TaskStore | None = None,
    ) -> None:
        """Initialize the Orchestrator with a Plan DAG."""
        self.plan = plan
        self.pool = pool or get_worker_pool()
        self.store = store or get_task_store()
        self.tasks = {t.id: t for t in plan.tasks}

        # Build dependency relations
        # graph[parent_id] = [child_id, ...] (child nodes depending on parent_id)
        self.graph: dict[str, list[str]] = {t.id: [] for t in plan.tasks}
        # parents[child_id] = {parent_id, ...} (set of parents that child_id depends on)
        self.parents: dict[str, set[str]] = {t.id: set() for t in plan.tasks}

        for child, parent in plan.dependencies:
            self.graph[parent].append(child)
            self.parents[child].add(parent)

        self.completed_tasks: set[str] = set()
        self.failed_tasks: set[str] = set()
        self.running_tasks: set[str] = set()
        self.dispatched_tasks: set[str] = set()
        self.task_handles: dict[str, SubAgentHandle] = {}
        self.results: dict[str, Any] = {}
        self.errors: dict[str, str] = {}

        self._loop_event = asyncio.Event()

    async def execute(self) -> dict[str, Any]:
        """Execute the DAG plan to completion.

        Returns:
            A dictionary of results mapped by task ID.
        """
        # Validate the plan DAG first
        validate_plan(self.plan)

        # Initialize all tasks as CREATED in the TaskStore
        for node in self.plan.tasks:
            durable_task = Task(
                id=node.id,
                objective=node.objective,
                owner="orchestrator",
                state=TaskState.CREATED,
            )
            # Link parent task relation if only a single parent dependency exists,
            # or use the first parent in metadata for tracking
            parents = sorted(list(self.parents[node.id]))
            if len(parents) == 1:
                durable_task.parent_task = parents[0]
            elif parents:
                durable_task.parent_task = parents[0]  # Reference first parent

            await self.store.save_task(durable_task)

            # Emit task created event (which persists to EventStore & publishes to NATS)
            event = TaskEvent.created(
                source="orchestrator",
                task_id=node.id,
                objective=node.objective,
                owner="orchestrator",
                parent_task=durable_task.parent_task,
            )
            emit_event_sync(event)

        logger.info(f"Starting DAG execution with {len(self.plan.tasks)} tasks...")

        while len(self.completed_tasks) + len(self.failed_tasks) < len(self.plan.tasks):
            # POL Interruption Check: Query the TaskStore for running tasks to see if they were set to FAILED externally (e.g., by POL)
            for tid in list(self.running_tasks):
                durable_task = await self.store.load_task(tid)
                if durable_task and durable_task.state == TaskState.FAILED:
                    logger.warning(
                        f"[Orchestrator] Task {tid} was set to FAILED externally (e.g. by POL control plane)"
                    )
                    self.failed_tasks.add(tid)
                    self.running_tasks.discard(tid)

            # POL Direct Intervension/Cancellation Check
            from nexusagent.core.pol import get_pol_control_plane

            pol = get_pol_control_plane()
            for intv in pol.list_interventions(status_filter="pending"):
                if intv.get("task_id") in self.running_tasks:
                    if intv.get("action") == "cancel" or (
                        intv.get("priority") == "high"
                        and "cancel" in str(intv.get("reason")).lower()
                    ):
                        logger.warning(
                            f"[Orchestrator] Interrupted by POL intervention {intv['id']}"
                        )
                        await self.cancel_all()
                        raise RuntimeError(f"Orchestration interrupted by POL: {intv['reason']}")

            # Check for any failures. If any task fails, abort/cancel the rest
            if self.failed_tasks:
                await self.cancel_all()
                raise RuntimeError(
                    f"Orchestration aborted due to task failures: {self.failed_tasks}"
                )

            # Clear event BEFORE dispatching so any events set during awaits are preserved
            self._loop_event.clear()

            # Identify ready tasks:
            # - Not yet dispatched
            # - All parent dependencies are completed
            ready_tasks = [
                tid
                for tid in self.tasks
                if tid not in self.dispatched_tasks
                and self.parents[tid].issubset(self.completed_tasks)
            ]

            if not ready_tasks and not self.running_tasks:
                raise RuntimeError(
                    "Orchestration deadlock: no tasks are ready and nothing is running."
                )

            for tid in ready_tasks:
                await self._dispatch_task(tid)

            # Re-check exit condition before waiting
            if len(self.completed_tasks) + len(self.failed_tasks) == len(self.plan.tasks):
                break

            # Wait for any task completion/failure to trigger the next step
            await self._loop_event.wait()

        # Check for any failures one last time
        if self.failed_tasks:
            raise RuntimeError(f"Orchestration failed with tasks: {self.failed_tasks}")

        return self.results

    async def _dispatch_task(self, task_id: str) -> None:
        """Transition task state and spawn worker execution."""
        self.dispatched_tasks.add(task_id)
        self.running_tasks.add(task_id)
        node = self.tasks[task_id]

        # Transition state to PLANNING first
        durable_task = await self.store.load_task(task_id)
        if durable_task:
            durable_task.transition_to(TaskState.PLANNING)
            await self.store.save_task(durable_task)

        # Create the TaskContract configuration
        contract = TaskContract(
            task_id=node.id,
            title=node.objective,
            description=node.objective,
            acceptance_criteria=node.acceptance_criteria,
            metadata=node.metadata,
        )

        # Spawn sub-agent worker
        logger.info(f"Dispatching task {task_id}: {node.objective}")
        handle = await self.pool.spawn(contract)
        self.task_handles[task_id] = handle

        # Transition state to EXECUTING
        if durable_task:
            durable_task.transition_to(TaskState.EXECUTING)
            await self.store.save_task(durable_task)

        # Emit task started event
        emit_event_sync(
            TaskEvent.started(source="orchestrator", task_id=task_id, owner=handle.worker_id)
        )

        # Monitor the spawned task completion asynchronously
        asyncio.create_task(self._monitor_task(task_id, handle))

    async def _monitor_task(self, task_id: str, handle: SubAgentHandle) -> None:
        """Wait for the sub-agent and report back to the Orchestrator."""
        try:
            result = await handle.wait()
            await self.notify_completed(task_id, result)
        except Exception as e:
            await self.notify_failed(task_id, str(e))

    async def notify_completed(self, task_id: str, result: Any) -> None:
        """Process completed task notification (can be triggered externally by events)."""
        if task_id in self.completed_tasks or task_id in self.failed_tasks:
            return

        logger.info(f"Task {task_id} completed successfully.")
        self.completed_tasks.add(task_id)
        self.running_tasks.discard(task_id)
        self.results[task_id] = result

        # Transition task to VERIFYING and then COMPLETED in store
        durable_task = await self.store.load_task(task_id)
        if durable_task:
            if durable_task.state == TaskState.EXECUTING:
                durable_task.transition_to(TaskState.VERIFYING)
                await self.store.save_task(durable_task)
            if durable_task.state == TaskState.VERIFYING:
                durable_task.transition_to(TaskState.COMPLETED)
                await self.store.save_task(durable_task)

        # Emit task completed event
        handle = self.task_handles.get(task_id)
        owner_id = handle.worker_id if handle else "orchestrator"
        emit_event_sync(
            TaskEvent.completed(
                source="orchestrator",
                task_id=task_id,
                owner=owner_id,
                result=result,
            )
        )

        # Trigger downstream task scheduling check
        self._loop_event.set()

    async def notify_failed(self, task_id: str, error: str) -> None:
        """Process failed task notification (can be triggered externally by events)."""
        if task_id in self.completed_tasks or task_id in self.failed_tasks:
            return

        logger.error(f"Task {task_id} failed: {error}")
        self.failed_tasks.add(task_id)
        self.running_tasks.discard(task_id)
        self.errors[task_id] = error

        # Transition task to FAILED in store
        durable_task = await self.store.load_task(task_id)
        if durable_task:
            try:
                durable_task.transition_to(TaskState.FAILED)
                await self.store.save_task(durable_task)
            except Exception:
                durable_task.state = TaskState.FAILED
                await self.store.save_task(durable_task)

        # Emit task failed event
        handle = self.task_handles.get(task_id)
        owner_id = handle.worker_id if handle else "orchestrator"
        emit_event_sync(
            TaskEvent.failed(
                source="orchestrator",
                task_id=task_id,
                owner=owner_id,
                error=error,
            )
        )

        # Trigger downstream task scheduling check
        self._loop_event.set()

    async def cancel_all(self) -> None:
        """Cancel all running task handles."""
        for tid, handle in list(self.task_handles.items()):
            if tid in self.running_tasks:
                try:
                    handle.cancel()
                except Exception as e:
                    logger.warning(f"Failed to cancel task {tid}: {e}")
