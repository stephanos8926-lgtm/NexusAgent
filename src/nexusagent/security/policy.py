"""Phase 8: Capability Security Model for NexusAgent.

Defines the PolicyEngine evaluating capability requests against current policy context.
"""

from __future__ import annotations

from typing import Any

from nexusagent.security.capability import registry as default_registry

# Mapping of standard developer roles to their default capability grants
ROLE_CAPABILITIES: dict[str, set[str]] = {
    "full": {
        "filesystem.read",
        "filesystem.write",
        "execute.tests",
        "git.commit",
        "network.access",
        "shell.execute",
    },
    "coder": {
        "filesystem.read",
        "filesystem.write",
        "execute.tests",
        "git.commit",
        "network.access",
        "shell.execute",
    },
    "tester": {
        "filesystem.read",
        "filesystem.write",
        "execute.tests",
        "shell.execute",
    },
    "reviewer": {
        "filesystem.read",
        "execute.tests",
    },
    "debugger": {
        "filesystem.read",
        "filesystem.write",
        "execute.tests",
        "shell.execute",
    },
    "researcher": {
        "filesystem.read",
        "network.access",
        "shell.execute",
    },
    "writer": {
        "filesystem.read",
        "filesystem.write",
    },
    "reader": {
        "filesystem.read",
        "network.access",
    },
    "minimal": set(),
}


class PolicyEngine:
    """Enforces role-based, mode-based, and scope-based security rules."""

    def __init__(self, registry: Any = None) -> None:
        self.registry = registry or default_registry

    def evaluate(
        self,
        context: dict[str, Any],
        capability_name: str,
        resource_scope: str | None = None,
    ) -> tuple[bool, str]:
        """Evaluate a capability request.

        Returns:
            (allowed: bool, rule_triggered: str)
        """
        role = context.get("role", "full")
        policy_mode = context.get("policy", "permissive")

        # Get set of unlocked capabilities from context (allows explicit dynamic grants)
        unlocked = context.get("unlocked")
        if unlocked is None:
            unlocked = set()
            context["unlocked"] = unlocked
        elif isinstance(unlocked, list):
            unlocked = set(unlocked)
            context["unlocked"] = unlocked

        # Verify capability exists
        cap = self.registry.get(capability_name)
        if not cap:
            return False, f"Capability '{capability_name}' does not exist in registry."

        role_caps = ROLE_CAPABILITIES.get(role, ROLE_CAPABILITIES["minimal"])

        is_allowed = False
        rule_triggered = ""

        # 1. Evaluate capability grant
        if capability_name in role_caps:
            is_allowed = True
            rule_triggered = f"Granted by role: '{role}'"
        elif capability_name in unlocked and policy_mode != "strict":
            is_allowed = True
            rule_triggered = "Granted by explicit unlock/operator authorization"
        elif policy_mode == "permissive":
            # Auto-unlock
            unlocked.add(capability_name)
            is_allowed = True
            rule_triggered = f"Auto-unlocked under '{policy_mode}' policy mode"
        else:
            is_allowed = False
            rule_triggered = f"Denied under '{policy_mode}' policy mode for role '{role}'"

        if not is_allowed:
            return False, rule_triggered

        # 2. Evaluate resource scope (utilize Phase 7 PolicyEvaluator)
        if resource_scope:
            from nexusagent.core.pol import PolicyEvaluator

            evaluator = PolicyEvaluator()

            if capability_name in ("shell.execute", "execute.tests"):
                allowed, reason = evaluator.evaluate_execution(resource_scope)
                if not allowed:
                    return False, f"Resource scope violation on command execution: {reason}"
            elif capability_name == "network.access":
                allowed, reason = evaluator.evaluate_network(resource_scope)
                if not allowed:
                    return False, f"Resource scope violation on network access: {reason}"

        return True, rule_triggered
