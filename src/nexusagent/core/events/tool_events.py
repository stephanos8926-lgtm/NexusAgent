"""Tool execution events.

Defines ToolEvent and its subtypes for tool execution tracking:
- tool.requested: Agent requests tool execution
- tool.completed: Tool returns result
- tool.denied: Policy rejects tool execution
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from nexusagent.core.events.base import SystemEvent, EventType


class ToolEventType(Enum):
    """Tool event types as defined in the architecture."""
    REQUESTED = "requested"
    COMPLETED = "completed"
    DENIED = "denied"


@dataclass
class ToolEvent(SystemEvent):
    """Event emitted during tool execution.
    
    Category: tool
    NATS subjects: nexus.tool.requested, nexus.tool.completed, nexus.tool.denied
    
    Payload contains tool-specific data:
    - task_id: The task context for this tool call
    - worker_id: The worker executing the tool
    - tool_name: Name of the tool being called
    - tool_args: Arguments passed to the tool
    - result: Result from tool execution
    - error: Error message if tool failed
    - denied_reason: Reason for denial (for denied events)
    - policy: Policy that was applied
    """
    
    category: EventType = EventType.TOOL
    
    # Convenience factory methods for each event type
    @classmethod
    def requested(
        cls,
        source: str,
        tool_name: str,
        task_id: str = "",
        worker_id: str = "",
        tool_args: dict | None = None,
        **extra: Any,
    ) -> "ToolEvent":
        """Create a tool.requested event."""
        return cls(
            source=source,
            type="requested",
            payload={
                "tool_name": tool_name,
                "task_id": task_id,
                "worker_id": worker_id,
                "tool_args": tool_args,
                **extra,
            },
        )
    
    @classmethod
    def completed(
        cls,
        source: str,
        tool_name: str,
        task_id: str = "",
        worker_id: str = "",
        result: Any = None,
        **extra: Any,
    ) -> "ToolEvent":
        """Create a tool.completed event."""
        return cls(
            source=source,
            type="completed",
            payload={
                "tool_name": tool_name,
                "task_id": task_id,
                "worker_id": worker_id,
                "result": result,
                **extra,
            },
        )
    
    @classmethod
    def denied(
        cls,
        source: str,
        tool_name: str,
        task_id: str = "",
        worker_id: str = "",
        reason: str = "",
        policy: str = "",
        **extra: Any,
    ) -> "ToolEvent":
        """Create a tool.denied event."""
        return cls(
            source=source,
            type="denied",
            payload={
                "tool_name": tool_name,
                "task_id": task_id,
                "worker_id": worker_id,
                "reason": reason,
                "policy": policy,
                **extra,
            },
        )
    
    @property
    def tool_name(self) -> str | None:
        """Extract tool_name from payload."""
        return self.payload.get("tool_name")
    
    @property
    def task_id(self) -> str | None:
        """Extract task_id from payload."""
        return self.payload.get("task_id")
    
    @property
    def worker_id(self) -> str | None:
        """Extract worker_id from payload."""
        return self.payload.get("worker_id")
    
    @property
    def result(self) -> Any:
        """Extract result from payload (for completed events)."""
        return self.payload.get("result")
    
    @property
    def reason(self) -> str | None:
        """Extract reason from payload (for denied events)."""
        return self.payload.get("reason")
    
    @property
    def policy(self) -> str | None:
        """Extract policy from payload (for denied events)."""
        return self.payload.get("policy")
