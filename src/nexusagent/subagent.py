# src/nexusagent/subagent.py
"""SubAgentHandle — control interface for spawned worker agents."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from nexusagent.models import TaskContract


class SubAgentStatus(StrEnum):
    """Lifecycle states for a sub-agent worker."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubAgentHandle:
    """Control handle for a spawned sub-agent worker.

    Provides status tracking, cancellation signaling, and synchronous/async
    waiting for completion.
    """

    def __init__(self, worker_id: str, contract: TaskContract) -> None:
        self.worker_id = worker_id
        self.contract = contract

        self._status: SubAgentStatus = SubAgentStatus.PENDING
        self._result: Any = None
        self._error: str | None = None

        self._cancel_event: asyncio.Event = asyncio.Event()
        self._done_event: asyncio.Event = asyncio.Event()

        self.created_at: datetime = datetime.now(UTC)
        self.completed_at: datetime | None = None

    # -- public properties ---------------------------------------------------

    @property
    def status(self) -> SubAgentStatus:
        return self._status

    @property
    def result(self) -> Any:
        return self._result

    @property
    def error(self) -> str | None:
        return self._error

    # -- public query methods ------------------------------------------------

    def is_done(self) -> bool:
        """Return True when the handle is in a terminal state."""
        return self._status in {
            SubAgentStatus.COMPLETED,
            SubAgentStatus.FAILED,
            SubAgentStatus.CANCELLED,
        }

    def is_cancelled(self) -> bool:
        """Return True if the sub-agent was cancelled."""
        return self._status == SubAgentStatus.CANCELLED

    # -- cancellation --------------------------------------------------------

    def cancel(self) -> bool:
        """Signal cancellation to the sub-agent.

        Returns True if the cancellation was signaled (the handle was not
        already in a terminal state), False otherwise.
        """
        if self.is_done():
            return False

        self._status = SubAgentStatus.CANCELLED
        self._cancel_event.set()
        self._done_event.set()
        self.completed_at = datetime.now(UTC)
        return True

    # -- waiting -------------------------------------------------------------

    async def wait(self, timeout: float | None = None) -> Any:
        """Wait for the sub-agent to reach a terminal state.

        Returns the result on completion.  Raises ``RuntimeError`` on failure
        or ``CancelledError`` on cancellation.
        """
        await asyncio.wait_for(self._done_event.wait(), timeout=timeout)

        if self._status == SubAgentStatus.FAILED:
            raise RuntimeError(f"Sub-agent {self.worker_id} failed: {self._error}")
        if self._status == SubAgentStatus.CANCELLED:
            raise asyncio.CancelledError(f"Sub-agent {self.worker_id} was cancelled")

        return self._result

    # -- internal state transitions ------------------------------------------

    def _mark_running(self) -> None:
        """Transition from PENDING → RUNNING."""
        if self._status != SubAgentStatus.PENDING:
            msg = f"Cannot mark RUNNING from {self._status!r}"
            raise RuntimeError(msg)
        self._status = SubAgentStatus.RUNNING

    def _mark_completed(self, result: Any) -> None:
        """Transition to COMPLETED with the given result."""
        self._status = SubAgentStatus.COMPLETED
        self._result = result
        self.completed_at = datetime.now(UTC)
        self._done_event.set()

    def _mark_failed(self, error: str) -> None:
        """Transition to FAILED with the given error message."""
        self._status = SubAgentStatus.FAILED
        self._error = error
        self.completed_at = datetime.now(UTC)
        self._done_event.set()
