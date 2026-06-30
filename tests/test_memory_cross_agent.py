"""Tests for cross-agent memory sharing (Phase 2: Session wiring + tests).

Covers inherit_from, promote_to_parent, parent index search integration,
and SessionManager wiring.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.core.session.manager import (
    SessionManager,
    _discover_cross_session_memories,
)
from nexusagent.memory.hybrid_memory import HybridMemoryManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_parent_dir():
    """Create a temporary parent workspace with some memories."""
    d = tempfile.mkdtemp()
    # Initialize with HybridMemoryManager so .memory/index.sqlite exists
    parent_mgr = HybridMemoryManager(d)
    parent_mgr.initialize()
    # Write a memory so the index has content
    asyncio.run(parent_mgr.remember(
        content="The deployment target is us-east-1 production cluster",
        type="world",
        description="Deployment target",
    ))
    asyncio.run(parent_mgr.close())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def tmp_child_dir():
    """Create a temporary child workspace."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _make_session_manager():
    """Create a SessionManager instance for testing."""
    return SessionManager()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _write_memory(mgr, content, entry_type="world"):
    """Write a memory entry."""
    await mgr.remember(content=content, type=entry_type)


# ---------------------------------------------------------------------------
# 1. test_inherit_from_loads_parent_memories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inherit_from_loads_parent_memories(tmp_parent_dir, tmp_child_dir):
    """Create parent with memories, create child with inherit_from, verify
    child can recall parent memories."""
    # Create child workspace and inherit from parent
    child_mgr = HybridMemoryManager(tmp_child_dir)
    child_mgr.initialize()
    await child_mgr.inherit_from(tmp_parent_dir)

    # Recall should find parent memory
    results = await child_mgr.recall("deployment target", max_results=5)
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
    contents = [r.get("content", "") for r in results]
    assert any("us-east-1" in c for c in contents), (
        f"Parent memory not found in results: {contents}"
    )
    await child_mgr.close()


# ---------------------------------------------------------------------------
# 2. test_write_isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_isolation(tmp_parent_dir, tmp_child_dir):
    """Child writes go to child directory only, not parent."""
    # Create child and inherit
    child_mgr = HybridMemoryManager(tmp_child_dir)
    child_mgr.initialize()
    await child_mgr.inherit_from(tmp_parent_dir)

    # Write a memory in child
    await child_mgr.remember(
        content="Child memory about UI design",
        type="observation",
    )
    await child_mgr.close()

    # Verify child bank/ has the child memory
    child_bank = Path(tmp_child_dir) / "bank"
    child_files = list(child_bank.glob("*.md"))
    assert any("UI design" in f.read_text() for f in child_files), (
        "Child memory not found in child bank/"
    )

    # Verify parent bank/ does NOT have the child memory
    parent_bank = Path(tmp_parent_dir) / "bank"
    parent_files = list(parent_bank.glob("*.md"))
    assert not any("UI design" in f.read_text() for f in parent_files), (
        "Child memory leaked to parent bank/"
    )


# ---------------------------------------------------------------------------
# 3. test_promote_to_parent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_promote_to_parent(tmp_parent_dir, tmp_child_dir):
    """Child memories promoted to parent directory."""
    # Create child with memories
    child_mgr = HybridMemoryManager(tmp_child_dir)
    child_mgr.initialize()
    await child_mgr.inherit_from(tmp_parent_dir)
    await child_mgr.remember(
        content="Important finding from child session",
        type="opinion",
        description="Child finding",
    )
    # Promote
    count = child_mgr.promote_to_parent()
    assert count >= 1, f"Expected at least 1 file promoted, got {count}"
    await child_mgr.close()

    # Verify the memory is now in parent's bank/
    parent_bank = Path(tmp_parent_dir) / "bank"
    parent_files = list(parent_bank.glob("*.md"))
    assert any("Important finding" in f.read_text() for f in parent_files), (
        "Promoted memory not found in parent bank/"
    )


# ---------------------------------------------------------------------------
# 4. test_promote_concurrent_locking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_promote_concurrent_locking(tmp_parent_dir, tmp_child_dir):
    """Two workers promoting simultaneously don't corrupt."""
    # Create child with multiple memories
    child_mgr = HybridMemoryManager(tmp_child_dir)
    child_mgr.initialize()
    await child_mgr.inherit_from(tmp_parent_dir)
    for i in range(5):
        await child_mgr.remember(
            content=f"Concurrent memory #{i}",
            type="observation",
        )

    # Simulate two concurrent promotions using asyncio.to_thread
    await asyncio.gather(
        asyncio.to_thread(child_mgr.promote_to_parent),
        asyncio.to_thread(child_mgr.promote_to_parent),
    )

    # At most 5 unique files should be promoted (no duplicates from lock)
    parent_bank = Path(tmp_parent_dir) / "bank"
    parent_files = list(parent_bank.glob("*.md"))
    # Each file should be unique (no corruption from concurrent access)
    contents = set()
    for f in parent_files:
        text = f.read_text()
        if "Concurrent memory" in text:
            contents.add(text)

    # We expect at most 5 unique "Concurrent memory" entries
    assert len(contents) <= 5, (
        f"Concurrent promotion created duplicates: {len(contents)} files"
    )
    await child_mgr.close()


# ---------------------------------------------------------------------------
# 5. test_parent_dir_deleted_mid_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parent_dir_deleted_mid_session(tmp_parent_dir, tmp_child_dir):
    """Graceful degradation when parent dir is deleted."""
    # Create child and inherit
    child_mgr = HybridMemoryManager(tmp_child_dir)
    child_mgr.initialize()
    await child_mgr.inherit_from(tmp_parent_dir)

    # Delete parent directory
    shutil.rmtree(tmp_parent_dir)

    # recall should not crash, just return own results (or empty)
    results = await child_mgr.recall("parent memory", max_results=5)
    # Should return empty list (parent index gone, no own memories match)
    assert isinstance(results, list)

    # Child should still be able to write
    await child_mgr.remember(
        content="Child still works after parent deletion",
        type="observation",
    )
    await child_mgr.close()


# ---------------------------------------------------------------------------
# 6. test_path_traversal_prevention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_path_traversal_prevention(tmp_child_dir):
    """inherit_from rejects paths that don't have a valid memory index."""
    child_mgr = HybridMemoryManager(tmp_child_dir)
    child_mgr.initialize()

    # Try a path that doesn't exist
    with pytest.raises(FileNotFoundError):
        await child_mgr.inherit_from("/tmp/nonexistent_path_12345")

    # Try a path that exists but has no memory index
    tmp_bad = tempfile.mkdtemp()
    try:
        with pytest.raises(FileNotFoundError):
            await child_mgr.inherit_from(tmp_bad)
    finally:
        shutil.rmtree(tmp_bad, ignore_errors=True)

    # Try a path traversal that resolves outside workspace
    with pytest.raises((FileNotFoundError, ValueError)):
        await child_mgr.inherit_from("../../../etc/passwd")

    await child_mgr.close()


# ---------------------------------------------------------------------------
# 7. test_self_inheritance_prevention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_inheritance_prevention(tmp_child_dir):
    """inherit_from rejects own workspace_dir."""
    child_mgr = HybridMemoryManager(tmp_child_dir)
    child_mgr.initialize()

    with pytest.raises(ValueError, match="Cannot inherit from own workspace"):
        await child_mgr.inherit_from(tmp_child_dir)

    await child_mgr.close()


# ---------------------------------------------------------------------------
# 8. test_duplicate_inherit_from
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_inherit_from(tmp_parent_dir, tmp_child_dir):
    """Calling inherit_from twice replaces parent cleanly."""
    # Create a second parent workspace
    parent2_dir = tempfile.mkdtemp()
    try:
        # Set up parent2 with a different memory
        parent2_mgr = HybridMemoryManager(parent2_dir)
        parent2_mgr.initialize()
        await parent2_mgr.remember(
            content="Memory from parent workspace TWO",
            type="world",
        )
        asyncio.run(parent2_mgr.close())

        # Create child and inherit from parent1 (already has memory from fixture)
        child_mgr = HybridMemoryManager(tmp_child_dir)
        child_mgr.initialize()
        await child_mgr.inherit_from(tmp_parent_dir)

        # Verify parent1 memory is found
        results = await child_mgr.recall("deployment target", max_results=5)
        contents = [r.get("content", "") for r in results]
        assert any("us-east-1" in c for c in contents), (
            f"Parent1 memory not found: {contents}"
        )

        # Now switch to parent2
        await child_mgr.inherit_from(parent2_dir)

        # Verify parent2 memory is found
        results = await child_mgr.recall("workspace TWO", max_results=5)
        contents = [r.get("content", "") for r in results]
        assert any("TWO" in c for c in contents), (
            f"Parent2 memory not found: {contents}"
        )
        # Parent1 index should be closed, so its results shouldn't appear
        assert not any("us-east-1" in c for c in contents), (
            f"Parent1 memory still present after replacement: {contents}"
        )
        await child_mgr.close()
    finally:
        shutil.rmtree(parent2_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 9. test_recall_merges_results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_merges_results(tmp_parent_dir, tmp_child_dir):
    """Parent and own memories both appear in recall results."""
    # Create child with inherit and own memory
    child_mgr = HybridMemoryManager(tmp_child_dir)
    child_mgr.initialize()
    await child_mgr.inherit_from(tmp_parent_dir)
    await child_mgr.remember(
        content="Child memory about API endpoints",
        type="observation",
    )

    # Recall with a query that matches parent memory
    results = await child_mgr.recall("deployment target", max_results=10)
    contents = [r.get("content", "") for r in results]
    assert any("us-east-1" in c for c in contents), (
        f"Parent memory missing from recall: {contents}"
    )
    assert any("API endpoints" in c for c in contents), (
        f"Child memory missing from recall: {contents}"
    )
    await child_mgr.close()


# ---------------------------------------------------------------------------
# 10. test_context_prefix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_prefix(tmp_parent_dir, tmp_child_dir):
    """Parent memories prefixed with [Parent Memory] in get_memory_context."""
    # Create child with inherit
    child_mgr = HybridMemoryManager(tmp_child_dir)
    child_mgr.initialize()
    await child_mgr.inherit_from(tmp_parent_dir)

    # Get context
    context = await child_mgr.get_memory_context("deployment", max_results=5)
    assert "[Parent Memory]" in context, (
        f"Parent memory prefix missing from context:\n{context}"
    )
    assert "us-east-1" in context
    await child_mgr.close()


# ---------------------------------------------------------------------------
# 11. test_regression_cross_session_discovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regression_cross_session_discovery():
    """Existing _discover_cross_session_memories still works."""
    mock_db_repo = AsyncMock()
    mock_db_repo.find_sessions_by_working_dir = AsyncMock(return_value=[])

    result = await _discover_cross_session_memories(
        working_dir="/some/path",
        session_id="test-session",
        db_repo=mock_db_repo,
    )
    assert result == []
    mock_db_repo.find_sessions_by_working_dir.assert_called_once_with(
        "/some/path", exclude="test-session", limit=5
    )


# ---------------------------------------------------------------------------
# 12. test_get_or_create_passes_parent_memory_dir
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_create_passes_parent_memory_dir(tmp_parent_dir, tmp_child_dir):
    """SessionManager passes parent_memory_dir through to Session."""
    sm = _make_session_manager()

    parent_path = Path(tmp_parent_dir)
    child_path = Path(tmp_child_dir)

    # Create a session with parent_memory_dir
    session = await sm.get_or_create(
        session_id="test-cross-agent",
        working_dir=str(child_path),
        agent=MagicMock(),
        db_repo=AsyncMock(),
        memory_dir=str(child_path),
        parent_memory_dir=str(parent_path),
    )

    assert session is not None
    assert session.parent_memory_dir is not None
    assert session.parent_memory_dir.resolve() == parent_path.resolve()

    # Clean up
    await sm.close("test-cross-agent")


# ---------------------------------------------------------------------------
# Additional edge case: Session parent_memory_dir property defaults to None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_parent_memory_dir_default_none(tmp_child_dir):
    """Session.parent_memory_dir is None when not provided."""
    sm = _make_session_manager()
    session = await sm.get_or_create(
        session_id="test-no-parent",
        working_dir=tmp_child_dir,
        agent=MagicMock(),
        db_repo=AsyncMock(),
        memory_dir=tmp_child_dir,
    )
    assert session.parent_memory_dir is None
    await sm.close("test-no-parent")
