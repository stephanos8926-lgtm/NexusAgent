"""Unit and integration tests for CapabilityRouter."""

from __future__ import annotations

import pytest

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


def test_dynamic_capability_gating_for_reserved_prefixes():
    """Verify custom/MCP tools with reserved prefixes require shell.execute."""
    assert get_required_capability("system__custom") == "shell.execute"
    assert get_required_capability("admin__tool") == "shell.execute"
    assert get_required_capability("bypass_auth") == "shell.execute"
    assert get_required_capability("inject_prompt") == "shell.execute"


def test_dynamic_capability_gating_for_injection_tools():
    """Verify custom/MCP tools matching injection blocklist require shell.execute."""
    assert get_required_capability("system_prompt") == "shell.execute"
    assert get_required_capability("override") == "shell.execute"
    assert get_required_capability("pretend") == "shell.execute"


def test_router_check_access_allowed():
    """Verify router allows access when capability is granted."""
    router = CapabilityRouter()

    # Coder role has filesystem.read and filesystem.write
    context = {"role": "coder", "policy": "strict", "unlocked": set()}
    allowed, reason = router.check_access("read_file", context=context)
    assert allowed
    assert reason == ""

    # Permissive mode auto-unlocks and allows
    context = {"role": "reader", "policy": "permissive", "unlocked": set()}
    allowed, reason = router.check_access("write_file", context=context)
    assert allowed
    assert "write_file" in context["unlocked"] or "filesystem.write" in context["unlocked"]


def test_router_check_access_denied():
    """Verify router denies access when capability is not granted."""
    router = CapabilityRouter()

    # Reader role in strict mode is denied writing
    context = {"role": "reader", "policy": "strict", "unlocked": set()}
    allowed, reason = router.check_access("write_file", context=context)
    assert not allowed
    assert "denied" in reason.lower()


def test_router_scope_checks():
    """Verify router performs scope validation."""
    router = CapabilityRouter()
    context = {"role": "coder", "policy": "strict", "unlocked": set()}

    # Allowed shell execution within workspace root
    allowed, reason = router.check_access("run_shell", resource_scope="ls -la", context=context)
    assert allowed

    # Denied shell execution outside workspace root
    allowed, reason = router.check_access("run_shell", resource_scope="cat ../../../etc/passwd", context=context)
    assert not allowed
    assert "outside workspace" in reason or "violation" in reason.lower()
