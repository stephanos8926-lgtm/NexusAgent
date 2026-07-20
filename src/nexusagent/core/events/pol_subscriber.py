# src/nexusagent/core/events/pol_subscriber.py
"""POL Subscriber for detecting failures and coordinating interventions."""

import logging
from typing import Any

from nexusagent.core.events.base import SystemEvent
from nexusagent.core.events.subscribers import EventSubscriber

logger = logging.getLogger(__name__)


class POLSubscriber(EventSubscriber):
    """POL Subscriber: monitors worker, tool, and task failures."""

    def __init__(self) -> None:
        super().__init__(
            name="pol_subscriber",
            subject="nexus.>",
            stream="nexus_events",
            durable="pol_durable",
        )
        self.interventions: list[dict[str, Any]] = []

    async def handle_event(self, event: SystemEvent) -> None:
        """Process failures and tool denials to trigger interventions."""
        if event.type in ("worker.failed", "tool.denied", "task.failed", "failed", "denied"):
            logger.warning(
                f"[POL] Alert! Detected failure/denial '{event.type}' in component {event.source}: {event.payload}"
            )
            self.interventions.append(
                {
                    "event_id": event.id,
                    "type": event.type,
                    "payload": event.payload,
                }
            )
