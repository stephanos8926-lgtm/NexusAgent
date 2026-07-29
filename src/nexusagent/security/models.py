# src/nexusagent/security/models.py
"""Data models and enums representing capabilities and dynamic security state."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk levels representing the severity of a capability's potential impact."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Permission(str, Enum):
    """Core privileges that can be mapped to capabilities."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class Capability(BaseModel):
    """A privileged action definition under the Capability Security Model."""

    name: str = Field(..., description="Unique dotted-notation capability identifier")
    permissions: list[Permission] = Field(..., description="The concrete permissions granted by this capability")
    risk_level: RiskLevel = Field(..., description="The level of security risk associated with this capability")
    scope: str = Field(..., description="Defined execution boundaries, e.g. workspace, network")


class CapabilityGrant(BaseModel):
    """A record of a session or global level capability grant or revocation."""

    capability_name: str = Field(..., description="The target capability identifier")
    session_id: str | None = Field(None, description="The session boundary for this grant, or None for global")
    allowed: bool = Field(True, description="True if allowed/granted, False if explicitly revoked/denied")
