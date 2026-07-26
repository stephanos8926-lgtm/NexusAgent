"""Unit tests for Capability registry and lookup."""

from __future__ import annotations

from nexusagent.security.capability import Capability, CapabilityRegistry, RiskLevel


def test_capability_creation():
    """Verify that a Capability dataclass can be created and has correct fields."""
    cap = Capability(
        name="test.privilege",
        scope="Workspace directory",
        permissions=["read", "write"],
        risk_level=RiskLevel.MEDIUM,
        audit_log=True,
    )
    assert cap.name == "test.privilege"
    assert cap.scope == "Workspace directory"
    assert "read" in cap.permissions
    assert cap.risk_level == RiskLevel.MEDIUM
    assert cap.audit_log is True


def test_capability_registry_register_and_get():
    """Verify registry correctly registers and looks up capabilities."""
    registry = CapabilityRegistry()
    assert len(registry.list_all()) == 0

    cap = Capability(
        name="test.cap",
        scope="Workspace",
        permissions=["execute"],
        risk_level=RiskLevel.LOW,
    )
    registry.register(cap)

    assert registry.get("test.cap") == cap
    assert registry.get("nonexistent") is None
    assert len(registry.list_all()) == 1
    assert registry.list_all()[0] == cap


def test_default_capabilities_registered():
    """Verify default 6 capabilities are registered in the global registry."""
    from nexusagent.security.capability import registry

    caps = registry.list_all()
    assert len(caps) >= 6

    expected_names = {
        "filesystem.read",
        "filesystem.write",
        "execute.tests",
        "git.commit",
        "network.access",
        "shell.execute",
    }
    registered_names = {c.name for c in caps}
    assert expected_names.issubset(registered_names)

    # Check properties of one of them
    fs_read = registry.get("filesystem.read")
    assert fs_read is not None
    assert fs_read.risk_level == RiskLevel.LOW
    assert "read" in fs_read.permissions
