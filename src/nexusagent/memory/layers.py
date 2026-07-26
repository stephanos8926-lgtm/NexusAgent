"""Memory layer taxonomy and backend protocol for Phase 9 Memory Evolution.

Four-layer architecture:
- Working: current execution context, session-lifetime, ephemeral
- Episodic: historical events/sessions, append-only, permanent
- Semantic: stable facts, curated, verified before write
- Procedural: skills/workflows, evolved through use

Every memory item carries:
- source: which agent/session created it
- confidence: how reliable it is (0.0-1.0)
- authority: trust level of the source
- timestamp: when it was observed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from nexusagent.core.trust import TrustLevel

if TYPE_CHECKING:
    from nexusagent.memory.memory_item import MemoryItem


class MemoryLayer(str, Enum):
    """Canonical memory layers."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class ConfidenceAction(str, Enum):
    """What to do when evaluating a memory's confidence."""

    ACCEPT = "accept"
    NEEDS_REVIEW = "needs_review"
    REJECT = "reject"
    PROMOTE = "promote"


@dataclass(frozen=True)
class MemoryProvenance:
    """Source identity for a memory item."""

    source: str = ""
    authority: TrustLevel = TrustLevel.UNTRUSTED
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "authority": self.authority.value,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryProvenance:
        return cls(
            source=data.get("source", ""),
            authority=TrustLevel(data.get("authority", TrustLevel.UNTRUSTED.value)),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
            session_id=data.get("session_id", ""),
        )


@dataclass
class LayerMemoryItem:
    """Memory item with layer-specific metadata."""

    item: MemoryItem
    layer: MemoryLayer = MemoryLayer.EPISODIC
    provenance: MemoryProvenance = field(default_factory=MemoryProvenance)
    confidence: float = 0.5
    min_confidence: float = 0.3
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def can_promote(self) -> bool:
        """Whether this item is eligible for promotion to a higher-trust layer."""
        return self.confidence >= self.min_confidence

    def effective_authority(self) -> TrustLevel:
        """Highest authority allowed by both item provenance and layer rules."""
        layer_caps = {
            MemoryLayer.WORKING: TrustLevel.TRUSTED,
            MemoryLayer.EPISODIC: TrustLevel.TOOL_INTERNAL,
            MemoryLayer.SEMANTIC: TrustLevel.TRUSTED,
            MemoryLayer.PROCEDURAL: TrustLevel.TOOL_INTERNAL,
        }
        cap = layer_caps[self.layer]
        return TrustLevel(min(self.provenance.authority.value, cap.value))


@runtime_checkable
class LayerBackend(Protocol):
    """Protocol for memory layer backends."""

    layer: MemoryLayer

    def put(self, item: LayerMemoryItem) -> str:
        """Persist a memory item. Returns the item id."""
        ...

    def get(self, item_id: str) -> LayerMemoryItem | None:
        """Retrieve a memory item by id."""
        ...

    def query(self, text: str, *, limit: int = 10) -> list[LayerMemoryItem]:
        """Find items similar to text."""
        ...

    def delete(self, item_id: str) -> bool:
        """Delete a memory item. Episodic/Semantic may refuse."""
        ...
