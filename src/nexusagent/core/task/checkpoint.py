"""Checkpoint dataclass and serialization/deserialization logic."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Checkpoint:
    """Captures the full execution state of a task at a point in time."""

    current_node: str
    completed_actions: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert Checkpoint to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        """Create a Checkpoint from a dictionary."""
        return cls(
            current_node=data.get("current_node", ""),
            completed_actions=list(data.get("completed_actions", [])),
            files_changed=list(data.get("files_changed", [])),
            tool_results=list(data.get("tool_results", [])),
            next_action=data.get("next_action", ""),
        )

    def serialize(self) -> str:
        """Serialize Checkpoint to a JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def deserialize(cls, json_str: str) -> Checkpoint:
        """Deserialize a JSON string to a Checkpoint."""
        data = json.loads(json_str)
        return cls.from_dict(data)
