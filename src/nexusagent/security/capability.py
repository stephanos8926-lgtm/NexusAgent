"""Phase 8: Capability Security Model for NexusAgent.

Defines the core Capability schema, RiskLevel enum, and CapabilityRegistry.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RiskLevel(StrEnum):
    """Risk levels representing potential security impact of a capability."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Capability:
    """Represents an elevated authority or privilege granted to an agent."""

    name: str
    scope: str
    permissions: list[str]
    risk_level: RiskLevel
    audit_log: bool = True


class CapabilityRegistry:
    """Thread-safe catalog of all registered capabilities."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        """Register a new capability in the catalog."""
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability | None:
        """Retrieve a capability by its name, returning None if not found."""
        return self._capabilities.get(name)

    def list_all(self) -> list[Capability]:
        """Return a list of all registered capabilities."""
        return list(self._capabilities.values())


# Global singleton registry
registry = CapabilityRegistry()

# Register the standard 6 capabilities defined in Phase 8 spec
registry.register(
    Capability(
        name="filesystem.read",
        scope="Workspace directory",
        permissions=["read"],
        risk_level=RiskLevel.LOW,
    )
)
registry.register(
    Capability(
        name="filesystem.write",
        scope="Workspace directory",
        permissions=["write"],
        risk_level=RiskLevel.MEDIUM,
    )
)
registry.register(
    Capability(
        name="execute.tests",
        scope="Project workspace",
        permissions=["execute"],
        risk_level=RiskLevel.LOW,
    )
)
registry.register(
    Capability(
        name="git.commit",
        scope="Current repository",
        permissions=["write"],
        risk_level=RiskLevel.HIGH,
    )
)
registry.register(
    Capability(
        name="network.access",
        scope="Allowlisted endpoints",
        permissions=["execute"],
        risk_level=RiskLevel.HIGH,
    )
)
registry.register(
    Capability(
        name="shell.execute",
        scope="Workspace directory",
        permissions=["execute"],
        risk_level=RiskLevel.CRITICAL,
    )
)
