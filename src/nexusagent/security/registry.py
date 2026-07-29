# src/nexusagent/security/registry.py
"""Registry of defined capabilities and tool-to-capability mappings."""

from __future__ import annotations

from .models import Capability, Permission, RiskLevel

# Standard catalog of system capabilities as defined in Phase 8 specifications
CAPABILITIES = {
    "filesystem.read": Capability(
        name="filesystem.read",
        permissions=[Permission.READ],
        risk_level=RiskLevel.LOW,
        scope="workspace",
    ),
    "filesystem.write": Capability(
        name="filesystem.write",
        permissions=[Permission.WRITE],
        risk_level=RiskLevel.MEDIUM,
        scope="workspace",
    ),
    "execute.tests": Capability(
        name="execute.tests",
        permissions=[Permission.EXECUTE],
        risk_level=RiskLevel.LOW,
        scope="workspace",
    ),
    "git.commit": Capability(
        name="git.commit",
        permissions=[Permission.WRITE, Permission.EXECUTE],
        risk_level=RiskLevel.HIGH,
        scope="workspace",
    ),
    "network.access": Capability(
        name="network.access",
        permissions=[Permission.EXECUTE],
        risk_level=RiskLevel.HIGH,
        scope="network",
    ),
    "shell.execute": Capability(
        name="shell.execute",
        permissions=[Permission.EXECUTE],
        risk_level=RiskLevel.CRITICAL,
        scope="workspace",
    ),
}

# Explicit mapping from registered tool names to required capability constraints
TOOL_CAPABILITY_MAP = {
    # File & Search Read Tools
    "read_file": "filesystem.read",
    "read_multiple_files": "filesystem.read",
    "list_directory": "filesystem.read",
    "search_code": "filesystem.read",
    "search_local_docs": "filesystem.read",
    "find_symbol": "filesystem.read",
    "find_references": "filesystem.read",
    "git_status": "filesystem.read",
    "git_diff": "filesystem.read",
    "git_log": "filesystem.read",
    "git_show": "filesystem.read",
    "git_stash_list": "filesystem.read",
    "memory_get": "filesystem.read",
    "memory_search": "filesystem.read",
    "memory_index_search": "filesystem.read",
    "memory_list": "filesystem.read",
    "memory_health": "filesystem.read",

    # File & Memory Writing/Mutating Tools
    "write_file": "filesystem.write",
    "write_multiple_files": "filesystem.write",
    "edit_file": "filesystem.write",
    "apply_patch": "filesystem.write",
    "write_todos": "filesystem.write",
    "memory_write": "filesystem.write",
    "memory_update": "filesystem.write",
    "memory_delete": "filesystem.write",
    "memory_prune": "filesystem.write",
    "memory_consolidate": "filesystem.write",
    "memory_dream": "filesystem.write",

    # Test Execution Tools
    "run_tests": "execute.tests",
    "run_single_test": "execute.tests",

    # Git Committing & Branching Tools
    "git_commit": "git.commit",
    "git_checkout_branch": "git.commit",
    "git_stash_push": "git.commit",
    "git_stash_pop": "git.commit",

    # Web & API Access Tools
    "search_web": "network.access",

    # Shell Execution Tools
    "run_shell": "shell.execute",
    "run_shell_streaming": "shell.execute",
}


class CapabilityRegistry:
    """Registry that manages security capability definitions and tool constraints."""

    def __init__(self) -> None:
        self._capabilities = CAPABILITIES.copy()
        self._tool_map = TOOL_CAPABILITY_MAP.copy()

    def get_capability(self, name: str) -> Capability | None:
        """Retrieve capability definition by name."""
        return self._capabilities.get(name)

    def get_required_capability(self, tool_name: str) -> str | None:
        """Retrieve required capability identifier for a tool."""
        # Handle dynamic MCP/external tools dynamically, routing them under network.access
        if tool_name.startswith("mcp_") or tool_name.startswith("external_"):
            return "network.access"
        return self._tool_map.get(tool_name)


def get_required_capability(tool_name: str) -> str | None:
    """Module-level convenience: retrieve required capability for a tool."""
    return get_capability_registry().get_required_capability(tool_name)


# Global singleton pattern
_registry_instance: CapabilityRegistry | None = None


def get_capability_registry() -> CapabilityRegistry:
    """Get the global CapabilityRegistry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = CapabilityRegistry()
    return _registry_instance
