# src/nexusagent/core/events/dashboard_subscriber.py
"""Dashboard Subscriber for real-time visualization streams."""

import logging
from typing import Any

from nexusagent.core.events.base import SystemEvent
from nexusagent.core.events.subscribers import EventSubscriber

logger = logging.getLogger(__name__)


class DashboardSubscriber(EventSubscriber):
    """Dashboard Subscriber: captures all system events for real-time streaming."""

    def __init__(self) -> None:
        super().__init__(
            name="dashboard_subscriber",
            subject="nexus.>",
            stream="nexus_events",
            durable="dashboard_durable",
        )
        self.events_received: list[dict[str, Any]] = []

    async def handle_event(self, event: SystemEvent) -> None:
        """Stream system events to visualization dashboards."""
        logger.info(f"[Dashboard] Received live system event: {event.type}")
        self.events_received.append(event.to_dict())
