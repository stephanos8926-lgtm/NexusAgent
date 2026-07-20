# src/nexusagent/core/events/memory_subscriber.py
"""Memory Subscriber for triggered memory extraction and consolidation."""

import logging
from typing import Any

from nexusagent.core.events.base import SystemEvent
from nexusagent.core.events.subscribers import EventSubscriber

logger = logging.getLogger(__name__)


class MemorySubscriber(EventSubscriber):
    """Memory Subscriber: reacts to successful task and tool completions."""

    def __init__(self) -> None:
        super().__init__(
            name="memory_subscriber",
            subject="nexus.>",
            stream="nexus_events",
            durable="memory_durable",
        )
        self.processed_completions: list[dict[str, Any]] = []

    async def handle_event(self, event: SystemEvent) -> None:
        """Extract and consolidate memories on successful completion."""
        if event.type in ("task.completed", "tool.completed", "completed"):
            logger.info(
                f"[Memory] Triggered consolidation by {event.type} from source {event.source}"
            )
            self.processed_completions.append(
                {
                    "event_id": event.id,
                    "type": event.type,
                    "payload": event.payload,
                }
            )
