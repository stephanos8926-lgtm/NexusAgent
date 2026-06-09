# tests/tools/test_spawn_subagent.py
"""Tests for the spawn_subagent tool registration."""

import nexusagent.tools.register_all  # noqa: F401 — triggers registration
from nexusagent.tools.registry import get_tool_info


def test_spawn_subagent_registered():
    """spawn_subagent should be registered with category='orchestration'."""
    info = get_tool_info("spawn_subagent")
    assert info is not None, "spawn_subagent not found in registry"
    assert info.category == "orchestration", f"Expected 'orchestration', got {info.category!r}"
    assert info.name == "spawn_subagent"
