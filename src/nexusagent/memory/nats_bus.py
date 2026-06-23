"""NATS-based distributed memory bus for cross-worker memory sharing.

Enables workers on different machines to share memories via NATS JetStream
pub/sub. When a worker writes a memory, it's published to a NATS subject.
Other workers subscribed to that subject receive the memory and index it locally.

Architecture:
    Worker A (machine 1)                  Worker B (machine 2)
    ┌──────────────────┐                 ┌──────────────────┐
    │ HybridMemoryMgr  │                 │ HybridMemoryMgr  │
    │       ↕          │                 │       ↕          │
    │ NatsMemoryBus ──│── publish ──────│──→ NatsMemoryBus │
    │                  │                 │       ↕          │
    │                  │                 │ NatsMemoryListener│
    └──────────────────┘                 └──────────────────┘
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from nexusagent.infrastructure.bus import NATSJSONEncoder

logger = logging.getLogger(__name__)


class MemoryOperation(StrEnum):
    """Types of memory operations that can be published to NATS."""
    REMEMBER = "remember"
    DELETE = "delete"
    PROMOTE = "promote"


@dataclass
class MemoryEvent:
    """A memory operation event published to NATS.

    Attributes:
        event_id: Unique identifier for this event.
        operation: The type of memory operation (remember, delete, promote).
        session_id: The session that originated this event.
        timestamp: When the event was created (ISO format).
        payload: The operation-specific data.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operation: MemoryOperation = MemoryOperation.REMEMBER
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "event_id": self.event_id,
            "operation": self.operation.value,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }, cls=NATSJSONEncoder)

    @classmethod
    def from_json(cls, data: str) -> MemoryEvent:
        d = json.loads(data)
        return cls(
            event_id=d["event_id"],
            operation=MemoryOperation(d["operation"]),
            session_id=d["session_id"],
            timestamp=d["timestamp"],
            payload=d["payload"],
        )


class NatsMemoryBus:
    """Publishes memory events to NATS subjects.

    Uses the existing AgentBus NATS connection to publish memory operations
    to a configurable subject prefix. Workers can subscribe to receive
    memories from other workers.

    Args:
        nats_client: An existing NATS client connection.
        subject_prefix: NATS subject prefix for memory events
                        (default: "nexus.memory").
        session_id: The session ID of the publishing worker.
    """

    def __init__(
        self,
        nats_client: Any,
        subject_prefix: str = "nexus.memory",
        session_id: str = "",
    ):
        self._client = nats_client
        self._subject_prefix = subject_prefix
        self._session_id = session_id

    async def publish_remember(
        self,
        content: str,
        memory_type: str = "observation",
        description: str = "",
        confidence: float | None = None,
        entities: list[str] | None = None,
        source_path: str = "",
    ) -> str:
        """Publish a memory write event to NATS.

        Args:
            content: The memory content.
            memory_type: Type of memory (observation, world, opinion, etc.).
            description: Short description/title.
            confidence: Confidence score (0.0-1.0).
            entities: Related entity names.
            source_path: Path to the memory file (if already written locally).

        Returns:
            The event ID of the published event.
        """
        event = MemoryEvent(
            operation=MemoryOperation.REMEMBER,
            session_id=self._session_id,
            payload={
                "content": content,
                "type": memory_type,
                "description": description,
                "confidence": confidence,
                "entities": entities or [],
                "source_path": source_path,
            },
        )
        subject = f"{self._subject_prefix}.remember"
        try:
            await self._client.publish(subject, event.to_json().encode())
            logger.debug("Published memory event %s to %s", event.event_id, subject)
        except Exception as exc:
            logger.warning("Failed to publish memory event: %s", exc)
        return event.event_id

    async def publish_delete(self, memory_path: str) -> str:
        """Publish a memory delete event to NATS.

        Args:
            memory_path: Path to the memory file being deleted.

        Returns:
            The event ID of the published event.
        """
        event = MemoryEvent(
            operation=MemoryOperation.DELETE,
            session_id=self._session_id,
            payload={"memory_path": memory_path},
        )
        subject = f"{self._subject_prefix}.delete"
        try:
            await self._client.publish(subject, event.to_json().encode())
        except Exception as exc:
            logger.warning("Failed to publish delete event: %s", exc)
        return event.event_id

    async def publish_promote(
        self,
        source_session_id: str,
        memory_path: str,
    ) -> str:
        """Publish a memory promotion event (child → parent).

        Args:
            source_session_id: The child session promoting from.
            memory_path: Path to the memory file being promoted.

        Returns:
            The event ID of the published event.
        """
        event = MemoryEvent(
            operation=MemoryOperation.PROMOTE,
            session_id=self._session_id,
            payload={
                "source_session_id": source_session_id,
                "memory_path": memory_path,
            },
        )
        subject = f"{self._subject_prefix}.promote"
        try:
            await self._client.publish(subject, event.to_json().encode())
        except Exception as exc:
            logger.warning("Failed to publish promote event: %s", exc)
        return event.event_id


class NatsMemoryListener:
    """Listens for memory events on NATS and applies them to local memory.

    Subscribes to the memory event subjects and, when a REMEMBER event is
    received from another session, writes the memory to the local HybridMemoryManager.

    Args:
        nats_client: An existing NATS client connection.
        memory_manager: The local HybridMemoryManager to write received memories to.
        subject_prefix: NATS subject prefix to subscribe to.
        session_id: The local session ID (to filter out own events).
    """

    def __init__(
        self,
        nats_client: Any,
        memory_manager: Any,
        subject_prefix: str = "nexus.memory",
        session_id: str = "",
    ):
        self._client = nats_client
        self._memory_manager = memory_manager
        self._subject_prefix = subject_prefix
        self._session_id = session_id
        self._subscription: Any = None
        self._running = False
        self._received_event_ids: set[str] = set()

    async def start(self) -> None:
        """Start listening for memory events on NATS."""
        if self._running:
            return
        self._running = True
        subject = f"{self._subject_prefix}.*"
        try:
            self._subscription = await self._client.subscribe(
                subject, cb=self._handle_message
            )
            logger.info("NATS memory listener started on %s", subject)
        except Exception as exc:
            logger.warning("Failed to start NATS memory listener: %s", exc)
            self._running = False

    async def stop(self) -> None:
        """Stop listening and unsubscribe."""
        if not self._running:
            return
        self._running = False
        if self._subscription:
            try:
                await self._subscription.unsubscribe()
            except Exception as exc:
                logger.debug("Error unsubscribing: %s", exc)
            self._subscription = None
        logger.info("NATS memory listener stopped")

    async def _handle_message(self, msg: Any) -> None:
        """Handle an incoming NATS memory event message."""
        try:
            event = MemoryEvent.from_json(msg.data.decode())
        except Exception as exc:
            logger.warning("Failed to parse memory event: %s", exc)
            return

        # Skip own events
        if event.session_id == self._session_id:
            return

        # Deduplicate
        if event.event_id in self._received_event_ids:
            return
        self._received_event_ids.add(event.event_id)

        try:
            if event.operation == MemoryOperation.REMEMBER:
                await self._handle_remember(event)
            elif event.operation == MemoryOperation.DELETE:
                await self._handle_delete(event)
            elif event.operation == MemoryOperation.PROMOTE:
                await self._handle_promote(event)
        except Exception as exc:
            logger.warning("Failed to handle memory event %s: %s", event.event_id, exc)

    async def _handle_remember(self, event: MemoryEvent) -> None:
        """Handle a REMEMBER event by writing to local memory."""
        payload = event.payload
        await self._memory_manager.remember(
            content=f"[Remote: {event.session_id}] {payload.get('content', '')}",
            type=payload.get("type", "observation"),
            description=payload.get("description", ""),
            confidence=payload.get("confidence"),
            entities=payload.get("entities"),
        )
        logger.debug("Applied remote memory from session %s", event.session_id)

    async def _handle_delete(self, event: MemoryEvent) -> None:
        """Handle a DELETE event (no-op for remote — we don't delete others' memories)."""
        logger.debug("Received delete event from %s (no-op)", event.session_id)

    async def _handle_promote(self, event: MemoryEvent) -> None:
        """Handle a PROMOTE event by writing promoted memory locally."""
        payload = event.payload
        source = payload.get("source_session_id", "unknown")
        await self._memory_manager.remember(
            content=f"[Promoted: {source}] {payload.get('content', '')}",
            type="observation",
            description=f"Promoted from session {source}",
            confidence=0.7,
        )
