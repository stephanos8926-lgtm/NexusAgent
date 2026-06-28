# src/nexusagent/sdk.py
"""NexusSDK — high-level client for submitting tasks and retrieving results.

Provides a unified API over NATS JetStream for task submission, result
retrieval, and health monitoring. Used by both the FastAPI server and
external clients.
"""

import asyncio
import logging
import uuid

from nexusagent.infrastructure.bus import AgentBus, get_bus
from nexusagent.llm.models import ResultSchema, TaskSchema, TaskStatus
from nexusagent.version import MIN_CLIENT_VERSION, VERSION

logger = logging.getLogger(__name__)

# Version constants — single source of truth is nexusagent.version
SERVER_VERSION = VERSION


class NexusSDK:
    """High-level SDK for interacting with the NexusAgent system.
    This can be used by both the FastAPI server and external clients.

    Usage:
        # One-off calls (auto-connects)
        sdk = NexusSDK()
        task_id = await sdk.submit_task({"description": "hello"})
        result = await sdk.get_result(task_id)

        # Context manager (explicit connect/disconnect)
        async with NexusSDK() as sdk:
            task_id = await sdk.submit_task({"description": "hello"})
            result = await sdk.wait_for_result(task_id, timeout=60)

        # Batch submit
        ids = await sdk.submit_batch([
            {"description": "task 1"},
            {"description": "task 2"},
        ])
    """

    def __init__(self, bus: AgentBus | None = None):
        """Initialize the SDK with an optional NATS bus instance.

        Args:
            bus: An existing ``AgentBus`` to reuse. If None, uses the
                global default bus via ``get_bus()``.
        """
        self.bus = bus or get_bus()

    async def connect(self):
        """Ensure NATS connection is established."""
        if not self.bus.nc:
            await self.bus.connect()

    async def disconnect(self) -> None:
        """Close the NATS connection."""
        if self.bus and self.bus.nc:
            await self.bus.close()

    async def __aenter__(self) -> "NexusSDK":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.disconnect()

    # ─── Core Operations ─────────────────────────────────────────────────

    async def submit_task(self, task_data: dict) -> str:
        """Submits a task to the NATS bus. Returns the task ID."""
        await self.connect()

        # Don't mutate the caller's dict
        task_data = dict(task_data)
        task_id = task_data.pop("id", str(uuid.uuid4()))
        working_dir = task_data.pop("working_dir", None)
        task = TaskSchema(id=task_id, working_dir=working_dir, **task_data)

        logger.info(f"Submitting task {task_id}: {task.description}")
        await self.bus.publish("tasks.submit", task.model_dump())
        return task_id

    async def get_task_status(self, task_id: str) -> TaskStatus | None:
        """Query the current status of a task from the database."""
        from nexusagent.infrastructure.db import get_task_repo

        task_repo = get_task_repo()
        status_str = await task_repo.get_task_status(task_id)
        if status_str:
            return TaskStatus(status_str)
        return None

    async def get_result(self, task_id: str) -> ResultSchema | None:
        """Retrieve the result of a specific task from the JetStream KV store.
        This replaces the ephemeral subscription model to prevent resource leaks.
        """
        await self.connect()

        # We simply fetch the result from the KV store.
        # If the result isn't there yet, the caller can poll or use a watch.
        result_data = await self.bus.get_result(task_id)

        if not result_data:
            return None

        return ResultSchema(**result_data)

    # ─── Listing & Management ────────────────────────────────────────────

    async def list_tasks(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List tasks with optional status filter and pagination."""
        from nexusagent.infrastructure.db import get_task_repo

        task_repo = get_task_repo()
        return await task_repo.list_tasks(status=status, limit=limit, offset=offset)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or processing task. Returns True if cancelled."""
        from nexusagent.infrastructure.db import get_task_repo

        task_repo = get_task_repo()
        return await task_repo.cancel_task(task_id)

    async def retry_task(self, task_id: str) -> str | None:
        """Retry a failed task. Returns task ID or None if not eligible."""
        from nexusagent.infrastructure.db import get_task_repo

        task_repo = get_task_repo()
        new_id = await task_repo.retry_task(task_id)
        if new_id:
            # Re-publish to NATS
            await self.submit_task({"id": new_id, "description": "retried", "priority": 1})
        return new_id

    # ─── Polling Helpers ─────────────────────────────────────────────────

    async def wait_for_result(
        self,
        task_id: str,
        timeout: float = 300.0,
        poll_interval: float = 1.0,
    ) -> ResultSchema | None:
        """Poll for a task result until timeout. Returns the result or None."""
        start = asyncio.get_running_loop().time()
        while True:
            result = await self.get_result(task_id)
            if result is not None:
                return result
            if asyncio.get_running_loop().time() - start >= timeout:
                return None
            await asyncio.sleep(poll_interval)

    async def submit_and_wait(
        self,
        task_data: dict,
        timeout: float = 300.0,
        poll_interval: float = 1.0,
    ) -> ResultSchema | None:
        """Submit a task and wait for the result."""
        task_id = await self.submit_task(task_data)
        return await self.wait_for_result(task_id, timeout=timeout, poll_interval=poll_interval)

    # ─── Batch Operations ────────────────────────────────────────────────

    async def submit_batch(self, tasks: list[dict]) -> list[str]:
        """Submit multiple tasks. Returns list of task IDs."""
        ids = []
        for task_data in tasks:
            task_id = await self.submit_task(task_data)
            ids.append(task_id)
        return ids

    # ─── Status Helpers ──────────────────────────────────────────────────

    async def health_check(self) -> dict:
        """Check system health (NATS connection status + version)."""
        return {
            "status": "ok",
            "version": SERVER_VERSION,
            "minClient": MIN_CLIENT_VERSION,
            "nats": "connected" if self.bus.nc else "disconnected",
        }

    async def list_workers(self) -> dict:
        """List worker status including circuit breaker state."""
        from nexusagent.core.worker import _agent_breaker, _nats_breaker

        return {
            "workers": [
                {
                    "name": "default",
                    "status": "running",
                    "circuit_breakers": {
                        "agent": {
                            "state": _agent_breaker.state,
                            "failure_count": _agent_breaker.failure_count,
                        },
                        "nats": {
                            "state": _nats_breaker.state,
                            "failure_count": _nats_breaker.failure_count,
                        },
                    },
                }
            ]
        }

    async def list_tools(self) -> dict:
        """List all registered tools grouped by category."""
        from nexusagent.tools.registry import list_all_tools

        tools = list_all_tools()
        by_cat: dict[str, list[dict]] = {}
        for t in tools:
            by_cat.setdefault(t.category, []).append(
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            )

        return {"tools": by_cat, "total": len(tools)}


# Global SDK instance
sdk = NexusSDK()
