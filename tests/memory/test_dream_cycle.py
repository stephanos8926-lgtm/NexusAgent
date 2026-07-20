"""Integration tests for the 4-phase DreamCycle memory consolidation system."""

import os
import shutil
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nexusagent.memory.dream import DreamCycle, STALE_THRESHOLD_DAYS
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


def _write_raw_memory(workspace, name, content):
    """Write a raw memory file to bank/."""
    bank_dir = Path(workspace) / "bank"
    bank_dir.mkdir(parents=True, exist_ok=True)
    filepath = bank_dir / f"{name}.md"
    filepath.write_text(content)
    return filepath


def test_dream_cycle_lock(workspace_dir):
    """Verify that DreamLock prevents concurrent runs and automatically breaks stale locks."""
    cycle1 = DreamCycle(workspace_dir)
    cycle2 = DreamCycle(workspace_dir)

    # Acquire lock
    assert cycle1.lock.acquire() is True
    # Attempting to acquire again fails
    assert cycle2.lock.acquire() is False

    # Release and acquire works
    cycle1.lock.release()
    assert cycle2.lock.acquire() is True
    cycle2.lock.release()


@pytest.mark.asyncio
async def test_dream_cycle_four_phases_e2e(workspace_dir, file_memory):
    """Verify the 4-phase consolidation runs with real memory items and index rebuild."""
    # Phase 1: Write some real entries
    # 1. Duplicate entries (identical files)
    raw = (
        "---\n"
        'name: "dup-test"\n'
        "description: test\n"
        "type: world\n"
        f"created: {datetime.now(UTC).isoformat()}\n"
        "---\n\n"
        "Identical body text for duplicates\n"
    )
    _write_raw_memory(workspace_dir, "orig", raw)
    # Ensure slightly different mtimes to keep "orig" and remove "copy"
    time.sleep(0.01)
    _write_raw_memory(workspace_dir, "copy", raw)

    # 3. Stale entry
    stale_path = file_memory.write_entry(
        content="Old outdated fact about legacy system.",
        entry_type=MemoryEntryType.WORLD,
        description="Legacy System",
        confidence=0.5,
    )
    # Set its mtime to 60 days ago
    old_time = time.time() - (STALE_THRESHOLD_DAYS + 10) * 86400
    os.utime(stale_path, (old_time, old_time))

    # Initialize the HybridMemoryIndex and index them
    idx = HybridMemoryIndex(str(workspace_dir))
    for f in file_memory.list_all_files():
        idx.index_file(f)

    # Run the DreamCycle end-to-end
    cycle = DreamCycle(workspace_dir, llm_refinement=False)
    report = await cycle.run()

    # Verify the results of the run
    assert report["dry_run"] is False
    assert report["duplicates_removed"] == 1
    assert report["stale_pruned"] == 1
    assert len(report["phase2_patterns"]["type_distribution"]) >= 1

    # Verify index rebuilt during Trim phase (Phase 4)
    assert report["phase4_trim"]["index_rebuilt"] is True

    # Verify the files are gone on disk
    assert not Path(stale_path).exists()
    assert not (workspace_dir / "bank" / "copy.md").exists()
    assert (workspace_dir / "bank" / "orig.md").exists()

    await idx.close()
