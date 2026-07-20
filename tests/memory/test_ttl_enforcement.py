"""Integration tests for TTL enforcement, expired item sweeping, and index exclusion."""

import shutil
import tempfile
from pathlib import Path

import pytest

from nexusagent.memory.dream import DreamCycle
from nexusagent.memory.memory_files import FileMemory, MemoryEntryType
from nexusagent.memory.memory_index import HybridMemoryIndex


@pytest.fixture
def workspace_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d)


@pytest.fixture
def file_memory(workspace_dir):
    fm = FileMemory(str(workspace_dir))
    fm.initialize()
    return fm


@pytest.mark.asyncio
async def test_ttl_enforcement_and_sweeping(workspace_dir, file_memory):
    """Verify that expired items are excluded from index and swept properly."""
    # Write fresh item (no TTL)
    fresh_path = file_memory.write_entry(
        content="This is fresh knowledge about Python.",
        entry_type=MemoryEntryType.WORLD,
        description="Fresh Python",
    )

    # Write expired item (TTL of -1 hours, so it is in the past)
    expired_path = file_memory.write_entry(
        content="This is expired knowledge about old software.",
        entry_type=MemoryEntryType.WORLD,
        description="Expired Old Software",
        ttl_hours=-1,
    )

    # Verify both exist on disk initially
    assert Path(fresh_path).exists()
    assert Path(expired_path).exists()

    # Verify `get_index_entries` silently excludes the expired one
    index_entries = file_memory.get_index_entries()
    filenames = [e["file"] for e in index_entries]
    # 'Fresh Python''s file should be in index, but 'Expired Old Software''s file should NOT!
    assert any("fresh" in f for f in filenames)
    assert not any("expired" in f for f in filenames)

    # Setup the index and index both files
    idx = HybridMemoryIndex(str(workspace_dir))
    idx.index_file(str(Path(fresh_path).relative_to(workspace_dir)))
    idx.index_file(str(Path(expired_path).relative_to(workspace_dir)))

    # Rebuild FTS5/vector index and run sweeping (via DreamCycle.trim_index())
    cycle = DreamCycle(workspace_dir, llm_refinement=False)
    trim_report = cycle.trim_index()

    # Verify sweeping physically deleted the expired file but kept the fresh one
    assert trim_report["expired_swept"]["files_removed"] == 1
    assert not Path(expired_path).exists()
    assert Path(fresh_path).exists()

    # Verify index search no longer finds the swept expired entry
    results = idx.search_sync("expired")
    assert not any("expired" in r["file"] for r in results)

    await idx.close()
