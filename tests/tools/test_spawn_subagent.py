# tests/tools/test_spawn_subagent.py
"""Tests for the spawn_subagent tool registration."""

import pytest

import nexusagent.tools.register_all
from nexusagent.tools.registry import get_tool_info
from nexusagent.tools.registry.core import registry


@pytest.fixture(autouse=True)
def ensure_registry_populated():
    """Ensure registry is populated for this test."""
    # Other test fixtures clear the registry before each test
    # We need to re-populate it
    with registry._lock:
        if not registry._pending:
            import importlib
            importlib.reload(nexusagent.tools.register_all)
    yield


def test_spawn_subagent_registered():
    """spawn_subagent should be registered with category='orchestration'."""
    info = get_tool_info("spawn_subagent")
    assert info is not None, "spawn_subagent not found in registry"
    assert info.category == "orchestration", f"Expected 'orchestration', got {info.category!r}"
    assert info.name == "spawn_subagent"
