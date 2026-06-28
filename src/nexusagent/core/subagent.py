# src/nexusagent/subagent.py
"""SubAgentHandle — control interface for spawned worker agents."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from nexusagent.llm.models import TaskContract


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
    waiting for completion. Supports summary-only returns and per-agent
    model/depth configuration via the TaskContract.
    """

    def __init__(self, worker_id: str, contract: TaskContract, depth: int = 0) -> None:
        """Initialize a sub-agent control handle.

        Args:
            worker_id: Unique identifier for the spawned worker.
            contract: Task configuration (model, max_depth, summary_only, etc.).
            depth: Current nesting depth (0 = top-level). Children get depth + 1.
        """
        self.worker_id = worker_id
        self.contract = contract
        self.depth = depth  # Nesting depth (0 = top-level)

        self._status: SubAgentStatus = SubAgentStatus.PENDING
        self._result: Any = None
        self._summary: str | None = None  # Summary-only return
        self._error: str | None = None

        self._cancel_event: asyncio.Event = asyncio.Event()
        self._done_event: asyncio.Event = asyncio.Event()

        self.created_at: datetime = datetime.now(UTC)
        self.completed_at: datetime | None = None

    # -- public properties ---------------------------------------------------

    @property
    def status(self) -> SubAgentStatus:
        """Return the current lifecycle status of the sub-agent."""
        return self._status

    @property
    def result(self) -> Any:
        """Return full result or summary depending on contract.summary_only."""
        if self.contract.summary_only:
            return self._summary
        return self._result

    @property
    def summary(self) -> str | None:
        """Return the summary string (available when summary_only=True)."""
        return self._summary

    @property
    def error(self) -> str | None:
        """Return the error message if the sub-agent failed, or None."""
        return self._error

    @property
    def model(self) -> str:
        """Return the model for this sub-agent.

        Resolution order:
        1. contract.model  (explicit per-task override)
        2. AGENT_MODEL env var  (deployment-level override)
        3. settings.agent.default_model  (config file / default)

        Never falls back to a hardcoded model name — always inherits from
        the active configuration so subagents match the main agent provider.
        """
        from nexusagent.infrastructure.config import settings

        return self.contract.model or os.getenv("AGENT_MODEL") or settings.agent.default_model

    @property
    def provider(self) -> str:
        """Return the LLM provider for this sub-agent.

        Resolution order:
        1. contract.provider  (explicit per-task override)
        2. settings.agent.primary_provider  (config file / default)

        Ensures subagents use the same provider as the main agent unless
        explicitly overridden.
        """
        from nexusagent.infrastructure.config import settings

        return self.contract.provider or settings.agent.primary_provider

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

    def can_spawn_child(self) -> bool:
        """Return True if this sub-agent can spawn children (depth < max_depth)."""
        return self.depth < self.contract.max_depth

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

        Returns the result (or summary if summary_only=True) on completion.
        Raises ``RuntimeError`` on failure or ``CancelledError`` on cancellation.
        """
        await asyncio.wait_for(self._done_event.wait(), timeout=timeout)

        if self._status == SubAgentStatus.FAILED:
            raise RuntimeError(f"Sub-agent {self.worker_id} failed: {self._error}")
        if self._status == SubAgentStatus.CANCELLED:
            raise asyncio.CancelledError(f"Sub-agent {self.worker_id} was cancelled")

        return self.result

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
        # Generate summary if summary_only
        if self.contract.summary_only:
            self._summary = self._generate_summary(result)
        self.completed_at = datetime.now(UTC)
        self._done_event.set()

    def _mark_failed(self, error: str) -> None:
        """Transition to FAILED with the given error message."""
        self._status = SubAgentStatus.FAILED
        self._error = error
        self.completed_at = datetime.now(UTC)
        self._done_event.set()

    @staticmethod
    def _generate_summary(result: Any) -> str:
        """Generate a concise summary from a full result."""
        text = str(result)
        # Take first 500 chars as summary
        if len(text) > 500:
            return text[:500] + "... [truncated]"
        return text
