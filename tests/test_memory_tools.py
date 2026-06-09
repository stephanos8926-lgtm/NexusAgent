"""Tests for HybridMemoryManager and memory tools (Task 3)."""

import os
import tempfile
from pathlib import Path

import pytest

# Import register_all to populate the tool registry
import nexusagent.tools.register_all  # noqa: F401
from nexusagent.memory import HybridMemoryManager
from nexusagent.tools.registry import get_tool_info


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    import shutil

    shutil.rmtree(d)


# ── HybridMemoryManager tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_remember_and_recall(tmp_workspace):
    """Create HybridMemoryManager, remember something, recall it."""
    mgr = HybridMemoryManager(tmp_workspace)
    mgr.initialize()

    # Remember an entry (now async)
    filepath = await mgr.remember(
        content="The authentication module uses JWT tokens for session management.",
        type="world",
        description="Auth uses JWT",
        entities=["auth", "jwt"],
    )
    assert os.path.exists(filepath)

    # Recall it (sync)
    results = mgr.index.search_sync("JWT", max_results=5)
    assert len(results) >= 1
    assert any("JWT" in r["content"] for r in results)


@pytest.mark.asyncio
async def test_memory_context_format(tmp_workspace):
    """Verify get_memory_context returns formatted string with citations."""
    mgr = HybridMemoryManager(tmp_workspace)
    mgr.initialize()

    await mgr.remember(
        content="We use pytest for all Python testing.",
        type="opinion",
        description="Testing uses pytest",
        confidence=0.9,
        entities=["testing", "pytest"],
    )

    context = mgr.get_memory_context("pytest testing", max_results=5)
    assert context != ""
    assert "## Relevant Memories" in context
    assert "Source:" in context
    assert "bank/" in context


@pytest.mark.asyncio
async def test_flush_creates_daily_log(tmp_workspace):
    """Call flush, verify daily log file created."""
    mgr = HybridMemoryManager(tmp_workspace)
    mgr.initialize()

    await mgr.flush("Session summary: worked on memory system today")

    # Check daily log was created
    daily_files = list(Path(tmp_workspace).joinpath("memory").glob("*.md"))
    assert len(daily_files) >= 1
    content = daily_files[0].read_text()
    assert "Session summary" in content


@pytest.mark.asyncio
async def test_remember_and_recall_async(tmp_workspace):
    """Async version: remember + recall."""
    mgr = HybridMemoryManager(tmp_workspace)
    mgr.initialize()

    await mgr.remember(
        content="sqlite-vec provides vector similarity search in SQLite.",
        type="world",
        description="sqlite-vec for vector search",
    )

    results = await mgr.recall("vector similarity", max_results=5)
    assert len(results) >= 1


# ── Tool registration tests ────────────────────────────────────────────


def test_memory_search_tool_registered():
    """Verify memory_search tool is registered and has correct metadata."""
    info = get_tool_info("memory_search")
    assert info is not None
    assert info.name == "memory_search"
    assert info.category == "memory"
    assert "query" in info.parameters
    assert "max_results" in info.parameters


def test_memory_get_tool_registered():
    """Verify memory_get tool is registered and has correct metadata."""
    info = get_tool_info("memory_get")
    assert info is not None
    assert info.name == "memory_get"
    assert info.category == "memory"
    assert "path" in info.parameters
    assert "offset" in info.parameters
    assert "limit" in info.parameters


def test_memory_write_tool_registered():
    """Verify memory_write tool is registered and has correct metadata."""
    info = get_tool_info("memory_write")
    assert info is not None
    assert info.name == "memory_write"
    assert info.category == "memory"
    assert "content" in info.parameters
    assert "type" in info.parameters
    assert "description" in info.parameters
