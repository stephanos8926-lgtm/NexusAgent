# src/nexusagent/core/events/subscribers.py
"""Base Subscriber Framework for NexusAgent event-driven core."""

from __future__ import annotations

import json
import logging
from typing import Any

from nexusagent.core.events.base import SystemEvent
from nexusagent.infrastructure.bus import get_bus

logger = logging.getLogger(__name__)


class EventSubscriber:
    """Base class for all background event subscribers."""

    def __init__(
        self, name: str, subject: str, stream: str = "nexus_events", durable: str | None = None
    ) -> None:
        """Initialize the event subscriber with subject, stream and durable consumer names."""
        self.name = name
        self.subject = subject
        self.stream = stream
        self.durable = durable or name
        self._bus = get_bus()

    async def start(self) -> None:
        """Start the background consumer loop on the message bus."""
        logger.info(
            f"Starting subscriber {self.name} on subject '{self.subject}' (stream '{self.stream}', durable '{self.durable}')"
        )
        await self._bus.subscribe_durable(
            subject=self.subject,
            callback=self._handle_raw_msg,
            stream=self.stream,
            durable=self.durable,
        )

    async def _handle_raw_msg(self, msg: Any) -> None:
        """Parse raw NATS message and route to handle_event."""
        try:
            data = json.loads(msg.data.decode())
            # Convert from dict to SystemEvent
            event = SystemEvent(
                source=data.get("source", "unknown"),
                type=data.get("type", "unknown"),
                payload=data.get("payload", {}),
            )
            event.id = data.get("id", event.id)
            event.timestamp = data.get("timestamp", event.timestamp)
            await self.handle_event(event)
        except Exception as e:
            logger.error(f"Subscriber {self.name} failed to process message: {e}", exc_info=True)
            raise

    async def handle_event(self, event: SystemEvent) -> None:
        """Process the parsed SystemEvent. Must be implemented by subclasses."""
        raise NotImplementedError
