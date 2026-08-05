# SPDX-License-Identifier: MIT

# tests/core/test_security.py
"""Comprehensive unit tests for the Phase 8 Capability Security Model."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.core.events import PolicyEvent, set_emitter
from nexusagent.security.engine import get_policy_engine
from nexusagent.security.models import Capability, Permission, RiskLevel
from nexusagent.security.registry import get_capability_registry
from nexusagent.security.router import (
    log_audit_event_async,
    log_audit_event_sync,
)
from nexusagent.tools.register_all import register_all
from nexusagent.tools.registry.policy import (
    _is_tool_allowed,
    clear_policy_context,
    set_policy_context,
)


def test_capability_models():
    """Test validation and properties of Capability models."""
    cap = Capability(
        name="filesystem.read",
        permissions=[Permission.READ],
        risk_level=RiskLevel.LOW,
        scope="workspace",
    )
    assert cap.name == "filesystem.read"
    assert Permission.READ in cap.permissions
    assert cap.risk_level == RiskLevel.LOW


def test_capability_registry_resolution():
    """Test standard capability definition lookup and tool constraint resolution."""
    registry = get_capability_registry()

    # Verify standard capabilities exist
    fs_read = registry.get_capability("filesystem.read")
    assert fs_read is not None
    assert fs_read.risk_level == RiskLevel.LOW

    shell_execute = registry.get_capability("shell.execute")
    assert shell_execute is not None
    assert shell_execute.risk_level == RiskLevel.CRITICAL

    # Verify tool-to-capability mappings
    assert registry.get_required_capability("read_file") == "filesystem.read"
    assert registry.get_required_capability("write_file") == "filesystem.write"
    assert registry.get_required_capability("run_shell") == "shell.execute"
    assert registry.get_required_capability("run_tests") == "execute.tests"

    # MCP tools are mapped under network.access dynamically
    assert registry.get_required_capability("mcp_custom_tool") == "network.access"
    assert registry.get_required_capability("external_cool_tool") == "network.access"


def test_policy_engine_role_evaluation():
    """Test PolicyEngine role capabilities under restricted and strict modes."""
    engine = get_policy_engine()

    # 1. Minimal role gets only read access
    allowed, _ = engine.evaluate_capability(
        session_id="sess-1",
        role="minimal",
        policy_mode="restricted",
        capability_name="filesystem.read",
    )
    assert allowed
    allowed, _ = engine.evaluate_capability(
        session_id="sess-1",
        role="minimal",
        policy_mode="restricted",
        capability_name="filesystem.write",
    )
    assert not allowed

    # 2. Coder role gets full capabilities
    for cap in [
        "filesystem.read",
        "filesystem.write",
        "execute.tests",
        "git.commit",
        "network.access",
        "shell.execute",
    ]:
        allowed, _ = engine.evaluate_capability(
            session_id="sess-1", role="coder", policy_mode="restricted", capability_name=cap
        )
        assert allowed

    # 3. Tester gets read, write, tests, shell but no git or network
    for cap in ["filesystem.read", "filesystem.write", "execute.tests", "shell.execute"]:
        allowed, _ = engine.evaluate_capability(
            session_id="sess-1", role="tester", policy_mode="restricted", capability_name=cap
        )
        assert allowed

    allowed, _ = engine.evaluate_capability(
        session_id="sess-1", role="tester", policy_mode="restricted", capability_name="git.commit"
    )
    assert not allowed


def test_policy_engine_policy_modes():
    """Test PolicyEngine with Permissive, Restricted, and Strict policy modes."""
    engine = get_policy_engine()

    # Permissive: Allows everything
    allowed, _ = engine.evaluate_capability(
        session_id="sess-2",
        role="minimal",
        policy_mode="permissive",
        capability_name="shell.execute",
    )
    assert allowed

    # Restricted: Only allows base grants or administrative overrides
    allowed, _ = engine.evaluate_capability(
        session_id="sess-2",
        role="minimal",
        policy_mode="restricted",
        capability_name="shell.execute",
    )
    assert not allowed

    # Strict: Only allows exact base role capabilities
    allowed, _ = engine.evaluate_capability(
        session_id="sess-2", role="coder", policy_mode="strict", capability_name="shell.execute"
    )
    assert allowed
    allowed, _ = engine.evaluate_capability(
        session_id="sess-2", role="minimal", policy_mode="strict", capability_name="shell.execute"
    )
    assert not allowed


def test_dynamic_administrative_overrides():
    """Test runtime dynamic administrative capability grants and revocations on sessions."""
    engine = get_policy_engine()
    session_id = "sess-dynamic-123"

    # Base role "minimal" has filesystem.read but no filesystem.write
    allowed, _ = engine.evaluate_capability(
        session_id=session_id,
        role="minimal",
        policy_mode="restricted",
        capability_name="filesystem.write",
    )
    assert not allowed

    # Dynamic administrative grant
    engine.grant_capability(session_id, "filesystem.write")

    allowed, _ = engine.evaluate_capability(
        session_id=session_id,
        role="minimal",
        policy_mode="restricted",
        capability_name="filesystem.write",
    )
    assert allowed

    # Dynamic administrative revocation
    engine.revoke_capability(session_id, "filesystem.write")

    allowed, _ = engine.evaluate_capability(
        session_id=session_id,
        role="minimal",
        policy_mode="restricted",
        capability_name="filesystem.write",
    )
    assert not allowed

    # Strict policy mode ignores overrides
    engine.grant_capability(session_id, "filesystem.write")
    allowed, _ = engine.evaluate_capability(
        session_id=session_id,
        role="minimal",
        policy_mode="strict",
        capability_name="filesystem.write",
    )
    assert not allowed


@pytest.mark.asyncio
async def test_audit_trail_logging():
    """Test that capability evaluations publish correct sync/async PolicyEvents."""
    mock_emitter = MagicMock()
    set_emitter(mock_emitter)

    # Test sync audit logging
    log_audit_event_sync(
        source="CapabilityRouter",
        action="capability.filesystem.read",
        allowed=True,
        reason="Granted by default",
        role="coder",
        policy="restricted",
        resource="workspace",
        tool_name="read_file",
        task_id="task-001",
    )

    assert mock_emitter.emit_sync.call_count == 1
    event = mock_emitter.emit_sync.call_args[0][0]
    assert isinstance(event, PolicyEvent)
    assert event.type == "allowed"
    assert event.payload["action"] == "capability.filesystem.read"
    assert event.payload["tool_name"] == "read_file"
    assert event.payload["task_id"] == "task-001"

    # Test async audit logging
    mock_emitter.reset_mock()
    mock_emitter.emit = AsyncMock()

    await log_audit_event_async(
        source="CapabilityRouter",
        action="capability.filesystem.write",
        allowed=False,
        reason="Denied by default",
        role="minimal",
        policy="restricted",
        resource="workspace",
        tool_name="write_file",
        task_id="task-002",
    )

    assert mock_emitter.emit.call_count == 1
    event = mock_emitter.emit.call_args[0][0]
    assert isinstance(event, PolicyEvent)
    assert event.type == "denied"
    assert event.payload["action"] == "capability.filesystem.write"
    assert event.payload["reason"] == "Denied by default"
    assert event.payload["task_id"] == "task-002"

    # Clean up emitter
    set_emitter(None)


def test_capability_router_tool_integration():
    """Test the end-to-end integration where tool checks invoke the CapabilityRouter."""
    # Ensure static tools are registered so _is_tool_allowed checks do not bail early
    register_all()
    clear_policy_context()

    # 1. Under permissive policy context, writing is allowed even for reader role
    set_policy_context(role="reader", policy="permissive")
    allowed, _ = _is_tool_allowed("write_file")
    assert allowed

    # 2. Under restricted policy context, writing is denied for reader role
    set_policy_context(role="reader", policy="restricted")
    allowed, reason = _is_tool_allowed("write_file")
    assert not allowed
    assert "ACCESS DENIED" in reason
    assert "filesystem.write" in reason

    # 3. Reading is allowed for reader role
    allowed, _ = _is_tool_allowed("read_file")
    assert allowed

    clear_policy_context()


@pytest.mark.asyncio
async def test_api_endpoints_integration():
    """Test REST endpoints for managing dynamic capabilities in active sessions."""
    from fastapi.testclient import TestClient

    from nexusagent.infrastructure.api_auth import require_admin, verify_api_key
    from nexusagent.server.server import app

    # Apply FastAPI dependency overrides to bypass authentication
    app.dependency_overrides[verify_api_key] = lambda: None
    app.dependency_overrides[require_admin] = lambda: None

    client = TestClient(app)
    headers = {"x-api-key": "admin_test_key_placeholder"}

    try:
        session_id = "test-api-session-id"

        # 1. GET active capabilities
        response = client.get(f"/security/sessions/{session_id}/capabilities", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "capabilities" in data

        # 2. POST grant dynamic capability
        response = client.post(
            f"/security/sessions/{session_id}/capabilities/grant",
            json={"capability": "shell.execute"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "granted"

        # Verify it has been added
        response = client.get(f"/security/sessions/{session_id}/capabilities", headers=headers)
        assert "shell.execute" in response.json()["capabilities"]

        # 3. POST revoke dynamic capability
        response = client.post(
            f"/security/sessions/{session_id}/capabilities/revoke",
            json={"capability": "shell.execute"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "revoked"

        # Verify it is no longer granted
        response = client.get(f"/security/sessions/{session_id}/capabilities", headers=headers)
        assert "shell.execute" not in response.json()["capabilities"]

    finally:
        # Clear the dependency overrides
        app.dependency_overrides.clear()
