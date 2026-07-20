"""Integration tests for the ConsolidationEngine memory maintenance system."""

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from nexusagent.memory.consolidation import ConsolidationEngine
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


def test_consolidation_engine_scan_and_consolidate(workspace_dir, file_memory):
    """Verify that ConsolidationEngine correctly identifies issues and applies fixes."""
    # Write duplicates
    raw = (
        "---\n"
        'name: "dup-test"\n'
        "description: test\n"
        "type: world\n"
        "---\n\n"
        "Identical body text\n"
    )
    _write_raw_memory(workspace_dir, "file1", raw)
    _write_raw_memory(workspace_dir, "file2", raw)

    # Write stale entry
    stale_path = file_memory.write_entry(
        content="Old legacy system information.",
        entry_type=MemoryEntryType.WORLD,
        description="Legacy Info",
        confidence=0.5,
    )
    old_time = time.time() - 40 * 86400  # 40 days ago
    os.utime(stale_path, (old_time, old_time))

    # Test Scan
    engine = ConsolidationEngine(str(workspace_dir), dry_run=False)
    report = engine.scan()

    assert report["status"] == "ok"
    assert report["total_files"] == 3
    assert len(report["duplicates"]) == 1
    assert len(report["stale"]) == 1

    # Test Health Report
    health = engine.health_report()
    assert health["total_memories"] == 3
    assert health["duplicate_count"] == 1
    assert health["stale_count"] == 1
    assert health["health_score"] < 1.0

    # Test Consolidate
    actions = engine.consolidate(report)
    assert actions["duplicates_removed"] == 1
    assert actions["stale_pruned"] == 1
    assert actions["index_rebuilt"] is True

    # Verify clean up on disk
    assert not Path(stale_path).exists()
    assert not (workspace_dir / "bank" / "file2.md").exists()
    assert (workspace_dir / "bank" / "file1.md").exists()

    # Re-scan should be healthy
    health_after = engine.health_report()
    assert health_after["duplicate_count"] == 0
    assert health_after["stale_count"] == 0
    assert health_after["health_score"] == 1.0


def test_cosine_similarity_duplicate_concept():
    """Verify high-similarity cosine math used in deduplication concepts."""
    import math

    # Perfect match (similarity = 1.0)
    vec1 = [1.0, 2.0, 3.0]
    vec2 = [1.0, 2.0, 3.0]
    dot = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    mag_a = math.sqrt(sum(a * a for a in vec1))
    mag_b = math.sqrt(sum(b * b for b in vec2))
    sim = dot / (mag_a * mag_b)
    assert sim > 0.95

    # Completely different
    vec3 = [-1.0, -2.0, -3.0]
    dot = sum(a * b for a, b in zip(vec1, vec3, strict=True))
    mag_c = math.sqrt(sum(c * c for c in vec3))
    sim_opp = dot / (mag_a * mag_c)
    assert sim_opp < 0.0
