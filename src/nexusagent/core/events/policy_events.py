"""Policy enforcement events.

Defines PolicyEvent for tracking policy-related actions:
- policy.denied: Policy rejects an action (tool, file access, etc.)
- policy.allowed: Policy allows an action
- policy.updated: Policy configuration changed
- policy.violation: Policy violation detected
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from nexusagent.core.events.base import SystemEvent, EventType


class PolicyEventType(Enum):
    """Policy event types."""
    DENIED = "denied"
    ALLOWED = "allowed"
    UPDATED = "updated"
    VIOLATION = "violation"


@dataclass
class PolicyEvent(SystemEvent):
    """Event emitted during policy enforcement.
    
    Category: policy
    NATS subjects: nexus.policy.denied, nexus.policy.allowed, nexus.policy.updated, nexus.policy.violation
    
    Payload contains policy-specific data:
    - action: The action being checked (e.g., "tool_read_file", "access_secret")
    - resource: The resource being accessed
    - role: The role of the agent
    - policy: The policy mode (permissive, restricted, strict)
    - reason: Reason for denial or violation details
    - tool_name: Tool name if this is a tool access check
    - worker_id: Worker context
    - task_id: Task context
    """
    
    category: EventType = EventType.POLICY
    
    # Convenience factory methods for each event type
    @classmethod
    def denied(
        cls,
        source: str,
        action: str,
        reason: str,
        role: str = "",
        policy: str = "",
        resource: str = "",
        tool_name: str = "",
        task_id: str = "",
        worker_id: str = "",
        **extra: Any,
    ) -> "PolicyEvent":
        """Create a policy.denied event."""
        return cls(
            source=source,
            type="denied",
            payload={
                "action": action,
                "reason": reason,
                "role": role,
                "policy": policy,
                "resource": resource,
                "tool_name": tool_name,
                "task_id": task_id,
                "worker_id": worker_id,
                **extra,
            },
        )
    
    @classmethod
    def allowed(
        cls,
        source: str,
        action: str,
        role: str = "",
        policy: str = "",
        resource: str = "",
        tool_name: str = "",
        task_id: str = "",
        worker_id: str = "",
        **extra: Any,
    ) -> "PolicyEvent":
        """Create a policy.allowed event."""
        return cls(
            source=source,
            type="allowed",
            payload={
                "action": action,
                "role": role,
                "policy": policy,
                "resource": resource,
                "tool_name": tool_name,
                "task_id": task_id,
                "worker_id": worker_id,
                **extra,
            },
        )
    
    @classmethod
    def updated(
        cls,
        source: str,
        policy_name: str,
        new_config: dict,
        **extra: Any,
    ) -> "PolicyEvent":
        """Create a policy.updated event."""
        return cls(
            source=source,
            type="updated",
            payload={
                "policy_name": policy_name,
                "new_config": new_config,
                **extra,
            },
        )
    
    @classmethod
    def violation(
        cls,
        source: str,
        action: str,
        details: str,
        role: str = "",
        policy: str = "",
        **extra: Any,
    ) -> "PolicyEvent":
        """Create a policy.violation event."""
        return cls(
            source=source,
            type="violation",
            payload={
                "action": action,
                "details": details,
                "role": role,
                "policy": policy,
                **extra,
            },
        )
    
    @property
    def action(self) -> str | None:
        """Extract action from payload."""
        return self.payload.get("action")
    
    @property
    def reason(self) -> str | None:
        """Extract reason from payload."""
        return self.payload.get("reason")
    
    @property
    def role(self) -> str | None:
        """Extract role from payload."""
        return self.payload.get("role")
    
    @property
    def policy(self) -> str | None:
        """Extract policy from payload."""
        return self.payload.get("policy")
    
    @property
    def tool_name(self) -> str | None:
        """Extract tool_name from payload."""
        return self.payload.get("tool_name")
