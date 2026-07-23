"""Phase 8: Capability Security Model for NexusAgent.

Defines the CapabilityRouter, mapping tools to capabilities and gating access.
"""

from __future__ import annotations

import logging
from typing import Any

from nexusagent.security.audit import audit_denial_sync, audit_grant_sync
from nexusagent.security.policy import PolicyEngine

logger = logging.getLogger("nexusagent.security.router")

# Map of standard built-in tools to their required capabilities
TOOL_CAPABILITIES: dict[str, str] = {
    # filesystem.read
    "read_file": "filesystem.read",
    "read_multiple_files": "filesystem.read",
    "list_directory": "filesystem.read",
    "search_code": "filesystem.read",
    "find_symbol": "filesystem.read",
    "find_references": "filesystem.read",
    "git_status": "filesystem.read",
    "git_diff": "filesystem.read",
    "git_log": "filesystem.read",
    "git_branch": "filesystem.read",
    "git_show": "filesystem.read",
    "git_stash_list": "filesystem.read",
    "search_local_docs": "filesystem.read",
    "memory_get": "filesystem.read",
    "memory_search": "filesystem.read",
    "memory_index_search": "filesystem.read",
    "memory_list": "filesystem.read",
    "memory_health": "filesystem.read",
    # filesystem.write
    "write_file": "filesystem.write",
    "write_multiple_files": "filesystem.write",
    "edit_file": "filesystem.write",
    "apply_patch": "filesystem.write",
    "memory_write": "filesystem.write",
    "memory_update": "filesystem.write",
    "memory_delete": "filesystem.write",
    "memory_prune": "filesystem.write",
    "memory_consolidate": "filesystem.write",
    "memory_index_rebuild": "filesystem.write",
    "memory_dream": "filesystem.write",
    # execute.tests
    "run_tests": "execute.tests",
    "run_single_test": "execute.tests",
    # git.commit
    "git_commit": "git.commit",
    "git_checkout_branch": "git.commit",
    "git_stash_push": "git.commit",
    "git_stash_pop": "git.commit",
    # network.access
    "search_web": "network.access",
    "fetch_url": "network.access",
    # shell.execute
    "run_shell": "shell.execute",
    "run_shell_streaming": "shell.execute",
}

# Suspicious/reserved prefixes for dynamic capability gating
_RESERVED_PREFIXES = (
    "system__",
    "internal__",
    "admin__",
    "root__",
    "ignore_",
    "override_",
    "bypass_",
    "inject_",
    "hack_",
    "system_prompt",
    "instructions",
    "override",
    "new_instructions",
    "system_override",
)

# Blocklisted/injection tool names for dynamic capability gating
_INJECTION_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "system_prompt",
        "instructions",
        "override",
        "inject",
        "system_override",
        "new_instructions",
        "ignore_all",
        "forget_instructions",
        "pretend",
        "impersonate",
    }
)


def get_required_capability(tool_name: str) -> str | None:
    """Determine the required capability for a tool.

    If tool name matches standard tools, returns standard capability.
    If tool name is custom/MCP but starts with reserved prefix or belongs to injection tools,
    it is dynamically gated with shell.execute (critical risk level).
    """
    if tool_name in TOOL_CAPABILITIES:
        return TOOL_CAPABILITIES[tool_name]

    # Dynamic capability gating for custom/MCP tools
    for prefix in _RESERVED_PREFIXES:
        if tool_name.startswith(prefix):
            return "shell.execute"

    if tool_name in _INJECTION_TOOL_NAMES:
        return "shell.execute"

    return None


class CapabilityRouter:
    """Intercepts tool execution requests and mediates access via PolicyEngine."""

    def __init__(self, policy_engine: PolicyEngine | None = None) -> None:
        self.policy_engine = policy_engine or PolicyEngine()

    def check_access(
        self,
        tool_name: str,
        resource_scope: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Check if the current context has permission to execute the specified tool.

        Returns:
            (allowed: bool, reason: str)
        """
        # Load active policy context if not explicitly passed
        if context is None:
            from nexusagent.tools.registry.policy import _get_ctx

            context = _get_ctx()

        agent_id = context.get("session_id", "unknown-session")

        cap_name = get_required_capability(tool_name)
        if cap_name is None:
            # Unguarded tools require no capability and are always allowed
            return True, ""

        allowed, rule_triggered = self.policy_engine.evaluate(context, cap_name, resource_scope)

        if allowed:
            # Log successful grant in audit trail
            audit_grant_sync(
                agent_id=agent_id,
                capability=cap_name,
                scope=resource_scope or "Workspace directory",
                rule=rule_triggered,
                tool_name=tool_name,
            )
            return True, ""
        else:
            # Log denial in audit trail
            audit_denial_sync(
                agent_id=agent_id,
                capability=cap_name,
                scope=resource_scope or "Workspace directory",
                rule=rule_triggered,
                reason=rule_triggered,
                tool_name=tool_name,
            )
            return False, rule_triggered


# Global CapabilityRouter singleton
router = CapabilityRouter()
