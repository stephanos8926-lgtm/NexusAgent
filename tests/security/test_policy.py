"""Unit tests for PolicyEngine and role-based capability evaluation."""

from __future__ import annotations

import pytest

from nexusagent.security.policy import PolicyEngine


def test_policy_engine_role_evaluation():
    """Verify PolicyEngine correctly maps roles to capabilities."""
    engine = PolicyEngine()

    # Coder has all capabilities
    coder_context = {"role": "coder", "policy": "strict", "unlocked": set()}
    allowed, _ = engine.evaluate(coder_context, "filesystem.write")
    assert allowed
    allowed, _ = engine.evaluate(coder_context, "shell.execute")
    assert allowed

    # Reader does not have write or shell execution
    reader_context = {"role": "reader", "policy": "strict", "unlocked": set()}
    allowed, _ = engine.evaluate(reader_context, "filesystem.read")
    assert allowed
    allowed, _ = engine.evaluate(reader_context, "filesystem.write")
    assert not allowed
    allowed, _ = engine.evaluate(reader_context, "shell.execute")
    assert not allowed


def test_policy_engine_modes():
    """Verify permissive, restricted, and strict policy modes."""
    engine = PolicyEngine()

    # 1. Permissive mode: auto-unlocks on first call
    context = {"role": "reader", "policy": "permissive", "unlocked": set()}
    allowed, _ = engine.evaluate(context, "filesystem.write")
    assert allowed
    assert "filesystem.write" in context["unlocked"]

    # 2. Restricted mode: denies if not unlocked, allows if explicitly unlocked
    context = {"role": "reader", "policy": "restricted", "unlocked": set()}
    allowed, _ = engine.evaluate(context, "filesystem.write")
    assert not allowed

    # If explicitly unlocked, it is allowed
    context["unlocked"].add("filesystem.write")
    allowed, _ = engine.evaluate(context, "filesystem.write")
    assert allowed

    # 3. Strict mode: denies even if present in unlocked set, only role defaults allowed
    # Wait, the spec says in strict mode, only exact manifest, no unlocking.
    # Let's verify our PolicyEngine implementation handles strict:
    # "Capability '{capability_name}' is denied for role '{role}' under policy mode '{policy_mode}'."
    context = {
        "role": "reader",
        "policy": "strict",
        "unlocked": {"filesystem.write"},
    }
    allowed, _ = engine.evaluate(context, "filesystem.write")
    assert not allowed


def test_policy_engine_scope_validation():
    """Verify resource scope validations for execution and network capabilities."""
    engine = PolicyEngine()
    context = {"role": "coder", "policy": "strict", "unlocked": set()}

    # Shell execution within workspace is allowed
    allowed, _ = engine.evaluate(context, "shell.execute", "ls -la")
    assert allowed

    # Path escape outside workspace is blocked
    allowed, _ = engine.evaluate(context, "shell.execute", "cat ../../../etc/passwd")
    assert not allowed

    # Network access allowlisted is allowed
    allowed, _ = engine.evaluate(context, "network.access", "https://api.github.com/repos")
    assert allowed

    # Network access non-allowlisted is blocked
    allowed, _ = engine.evaluate(context, "network.access", "https://malicious-site.com")
    assert not allowed
