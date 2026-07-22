"""Phase 8: Capability Security Model for NexusAgent.

Handles audit trail logging of capability grants and denials to the EventStore.
"""

from __future__ import annotations

import logging
from typing import Any

from nexusagent.core.events.emitter import emit_event_sync
from nexusagent.core.events.policy_events import PolicyEvent

logger = logging.getLogger("nexusagent.security.audit")


async def audit_grant(
    agent_id: str,
    capability: str,
    scope: str,
    rule: str,
    **extra: Any,
) -> None:
    """Log a capability grant to the EventStore asynchronously."""
    try:
        from nexusagent.core.events.emitter import emit_event

        event = PolicyEvent.allowed(
            source="CapabilitySecurityModel",
            action=f"grant_{capability}",
            role="",
            policy="",
            resource=scope,
            tool_name="",
            task_id=agent_id,
            worker_id=agent_id,
            rule=rule,
            **extra,
        )
        await emit_event(event)
    except Exception as e:
        logger.error(f"Failed to emit audit event for capability grant: {e}")


async def audit_denial(
    agent_id: str,
    capability: str,
    scope: str,
    rule: str,
    reason: str,
    **extra: Any,
) -> None:
    """Log a capability denial to the EventStore asynchronously."""
    try:
        from nexusagent.core.events.emitter import emit_event

        event = PolicyEvent.denied(
            source="CapabilitySecurityModel",
            action=f"deny_{capability}",
            reason=reason,
            role="",
            policy="",
            resource=scope,
            tool_name="",
            task_id=agent_id,
            worker_id=agent_id,
            rule=rule,
            **extra,
        )
        await emit_event(event)
    except Exception as e:
        logger.error(f"Failed to emit audit event for capability denial: {e}")


def audit_grant_sync(
    agent_id: str,
    capability: str,
    scope: str,
    rule: str,
    **extra: Any,
) -> None:
    """Log a capability grant to the EventStore synchronously."""
    try:
        event = PolicyEvent.allowed(
            source="CapabilitySecurityModel",
            action=f"grant_{capability}",
            role="",
            policy="",
            resource=scope,
            tool_name="",
            task_id=agent_id,
            worker_id=agent_id,
            rule=rule,
            **extra,
        )
        emit_event_sync(event)
    except Exception as e:
        logger.error(f"Failed to emit audit event for capability grant: {e}")


def audit_denial_sync(
    agent_id: str,
    capability: str,
    scope: str,
    rule: str,
    reason: str,
    **extra: Any,
) -> None:
    """Log a capability denial to the EventStore synchronously."""
    try:
        event = PolicyEvent.denied(
            source="CapabilitySecurityModel",
            action=f"deny_{capability}",
            reason=reason,
            role="",
            policy="",
            resource=scope,
            tool_name="",
            task_id=agent_id,
            worker_id=agent_id,
            rule=rule,
            **extra,
        )
        emit_event_sync(event)
    except Exception as e:
        logger.error(f"Failed to emit audit event for capability denial: {e}")
