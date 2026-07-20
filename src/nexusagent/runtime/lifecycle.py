"""Lifecycle state machine for runtime components.

Provides a universal lifecycle model used by every managed component
in the NexusAgent runtime. All components follow the same 7-state
machine with observable transitions and health reporting.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# Valid transition map: source → set of allowed target values
_LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "created": {"initializing"},
    "initializing": {"running", "failed"},
    "running": {"paused", "failed", "terminated"},
    "paused": {"running", "failed"},
    "failed": {"terminated"},
    "completed": {"terminated"},
    "terminated": set(),  # terminal
}


class LifecycleState(str, enum.Enum):
    """Universal 7-state lifecycle for runtime components.

    Transitions:
        CREATED → INITIALIZING → RUNNING → (PAUSED | FAILED) → ...

    Invalid transitions (these raise ValueError):
        CREATED → TERMINATED       (must go through RUNNING)
        RUNNING → CREATED          (no going back)
        TERMINATED → any           (terminal state)
    """

    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"
    TERMINATED = "terminated"

    def can_transition_to(self, target: LifecycleState) -> bool:
        """Check if a transition from this state to target is valid."""
        return target.value in _LIFECYCLE_TRANSITIONS.get(self.value, set())

    def transition_to(self, target: LifecycleState) -> None:
        """Validate and perform a state transition. Raises ValueError if invalid."""
        if not self.can_transition_to(target):
            raise ValueError(
                f"Invalid lifecycle transition: {self.value} → {target.value}. "
                f"Allowed targets from {self.value}: "
                f"{_LIFECYCLE_TRANSITIONS.get(self.value, set()) or '(none — terminal)'}"
            )


@dataclass
class HealthStatus:
    """Health snapshot for a runtime component."""

    healthy: bool = True
    degraded: bool = False
    failed: bool = False
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.failed:
            return "failed"
        if self.degraded:
            return "degraded"
        if self.healthy:
            return "healthy"
        return "unknown"


class LifecycleMixin(ABC):
    """Abstract base for all runtime components with observable lifecycle.

    Every managed component implements this interface, providing:
    - An observable state machine
    - Async initialize/shutdown with proper transitions
    - A health snapshot for monitoring
    """

    @property
    @abstractmethod
    def state(self) -> LifecycleState:
        """Current lifecycle state of this component."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the component. Must transition to RUNNING on success."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the component. Must transition to TERMINATED on completion."""

    @abstractmethod
    def health(self) -> HealthStatus:
        """Return a health snapshot of this component."""
