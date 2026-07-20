"""Worker lifecycle events.

Defines WorkerEvent and its subtypes for worker lifecycle tracking:
- worker.started: Worker process begins
- worker.failed: Worker encounters unrecoverable error
- worker.recovered: Worker resumes from checkpoint
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from nexusagent.core.events.base import EventType, SystemEvent


class WorkerEventType(Enum):
    """Worker event types as defined in the architecture."""

    STARTED = "started"
    FAILED = "failed"
    RECOVERED = "recovered"


@dataclass
class WorkerEvent(SystemEvent):
    """Event emitted during worker lifecycle transitions.

    Category: worker
    NATS subjects: nexus.worker.started, nexus.worker.failed, nexus.worker.recovered

    Payload contains worker-specific data:
    - worker_id: The unique worker identifier
    - task_id: The task being executed by this worker
    - model: The LLM model being used
    - provider: The LLM provider
    - error: Error message for failed events
    - checkpoint: Checkpoint data for recovery events
    """

    category: EventType = EventType.WORKER

    # Convenience factory methods for each event type
    @classmethod
    def started(
        cls,
        source: str,
        worker_id: str,
        task_id: str = "",
        model: str = "",
        provider: str = "",
        **extra: Any,
    ) -> WorkerEvent:
        """Create a worker.started event."""
        return cls(
            source=source,
            type="started",
            payload={
                "worker_id": worker_id,
                "task_id": task_id,
                "model": model,
                "provider": provider,
                **extra,
            },
        )

    @classmethod
    def failed(
        cls,
        source: str,
        worker_id: str,
        task_id: str = "",
        error: str = "",
        **extra: Any,
    ) -> WorkerEvent:
        """Create a worker.failed event."""
        return cls(
            source=source,
            type="failed",
            payload={
                "worker_id": worker_id,
                "task_id": task_id,
                "error": error,
                **extra,
            },
        )

    @classmethod
    def recovered(
        cls,
        source: str,
        worker_id: str,
        task_id: str = "",
        checkpoint: dict | None = None,
        **extra: Any,
    ) -> WorkerEvent:
        """Create a worker.recovered event."""
        return cls(
            source=source,
            type="recovered",
            payload={
                "worker_id": worker_id,
                "task_id": task_id,
                "checkpoint": checkpoint,
                **extra,
            },
        )

    @property
    def worker_id(self) -> str | None:
        """Extract worker_id from payload."""
        return self.payload.get("worker_id")

    @property
    def task_id(self) -> str | None:
        """Extract task_id from payload."""
        return self.payload.get("task_id")

    @property
    def error(self) -> str | None:
        """Extract error from payload (for failed events)."""
        return self.payload.get("error")

    @property
    def checkpoint(self) -> dict | None:
        """Extract checkpoint from payload (for recovered events)."""
        return self.payload.get("checkpoint")
