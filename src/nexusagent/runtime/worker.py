"""Managed adapter for workers with lifecycle support.

ManagedWorker wraps SubAgentHandle with observable lifecycle.
RuntimeWorkerManager wraps WorkerPool with the same pattern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from nexusagent.runtime.context import RuntimeContext
from nexusagent.runtime.lifecycle import (
    HealthStatus,
    LifecycleMixin,
    LifecycleState,
)

logger = logging.getLogger("nexusagent.runtime.worker")


@dataclass
class WorkerMetadata:
    """Metadata for a managed worker."""

    worker_id: str
    created_at: float = 0.0
    label: str = ""
    tags: list[str] = field(default_factory=list)


class ManagedWorker(LifecycleMixin):
    """Wraps a SubAgentHandle with observable lifecycle.

    Maps SubAgentStatus → LifecycleState:
      PENDING       → CREATED
      RUNNING       → RUNNING
      COMPLETED     → COMPLETED
      FAILED        → FAILED
      CANCELLED     → TERMINATED
    """

    def __init__(
        self,
        handle: Any,
        context: Optional[RuntimeContext] = None,
        metadata: Optional[WorkerMetadata] = None,
    ) -> None:
        self._handle = handle
        self._context = context
        self._metadata = metadata or WorkerMetadata(
            worker_id=handle.worker_id,
            created_at=handle.created_at.timestamp() if hasattr(handle, "created_at") else 0,
        )
        self._state = LifecycleState.CREATED

    # --- LifecycleMixin ---

    @property
    def state(self) -> LifecycleState:
        """Derive lifecycle state from the underlying handle status."""
        self._sync_state()
        return self._state

    @property
    def handle(self) -> Any:
        return self._handle

    @property
    def worker_id(self) -> str:
        return self._handle.worker_id

    async def initialize(self) -> None:
        """ManagedWorker wraps an already-spawned handle — no-op."""
        self._sync_state()

    async def shutdown(self) -> None:
        """Cancel the worker if still running."""
        if not self._handle.is_done():
            self._handle.cancel()
        self._state = LifecycleState.TERMINATED

    def health(self) -> HealthStatus:
        self._sync_state()
        return HealthStatus(
            healthy=self._state in (LifecycleState.RUNNING, LifecycleState.COMPLETED),
            degraded=self._state == LifecycleState.CREATED,
            failed=self._state == LifecycleState.FAILED,
            details={
                "worker_id": self.worker_id,
                "state": self._state.value,
                "handle_status": str(self._handle.status),
            },
        )

    # --- Delegated API ---

    async def wait(self) -> Any:
        """Wait for the worker to complete."""
        return await self._handle.wait()

    def cancel(self) -> None:
        """Cancel the worker."""
        self._handle.cancel()
        self._state = LifecycleState.TERMINATED

    def is_done(self) -> bool:
        return self._handle.is_done()

    @property
    def result(self) -> Any:
        return self._handle.result

    @property
    def error(self) -> str | None:
        return self._handle.error

    # --- Internal ---

    def _sync_state(self) -> None:
        """Sync state from SubAgentHandle status."""
        from nexusagent.core.subagent import SubAgentStatus

        status = self._handle.status
        if status == SubAgentStatus.PENDING:
            self._state = LifecycleState.CREATED
        elif status == SubAgentStatus.RUNNING:
            self._state = LifecycleState.RUNNING
        elif status == SubAgentStatus.COMPLETED:
            self._state = LifecycleState.COMPLETED
        elif status == SubAgentStatus.FAILED:
            self._state = LifecycleState.FAILED
        elif status == SubAgentStatus.CANCELLED:
            self._state = LifecycleState.TERMINATED


class RuntimeWorkerManager(LifecycleMixin):
    """Manages multiple ManagedWorkers with Runtime context.

    Wraps WorkerPool with lifecycle and RuntimeContext integration.
    """

    def __init__(
        self,
        context: Optional[RuntimeContext] = None,
        max_workers: int = 4,
    ) -> None:
        self._context = context
        self._state = LifecycleState.CREATED
        self._workers: dict[str, ManagedWorker] = {}
        self._pool = None  # WorkerPool — lazily created
        self._max_workers = max_workers

    @property
    def state(self) -> LifecycleState:
        return self._state

    async def initialize(self) -> None:
        """Initialize the worker manager."""
        self._state = LifecycleState.INITIALIZING
        from nexusagent.core.worker.pool import WorkerPool

        self._pool = WorkerPool(max_workers=self._max_workers)
        if self._context is not None:
            self._context.worker_manager = self
        self._state = LifecycleState.RUNNING
        logger.info("RuntimeWorkerManager initialized (max_workers=%d).", self._max_workers)

    async def shutdown(self) -> None:
        """Cancel all active workers."""
        for worker_id, managed in list(self._workers.items()):
            try:
                managed.cancel()
            except Exception as e:
                logger.warning("Worker %s cancel error: %s", worker_id, e)
        self._workers.clear()
        self._state = LifecycleState.TERMINATED

    def health(self) -> HealthStatus:
        return HealthStatus(
            healthy=self._state == LifecycleState.RUNNING,
            details={
                "state": self._state.value,
                "active_workers": len(self._workers),
                "max_workers": self._max_workers,
            },
        )

    async def spawn(self, contract: Any, depth: int = 0) -> ManagedWorker:
        """Spawn a new worker and wrap it in ManagedWorker.

        Returns ManagedWorker wrapping the SubAgentHandle.
        """
        if self._pool is None:
            raise RuntimeError("Worker manager not initialized — call initialize() first")

        handle = await self._pool.spawn(contract, depth=depth)
        managed = ManagedWorker(
            handle=handle,
            context=self._context,
            metadata=WorkerMetadata(worker_id=handle.worker_id),
        )
        self._workers[handle.worker_id] = managed
        return managed

    def get(self, worker_id: str) -> Optional[ManagedWorker]:
        """Get a managed worker by ID."""
        return self._workers.get(worker_id)

    @property
    def active_count(self) -> int:
        return len(self._workers)
