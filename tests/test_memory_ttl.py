"""Tests for TTL enforcement in FileMemory."""

import shutil
import tempfile
from pathlib import Path

import pytest

from nexusagent.memory.memory_files import FileMemory, MemoryEntryType


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def test_ttl_expired_entry_excluded_from_index(tmp_workspace):
    """A memory with ttl_hours=0 should be excluded from get_index_entries()."""
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    # Write an already-expired entry (ttl_hours=0 means expires immediately)
    fm.write_entry(
        content="This is a short-lived memory",
        entry_type=MemoryEntryType.WORLD,
        description="Short-lived fact",
        ttl_hours=0,
    )

    # Write a normal entry that should remain visible
    fm.write_entry(
        content="This is a permanent memory",
        entry_type=MemoryEntryType.WORLD,
        description="Permanent fact",
    )

    entries = fm.get_index_entries()
    descriptions = [e["description"] for e in entries]

    # The expired entry should NOT appear in index results
    assert "Short-lived fact" not in descriptions
    # The permanent entry should still be there
    assert "Permanent fact" in descriptions


def test_sweep_expired_removes_files_and_index(tmp_workspace):
    """sweep_expired() should physically remove expired files and their index entries."""
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    # Write an already-expired entry
    fm.write_entry(
        content="This memory has expired",
        entry_type=MemoryEntryType.WORLD,
        description="Expired memory",
        ttl_hours=0,
    )

    # Write a permanent entry
    fm.write_entry(
        content="This memory is still valid",
        entry_type=MemoryEntryType.WORLD,
        description="Valid memory",
    )

    # Verify both files exist on disk before sweep
    bank_files_before = list(Path(tmp_workspace).glob("bank/*.md"))
    assert len(bank_files_before) == 2

    # Run sweep
    report = fm.sweep_expired()

    # Verify sweep report
    assert report["expired_found"] == 1
    assert report["files_removed"] == 1
    assert report["index_entries_removed"] == 1
    assert len(report["files"]) == 1
    assert "expired-memory" in report["files"][0]

    # Verify only the permanent file remains on disk
    bank_files_after = list(Path(tmp_workspace).glob("bank/*.md"))
    assert len(bank_files_after) == 1
    assert "valid-memory" in bank_files_after[0].name

    # Verify the expired entry is gone from the index
    entries = fm.get_index_entries()
    descriptions = [e["description"] for e in entries]
    assert "Expired memory" not in descriptions
    assert "Valid memory" in descriptions


def test_sweep_expired_no_op_when_no_expired(tmp_workspace):
    """sweep_expired() should be a no-op when nothing has expired."""
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    # Write a permanent entry
    fm.write_entry(
        content="This memory never expires",
        entry_type=MemoryEntryType.WORLD,
        description="Permanent fact",
    )

    report = fm.sweep_expired()

    assert report["expired_found"] == 0
    assert report["files_removed"] == 0
    assert report["index_entries_removed"] == 0
    assert report["files"] == []

    # File should still exist
    bank_files = list(Path(tmp_workspace).glob("bank/*.md"))
    assert len(bank_files) == 1


def test_sweep_expired_empty_workspace(tmp_workspace):
    """sweep_expired() should handle empty workspace gracefully."""
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    report = fm.sweep_expired()

    assert report["expired_found"] == 0
    assert report["files_removed"] == 0
    assert report["files"] == []


def test_ttl_future_entry_not_expired(tmp_workspace):
    """A memory with a future TTL should NOT be excluded."""
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    fm.write_entry(
        content="This memory is valid for 24 hours",
        entry_type=MemoryEntryType.WORLD,
        description="Future expiry",
        ttl_hours=24,
    )

    entries = fm.get_index_entries()
    descriptions = [e["description"] for e in entries]
    assert "Future expiry" in descriptions


def test_sweep_preserves_valid_entries(tmp_workspace):
    """sweep_expired() should only remove expired entries, preserving valid ones."""
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    # Write several entries: some expired, some not
    fm.write_entry(content="Expired 1", entry_type=MemoryEntryType.WORLD, description="Expired 1", ttl_hours=0)
    fm.write_entry(content="Valid 1", entry_type=MemoryEntryType.WORLD, description="Valid 1")
    fm.write_entry(content="Expired 2", entry_type=MemoryEntryType.WORLD, description="Expired 2", ttl_hours=0)
    fm.write_entry(content="Valid 2", entry_type=MemoryEntryType.WORLD, description="Valid 2")

    report = fm.sweep_expired()

    assert report["expired_found"] == 2
    assert report["files_removed"] == 2

    # Only valid entries should remain
    entries = fm.get_index_entries()
    descriptions = sorted(e["description"] for e in entries)
    assert descriptions == ["Valid 1", "Valid 2"]

    bank_files = list(Path(tmp_workspace).glob("bank/*.md"))
    assert len(bank_files) == 2
