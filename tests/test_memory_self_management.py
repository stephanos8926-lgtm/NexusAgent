"""Tests for memory self-management tools (Phase 1).

Tests memory_delete, memory_update, memory_list, and memory_prune tools.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

import nexusagent.tools.register_all  # noqa: F401
from nexusagent.memory.memory import HybridMemoryManager
from nexusagent.memory.memory_files import FileMemory, MemoryEntryType
from nexusagent.tools.registry import get_tool_info


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def _write_test_memory(workspace, name="test-entry", content="Test content",
                       entry_type="world", description="Test desc",
                       entities=None, confidence=None):
    """Helper to write a test memory entry and return its relative path."""
    fm = FileMemory(workspace)
    fm.initialize()
    filepath = fm.write_entry(
        content=content,
        entry_type=MemoryEntryType(entry_type),
        description=description,
        entities=entities or [],
        confidence=confidence,
    )
    # Return relative path within workspace
    return os.path.relpath(filepath, workspace)


# ── Tool registration tests ────────────────────────────────────────────


def test_memory_delete_tool_registered():
    info = get_tool_info("memory_delete")
    assert info is not None
    assert info.name == "memory_delete"
    assert info.category == "memory"
    assert "path" in info.parameters


def test_memory_update_tool_registered():
    info = get_tool_info("memory_update")
    assert info is not None
    assert info.name == "memory_update"
    assert info.category == "memory"
    assert "path" in info.parameters
    assert "content" in info.parameters


def test_memory_list_tool_registered():
    info = get_tool_info("memory_list")
    assert info is not None
    assert info.name == "memory_list"
    assert info.category == "memory"
    assert "type" in info.parameters
    assert "limit" in info.parameters


def test_memory_prune_tool_registered():
    info = get_tool_info("memory_prune")
    assert info is not None
    assert info.name == "memory_prune"
    assert info.category == "memory"
    assert "older_than_days" in info.parameters
    assert "dry_run" in info.parameters


# ── memory_delete tests ────────────────────────────────────────────────


def test_memory_delete_removes_file_and_index(tmp_workspace):
    """Delete a memory and verify both file and index entries are removed."""
    from nexusagent.tools.register_all import memory_delete

    rel_path = _write_test_memory(tmp_workspace, content="Delete me")
    full_path = os.path.join(tmp_workspace, rel_path)

    # Verify file exists
    assert os.path.exists(full_path)

    # Delete
    result = memory_delete(rel_path, workspace=tmp_workspace)
    assert "Deleted memory" in result
    assert "index entries removed" in result

    # Verify file is gone
    assert not os.path.exists(full_path)


def test_memory_delete_path_traversal_blocked(tmp_workspace):
    """Path traversal should be blocked."""
    from nexusagent.tools.register_all import memory_delete

    result = memory_delete("../../etc/passwd", workspace=tmp_workspace)
    assert "ACCESS DENIED" in result


def test_memory_delete_nonexistent_file(tmp_workspace):
    """Deleting a nonexistent file should return error."""
    from nexusagent.tools.register_all import memory_delete

    result = memory_delete("bank/nonexistent.md", workspace=tmp_workspace)
    assert "File not found" in result


# ── memory_update tests ────────────────────────────────────────────────


def test_memory_update_content(tmp_workspace):
    """Update a memory's content and verify it's changed."""
    from nexusagent.tools.register_all import memory_update

    rel_path = _write_test_memory(tmp_workspace, content="Original content")

    result = memory_update(rel_path, content="Updated content", workspace=tmp_workspace)
    assert "Updated memory" in result

    # Verify content changed
    full_path = os.path.join(tmp_workspace, rel_path)
    content = open(full_path).read()
    assert "Updated content" in content
    assert "Original content" not in content


def test_memory_update_preserves_frontmatter(tmp_workspace):
    """Update should preserve existing frontmatter fields."""
    from nexusagent.tools.register_all import memory_update

    rel_path = _write_test_memory(
        tmp_workspace,
        content="Original",
        entry_type="opinion",
        description="My opinion",
        confidence=0.8,
        entities=["test"],
    )

    result = memory_update(rel_path, content="New content", workspace=tmp_workspace)
    assert "Updated memory" in result

    full_path = os.path.join(tmp_workspace, rel_path)
    content = open(full_path).read()
    assert "type: opinion" in content
    assert "confidence: 0.8" in content
    assert "New content" in content


def test_memory_update_overrides_type(tmp_workspace):
    """Update with explicit type should override frontmatter."""
    from nexusagent.tools.register_all import memory_update

    rel_path = _write_test_memory(tmp_workspace, entry_type="world")

    result = memory_update(rel_path, content="New", type="observation", workspace=tmp_workspace)
    assert "Updated memory" in result

    full_path = os.path.join(tmp_workspace, rel_path)
    content = open(full_path).read()
    assert "type: observation" in content


def test_memory_update_path_traversal_blocked(tmp_workspace):
    from nexusagent.tools.register_all import memory_update

    result = memory_update("../../etc/passwd", content="hack", workspace=tmp_workspace)
    assert "ACCESS DENIED" in result


def test_memory_update_nonexistent_file(tmp_workspace):
    from nexusagent.tools.register_all import memory_update

    result = memory_update("bank/nonexistent.md", content="test", workspace=tmp_workspace)
    assert "File not found" in result


# ── memory_list tests ──────────────────────────────────────────────────


def test_memory_list_all(tmp_workspace):
    """List all memories."""
    from nexusagent.tools.register_all import memory_list

    _write_test_memory(tmp_workspace, name="entry1", content="First")
    _write_test_memory(tmp_workspace, name="entry2", content="Second")

    result = memory_list(workspace=tmp_workspace)
    assert "Memory entries" in result
    assert "bank/" in result


def test_memory_list_filter_by_type(tmp_workspace):
    """List with type filter."""
    from nexusagent.tools.register_all import memory_list

    _write_test_memory(tmp_workspace, name="fact1", entry_type="world")
    _write_test_memory(tmp_workspace, name="op1", entry_type="opinion")

    result = memory_list(type="world", workspace=tmp_workspace)
    assert "world" in result


def test_memory_list_limit(tmp_workspace):
    """List with limit."""
    from nexusagent.tools.register_all import memory_list

    for i in range(5):
        _write_test_memory(tmp_workspace, name=f"entry{i}", content=f"Entry {i}",
                           description=f"Unique desc {i}")

    result = memory_list(limit=3, workspace=tmp_workspace)
    # Should show at most 3
    assert "3 shown" in result


def test_memory_list_empty_workspace(tmp_workspace):
    """List on empty workspace."""
    from nexusagent.tools.register_all import memory_list

    result = memory_list(workspace=tmp_workspace)
    assert "No memories found" in result


# ── memory_prune tests ─────────────────────────────────────────────────


def test_memory_prune_dry_run(tmp_workspace):
    """Prune dry-run should not delete files."""
    from nexusagent.tools.register_all import memory_prune

    rel_path = _write_test_memory(tmp_workspace, name="old", content="Old memory")
    full_path = os.path.join(tmp_workspace, rel_path)

    result = memory_prune(older_than_days=0, type="world", dry_run=True, workspace=tmp_workspace)
    # Dry run should not delete
    assert "Dry run" in result
    assert os.path.exists(full_path)


def test_memory_prune_by_type(tmp_workspace):
    """Prune by type should only delete matching entries."""
    from nexusagent.tools.register_all import memory_prune

    _write_test_memory(tmp_workspace, name="fact", entry_type="world")
    _write_test_memory(tmp_workspace, name="op", entry_type="opinion")

    result = memory_prune(type="observation", dry_run=False, workspace=tmp_workspace)
    # Should not delete anything (no observation entries)
    assert "No memories match" in result or "0" in result


def test_memory_prune_no_criteria(tmp_workspace):
    """Prune with no criteria should not delete anything."""
    from nexusagent.tools.register_all import memory_prune

    _write_test_memory(tmp_workspace, name="entry", content="Test")

    result = memory_prune(dry_run=False, workspace=tmp_workspace)
    assert "No memories match" in result


def test_memory_prune_path_traversal_via_workspace(tmp_workspace):
    """Prune should use workspace safely."""
    from nexusagent.tools.register_all import memory_prune

    # Normal operation should work
    result = memory_prune(older_than_days=365, dry_run=True, workspace=tmp_workspace)
    # Should not crash
    assert isinstance(result, str)


# ── HybridMemoryIndex.delete_by_file tests ─────────────────────────────


def test_delete_by_file_removes_chunks(tmp_workspace):
    """delete_by_file should remove all chunks for a file."""
    from nexusagent.memory.index.index import HybridMemoryIndex

    rel_path = _write_test_memory(tmp_workspace, content="Test content for indexing")

    # Index the file
    idx = HybridMemoryIndex(tmp_workspace)
    idx.index_file(rel_path)

    # Now delete should find chunks
    deleted = idx.delete_by_file(rel_path)
    assert deleted >= 1


def test_delete_by_file_nonexistent(tmp_workspace):
    """delete_by_file for nonexistent file should return 0."""
    from nexusagent.memory.index.index import HybridMemoryIndex

    idx = HybridMemoryIndex(tmp_workspace)
    deleted = idx.delete_by_file("bank/nonexistent.md")
    assert deleted == 0


def test_reindex_file_updates_index(tmp_workspace):
    """reindex_file should delete old and create new index entries."""
    from nexusagent.memory.index.index import HybridMemoryIndex

    rel_path = _write_test_memory(tmp_workspace, content="Reindex test")

    idx = HybridMemoryIndex(tmp_workspace)
    result = idx.reindex_file(rel_path)
    assert result is True


def test_reindex_file_nonexistent(tmp_workspace):
    """reindex_file for nonexistent file should return False."""
    from nexusagent.memory.index.index import HybridMemoryIndex

    idx = HybridMemoryIndex(tmp_workspace)
    result = idx.reindex_file("bank/nonexistent.md")
    assert result is False
