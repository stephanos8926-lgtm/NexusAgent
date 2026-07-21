# src/nexusagent/core/pol_subscriber.py
"""POL Subscriber for detecting failures and coordinating interventions."""

import logging
from typing import Any

from nexusagent.core.events.base import SystemEvent
from nexusagent.core.events.subscribers import EventSubscriber
from nexusagent.core.pol import get_pol_control_plane

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
        # Check standard failure types or policy violations
        is_failure_or_denial = event.type in (
            "worker.failed",
            "tool.denied",
            "task.failed",
            "failed",
            "denied",
            "violation",
        )

        if is_failure_or_denial:
            logger.warning(
                f"[POL] Alert! Detected failure/denial '{event.type}' in component {event.source}: {event.payload}"
            )
            # Create active intervention in the POL Control Plane
            pol = get_pol_control_plane()
            task_id = event.payload.get("task_id")
            reason = "repeated_tool_failure" if event.type == "tool.denied" else f"{event.type}"
            guidance = (
                event.payload.get("reason")
                or event.payload.get("error")
                or "Review failure logs before proceeding."
            )

            # Save in list for subscriber-level tracking/backward compatibility
            self.interventions.append(
                {
                    "event_id": event.id,
                    "type": event.type,
                    "payload": event.payload,
                }
            )

            # Register in the POL Control Plane
            await pol.create_intervention(
                task_id=task_id,
                reason=reason,
                guidance=guidance,
                priority="high" if event.type != "violation" else "medium",
                payload={"event_id": event.id, "source": event.source, **event.payload},
            )
