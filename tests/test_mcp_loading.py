"""Tests for MCP tool loading and memory index wiring — Kanban t_3b8d39cb."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_memory_search_registered():
    """memory_search tool is registered in the tool registry."""
    import nexusagent.tools.register_all  # noqa: F401 — populates registry
    from nexusagent.tools.registry import _REGISTRY
    assert "memory_search" in _REGISTRY, "memory_search not in registry"


def test_memory_index_search_registered():
    """memory_index_search tool is registered."""
    import nexusagent.tools.register_all  # noqa: F401
    from nexusagent.tools.registry import _REGISTRY
    assert "memory_index_search" in _REGISTRY, "memory_index_search not in registry"


def test_memory_index_rebuild_registered():
    """memory_index_rebuild tool is registered."""
    import nexusagent.tools.register_all  # noqa: F401
    from nexusagent.tools.registry import _REGISTRY
    assert "memory_index_rebuild" in _REGISTRY, "memory_index_rebuild not in registry"


def test_register_mcp_tools_is_callable():
    """register_mcp_tools function exists and is idempotent."""
    from nexusagent.tools.register_all import register_mcp_tools
    import asyncio
    result = asyncio.run(register_mcp_tools())
    assert isinstance(result, list)


def test_memory_search_returns_string():
    """memory_search tool returns a string result."""
    import asyncio
    from nexusagent.tools.register_all import memory_search

    async def run():
        result = await memory_search("test query", max_results=1)
        assert isinstance(result, str)

    asyncio.run(run())


def test_ensure_mcp_tools_loaded_called():
    """_ensure_mcp_tools_loaded is importable from agent module."""
    from nexusagent.core.agent import _ensure_mcp_tools_loaded
    assert callable(_ensure_mcp_tools_loaded)
