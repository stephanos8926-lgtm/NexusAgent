# src/nexusagent/security/router.py
"""CapabilityRouter checks required capabilities for tools and emits audit trail events."""

from __future__ import annotations

import logging
from typing import Any

from nexusagent.core.events import PolicyEvent, emit_event, emit_event_sync

from .engine import get_policy_engine
from .registry import (  # noqa: F401 (re-exported for test)
    get_capability_registry,
    get_required_capability,
)

logger = logging.getLogger(__name__)


def log_audit_event_sync(
    source: str,
    action: str,
    allowed: bool,
    reason: str,
    role: str = "",
    policy: str = "",
    resource: str = "",
    tool_name: str = "",
    task_id: str = "",
    worker_id: str = "",
    **extra: Any,
) -> None:
    """Synchronously log a capability check to the event store/NATS."""
    try:
        if allowed:
            event = PolicyEvent.allowed(
                source=source,
                action=action,
                role=role,
                policy=policy,
                resource=resource,
                tool_name=tool_name,
                task_id=task_id,
                worker_id=worker_id,
                **extra,
            )
        else:
            event = PolicyEvent.denied(
                source=source,
                action=action,
                reason=reason,
                role=role,
                policy=policy,
                resource=resource,
                tool_name=tool_name,
                task_id=task_id,
                worker_id=worker_id,
                **extra,
            )
        emit_event_sync(event)
    except Exception as e:
        logger.warning(f"Failed to log sync security audit event: {e}")


async def log_audit_event_async(
    source: str,
    action: str,
    allowed: bool,
    reason: str,
    role: str = "",
    policy: str = "",
    resource: str = "",
    tool_name: str = "",
    task_id: str = "",
    worker_id: str = "",
    **extra: Any,
) -> None:
    """Asynchronously log a capability check to the event store/NATS."""
    try:
        if allowed:
            event = PolicyEvent.allowed(
                source=source,
                action=action,
                role=role,
                policy=policy,
                resource=resource,
                tool_name=tool_name,
                task_id=task_id,
                worker_id=worker_id,
                **extra,
            )
        else:
            event = PolicyEvent.denied(
                source=source,
                action=action,
                reason=reason,
                role=role,
                policy=policy,
                resource=resource,
                tool_name=tool_name,
                task_id=task_id,
                worker_id=worker_id,
                **extra,
            )
        await emit_event(event)
    except Exception as e:
        logger.warning(f"Failed to log async security audit event: {e}")


class CapabilityRouter:
    """Intercepts and evaluates privilege and tool checks, ensuring strict capability-based authorization."""

    def __init__(self) -> None:
        self.registry = get_capability_registry()
        self.engine = get_policy_engine()

    def check_tool_access(self, tool_name: str) -> tuple[bool, str]:
        """Check if the current context has the capability required to run the given tool."""
        # Dynamically resolve context to avoid circular dependencies and handle concurrent sessions
        from nexusagent.runtime.context import current_context
        from nexusagent.tools.registry.policy import get_policy_context

        ctx = current_context()
        session_id = None
        role = "full"
        policy_mode = "permissive"

        if ctx is not None:
            session_id = ctx.current_session_id
            if ctx.policy_context:
                role = ctx.policy_context.get("role", "full")
                policy_mode = ctx.policy_context.get("policy", "permissive")
        else:
            # Fallback to local thread/context storage
            from nexusagent.core.agent import _current_session
            local_session = _current_session.get()
            if local_session:
                session_id = getattr(local_session, "session_id", None)

            pctx = get_policy_context()
            role = pctx.get("role", "full")
            policy_mode = pctx.get("policy", "permissive")

        # Resolve capability constraint
        capability_name = self.registry.get_required_capability(tool_name)
        if not capability_name:
            # Unprivileged/general tools are always allowed
            return True, "Allowed (unprivileged tool)"

        cap_info = self.registry.get_capability(capability_name)
        scope = cap_info.scope if cap_info else "workspace"
        risk_label = cap_info.risk_level.value if cap_info else "low"

        # Evaluate capability via PolicyEngine
        allowed, reason = self.engine.evaluate_capability(
            session_id=session_id,
            role=role,
            policy_mode=policy_mode,
            capability_name=capability_name,
            tool_name=tool_name,
        )

        # Sync audit trail logging
        log_audit_event_sync(
            source="CapabilityRouter",
            action=f"capability.{capability_name}",
            allowed=allowed,
            reason=reason,
            role=role,
            policy=policy_mode,
            resource=scope,
            tool_name=tool_name,
            task_id=session_id or "",
        )

        if not allowed:
            # Return legacy-compatible error output structure
            return False, f"ACCESS DENIED: Capability '{capability_name}' (risk: {risk_label}) is required but denied: {reason}"

        return True, ""


# Global singleton pattern
_router_instance: CapabilityRouter | None = None


def get_capability_router() -> CapabilityRouter:
    """Get the global CapabilityRouter instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = CapabilityRouter()
    return _router_instance
