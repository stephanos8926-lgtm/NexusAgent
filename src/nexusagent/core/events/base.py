"""Base SystemEvent class and event types.

Defines the fundamental event schema with required fields:
- id: unique event identifier (UUID)
- timestamp: ISO-8601 formatted datetime
- source: component identity that emitted the event
- type: event category and specific type
- payload: type-specific data
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar


class EventType(Enum):
    """Base event type categories."""

    TASK = "task"
    WORKER = "worker"
    TOOL = "tool"
    POLICY = "policy"


@dataclass
class SystemEvent:
    """Base class for all system events.

    Every event requires:
    - id: unique UUID identifier
    - timestamp: ISO-8601 formatted datetime
    - source: component identity (e.g., "worker-abc123", "task-xyz789")
    - type: event category (from EventType) and specific subtype
    - payload: type-specific data dictionary
    """

    # Class-level configuration
    category: ClassVar[EventType]  # Override in subclasses

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    type: str = ""  # Specific event type (e.g., "task.created")
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and set default type from category."""
        if not self.type:
            # Default type is category.value if not specified
            self.type = self.category.value

    @property
    def nats_subject(self) -> str:
        """Return the NATS subject for this event.

        Format: nexus.{category}.{type}
        e.g., nexus.task.created, nexus.worker.started
        """
        return f"nexus.{self.category.value}.{self.type}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime to ISO format string
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemEvent:
        """Deserialize event from dictionary."""
        return cls(
            id=data.get("id", uuid.uuid4().hex),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", datetime.now(UTC)),
            source=data.get("source", ""),
            type=data.get("type", ""),
            payload=data.get("payload", {}),
        )

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        import json

        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> SystemEvent:
        """Deserialize event from JSON string."""
        import json

        return cls.from_dict(json.loads(json_str))
