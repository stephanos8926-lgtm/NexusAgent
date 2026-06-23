"""WorkerPool — manages a pool of isolated worker executions.

Provides concurrency-limited spawning of sub-agent workers with turn counting,
wall-time bounds, and cancellation support.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from nexusagent.core.subagent import SubAgentHandle
from nexusagent.core.worker.handler import _run_agent_task
from nexusagent.llm.models import TaskSchema

logger = logging.getLogger(__name__)


class WorkerPool:
    """Manages a pool of isolated worker executions."""

    def __init__(self, max_workers: int = 4):
        """Initialize the worker pool with a concurrency limit.

        Args:
            max_workers: Maximum number of concurrent worker executions.
        """
        self.max_workers = max_workers
        self._active: dict[str, SubAgentHandle] = {}
        self._tasks: set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(max_workers)

    async def spawn(self, contract, depth: int = 0) -> SubAgentHandle:
        """Spawn an isolated worker. Returns a handle to monitor/control it.

        Args:
            contract: Task configuration including model, max_depth, summary_only.
            depth: Current nesting depth (0 = top-level). Children get depth+1.
        """
        if depth >= contract.max_depth:
            raise RuntimeError(
                f"Max sub-agent depth ({contract.max_depth}) reached. "
                f"Cannot spawn worker for task: {contract.task_id}"
            )
        worker_id = f"worker-{str(uuid.uuid4())[:8]}"
        handle = SubAgentHandle(worker_id=worker_id, contract=contract, depth=depth)
        self._active[worker_id] = handle
        task = asyncio.create_task(self._run_worker(handle))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return handle

    async def _run_worker(self, handle: SubAgentHandle):
        """Run a worker to completion within its contract bounds."""
        async with self._semaphore:
            handle._mark_running()
            try:
                meta = dict(handle.contract.metadata)
                meta.setdefault("agent_model", handle.model)
                meta.setdefault("agent_provider", handle.provider)
                # Pass working_dir and system_prompt from contract to task metadata
                if handle.contract.working_dir and handle.contract.working_dir != ".":
                    meta["working_dir"] = handle.contract.working_dir
                if handle.contract.system_prompt:
                    meta["system_prompt"] = handle.contract.system_prompt
                task = TaskSchema(
                    id=handle.contract.task_id,
                    description=handle.contract.description,
                    priority=handle.contract.priority,
                    metadata=meta,
                )
                result = await self._execute_bounded(task, handle)
                if handle.is_cancelled():
                    handle._mark_failed("Cancelled by user")
                else:
                    handle._mark_completed(result)
            except Exception as e:
                handle._mark_failed(str(e))
            finally:
                self._active.pop(handle.worker_id, None)

    async def _execute_bounded(self, task, handle) -> str:
        """Execute with turn counting, wall time, and cancellation checks."""
        start = time.time()
        turn = 0
        last_result = None
        contract = handle.contract

        while turn < contract.max_turns:
            if handle.is_cancelled():
                return "Cancelled"
            elapsed = time.time() - start
            if elapsed >= contract.max_wall_time:
                return f"Timed out after {elapsed:.1f}s"
            try:
                turn_task = TaskSchema(
                    id=task.id,
                    description=task.description,
                    priority=task.priority,
                    metadata={
                        **task.metadata,
                        "turn": turn,
                        "max_turns": contract.max_turns,
                        "acceptance_criteria": contract.acceptance_criteria,
                        "last_result": last_result,
                    },
                )
                result = await _run_agent_task(turn_task)
                last_result = result
                if result.get("success") is True or result.get("status") == "complete":
                    return last_result
            except Exception as e:
                if contract.on_failure == "abort":
                    return f"Aborted: {e}"
                elif contract.on_failure == "retry":
                    continue
                return f"Escalated: {e}"
            turn += 1
        return f"Max turns reached. Last: {last_result}"

    def list_active(self) -> list[SubAgentHandle]:
        """Return a snapshot of all currently active sub-agent handles."""
        return list(self._active.values())


# Module-level singleton (lazy, injectable)
_worker_pool_instance: WorkerPool | None = None


def get_worker_pool() -> WorkerPool:
    """Get or create the module-level WorkerPool singleton."""
    global _worker_pool_instance
    if _worker_pool_instance is None:
        _worker_pool_instance = WorkerPool()
    return _worker_pool_instance


def set_worker_pool(instance: WorkerPool) -> None:
    """Override the module-level WorkerPool singleton (for testing/dependency injection)."""
    global _worker_pool_instance
    _worker_pool_instance = instance


# Backward-compatible alias — deprecated, use get_worker_pool()
worker_pool = get_worker_pool()
