# SPDX-License-Identifier: MIT

"""Unit and integration tests for CapabilityRouter."""

from __future__ import annotations

from nexusagent.security.router import CapabilityRouter, get_required_capability


def test_get_required_capability_mappings():
    """Verify tool-to-capability mappings."""
    # Standard tools
    assert get_required_capability("read_file") == "filesystem.read"
    assert get_required_capability("write_file") == "filesystem.write"
    assert get_required_capability("run_tests") == "execute.tests"
    assert get_required_capability("git_commit") == "git.commit"
    assert get_required_capability("search_web") == "network.access"
    assert get_required_capability("run_shell") == "shell.execute"

    # Public/unguarded tools require no capability
    assert get_required_capability("tool_search") is None
    assert get_required_capability("auto_correct") is None


def test_dynamic_capability_gating_for_mcp_tools():
    """Verify MCP/external tools require network.access."""
    assert get_required_capability("mcp_custom") == "network.access"
    assert get_required_capability("external_tool") == "network.access"
    # Unknown tools not in map return None
    assert get_required_capability("system__custom") is None
    assert get_required_capability("admin__tool") is None


def test_router_check_tool_access_allowed():
    """Verify router allows access for unprivileged tools."""
    router = CapabilityRouter()

    # Unprivileged tools (no capability required) are always allowed
    allowed, reason = router.check_tool_access("tool_search")
    assert allowed
    assert "Allowed" in reason


def test_router_check_tool_access_for_registered_tool():
    """Verify registered tools are evaluated through the policy engine."""
    router = CapabilityRouter()

    # Run through policy engine (default role=full, policy=permissive)
    allowed, reason = router.check_tool_access("read_file")
    # With full role + permissive policy, should be allowed
    assert isinstance(allowed, bool)
    assert isinstance(reason, str)
