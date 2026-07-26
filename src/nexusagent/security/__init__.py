"""Phase 8: Capability Security Model for NexusAgent.

Public API exports.
"""

from nexusagent.security.audit import (
    audit_denial,
    audit_denial_sync,
    audit_grant,
    audit_grant_sync,
)
from nexusagent.security.capability import (
    Capability,
    CapabilityRegistry,
    RiskLevel,
    registry,
)
from nexusagent.security.policy import ROLE_CAPABILITIES, PolicyEngine
from nexusagent.security.router import (
    CapabilityRouter,
    get_required_capability,
    router,
)

__all__ = [
    "ROLE_CAPABILITIES",
    "Capability",
    "CapabilityRegistry",
    "CapabilityRouter",
    "PolicyEngine",
    "RiskLevel",
    "audit_denial",
    "audit_denial_sync",
    "audit_grant",
    "audit_grant_sync",
    "get_required_capability",
    "registry",
    "router",
]
