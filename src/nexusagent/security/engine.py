# SPDX-License-Identifier: MIT

# src/nexusagent/security/engine.py
"""Policy engine evaluating capability grants/revocations and role mappings."""

from __future__ import annotations

import logging
import threading

from .registry import get_capability_registry

logger = logging.getLogger(__name__)

# Thread-safe lock and dictionary storing dynamic overrides per active session
# Overrides map capability names to boolean grants (True = granted, False = revoked)
_active_grants_lock = threading.RLock()
_active_grants: dict[str, dict[str, bool]] = {}

# Default role mapping to capability grants as specified in Phase 8
DEFAULT_ROLE_GRANTS = {
    "minimal": {
        "filesystem.read",
    },
    "reader": {
        "filesystem.read",
        "network.access",
    },
    "writer": {
        "filesystem.read",
        "filesystem.write",
    },
    "reviewer": {
        "filesystem.read",
        "execute.tests",
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
    "full": {
        "filesystem.read",
        "filesystem.write",
        "execute.tests",
        "git.commit",
        "network.access",
        "shell.execute",
    },
}


class PolicyEngine:
    """Evaluates dynamic capability grants and revocations against security policies."""

    def __init__(self) -> None:
        self.role_grants = DEFAULT_ROLE_GRANTS.copy()

    def grant_capability(self, session_id: str, capability_name: str) -> None:
        """Dynamically grant a specific capability to a session."""
        with _active_grants_lock:
            if session_id not in _active_grants:
                _active_grants[session_id] = {}
            _active_grants[session_id][capability_name] = True
            logger.info(
                f"Dynamically granted capability '{capability_name}' to session '{session_id}'"
            )

    def revoke_capability(self, session_id: str, capability_name: str) -> None:
        """Dynamically revoke a specific capability from a session."""
        with _active_grants_lock:
            if session_id not in _active_grants:
                _active_grants[session_id] = {}
            _active_grants[session_id][capability_name] = False
            logger.info(
                f"Dynamically revoked capability '{capability_name}' from session '{session_id}'"
            )

    def get_session_capabilities(
        self, session_id: str | None, role: str, policy_mode: str
    ) -> list[str]:
        """List all capabilities currently active/granted to a session."""
        base_grants = set(self.role_grants.get(role, self.role_grants["minimal"]))
        if role == "full":
            base_grants = set(self.role_grants["full"])

        if policy_mode == "strict":
            # strict mode ignores dynamic administrative grants/revocations
            return sorted(list(base_grants))

        # Merge base grants with dynamic overrides for non-strict modes
        final_grants = base_grants.copy()
        if session_id:
            with _active_grants_lock:
                session_overrides = _active_grants.get(session_id, {})
            for cap, allowed in session_overrides.items():
                if allowed:
                    final_grants.add(cap)
                else:
                    final_grants.discard(cap)

        return sorted(list(final_grants))

    def evaluate_capability(
        self,
        session_id: str | None,
        role: str,
        policy_mode: str,
        capability_name: str,
        tool_name: str = "",
    ) -> tuple[bool, str]:
        """Evaluate if a capability/tool is allowed under the current security context."""
        registry = get_capability_registry()
        cap_info = registry.get_capability(capability_name)
        if not cap_info:
            return False, f"Capability '{capability_name}' is not registered."

        # Delayed imports to avoid circular dependency
        from nexusagent.tools.registry.policy import _get_ctx, get_manifest

        ctx = _get_ctx()
        unlocked = ctx.get("unlocked", set())
        manifest = get_manifest(role)

        # Fallback if no specific tool name is passed (raw capability check)
        if not tool_name:
            if policy_mode == "permissive":
                return True, "Allowed (permissive policy mode)"

            base_grants = self.role_grants.get(role, self.role_grants["minimal"])
            if role == "full":
                base_grants = self.role_grants["full"]

            if policy_mode == "strict":
                if capability_name in base_grants:
                    return True, f"Allowed by base role '{role}' in strict mode"
                return (
                    False,
                    f"Capability '{capability_name}' is not allowed for role '{role}' in strict mode",
                )

            if session_id:
                with _active_grants_lock:
                    session_overrides = _active_grants.get(session_id, {})
                if capability_name in session_overrides:
                    if session_overrides[capability_name]:
                        return True, "Allowed by administrative dynamic grant"
                    return False, "Denied by administrative dynamic revocation"

            if capability_name in base_grants:
                return True, f"Allowed by base role '{role}' in restricted mode"

            return (
                False,
                f"Capability '{capability_name}' is not granted to role '{role}' in restricted mode",
            )

        # 1. Permissive policy mode: all registered capabilities/tools allowed by default (adds to unlocked)
        if policy_mode == "permissive":
            unlocked.add(tool_name)
            return True, "Allowed (permissive policy mode)"

        # 2. Strict policy mode: only exact manifest allowed (overrides and unlocking ignored)
        if policy_mode == "strict":
            if tool_name in manifest:
                return True, f"Allowed by base role '{role}' in strict mode"
            return False, (
                f"Tool '{tool_name}' is not available in strict mode for role '{role}'. "
                f"You are locked to your initial tool set."
            )

        # 3. Restricted policy mode: respect dynamic overrides, fallback to manifest/unlocked tools
        if session_id:
            with _active_grants_lock:
                session_overrides = _active_grants.get(session_id, {})
            if capability_name in session_overrides:
                if session_overrides[capability_name]:
                    return True, "Allowed by administrative dynamic grant"
                return False, f"Tool '{tool_name}' denied by administrative dynamic revocation"

        # Fallback to base manifest or unlocked set for restricted mode
        if tool_name in manifest or tool_name in unlocked:
            return True, f"Allowed by base role '{role}' / unlocked tools"

        return False, (
            f"Tool '{tool_name}' is not in your role manifest for '{role}'. "
            f"Use tool_search() to find appropriate tools."
        )


# Global singleton pattern
_engine_instance: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    """Get the global PolicyEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PolicyEngine()
    return _engine_instance
