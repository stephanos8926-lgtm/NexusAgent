"""Tests for the file-based memory layer."""

import shutil
import tempfile
from pathlib import Path

import pytest

from nexusagent.memory_files import FileMemory, MemoryEntryType


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def test_create_workspace(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()
    assert (Path(tmp_workspace) / "MEMORY.md").exists()
    assert (Path(tmp_workspace) / "memory").exists()
    assert (Path(tmp_workspace) / "bank").exists()


def test_write_and_read_entry(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    fm.write_entry(
        content="The auth module uses JWT tokens",
        entry_type=MemoryEntryType.WORLD,
        description="Auth uses JWT",
        entities=["auth", "jwt"],
    )

    # Should create a topic file
    topic_files = list(Path(tmp_workspace).glob("bank/*.md"))
    assert len(topic_files) >= 1

    # MEMORY.md should have a pointer
    mem_md = (Path(tmp_workspace) / "MEMORY.md").read_text()
    assert "JWT" in mem_md or "auth" in mem_md


def test_daily_log(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    fm.append_daily_log("Worked on memory system today")
    fm.append_daily_log("## Retain\n- W: Implemented hybrid memory with FTS5 + sqlite-vec")

    daily_files = list((Path(tmp_workspace) / "memory").glob("*.md"))
    assert len(daily_files) >= 1


def test_memory_index_truncation(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    # Write 250 entries (over the 200 line limit)
    for i in range(250):
        fm.write_entry(f"Entry {i}", MemoryEntryType.WORLD, f"Entry {i}")

    mem_md = (Path(tmp_workspace) / "MEMORY.md").read_text()
    lines = mem_md.strip().split("\n")
    # Should be truncated to ~200 lines
    assert len(lines) <= 210  # small buffer for header


def test_frontmatter_format(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    fm.write_entry(
        "Test content", MemoryEntryType.OPINION, "Test opinion", confidence=0.8, entities=["test"]
    )

    topic_files = list(Path(tmp_workspace).glob("bank/*.md"))
    content = topic_files[0].read_text()
    assert "---" in content  # YAML frontmatter
    assert "type: opinion" in content
    assert "confidence: 0.8" in content


def test_entity_pages(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    fm.write_entry(
        content="The auth module uses JWT tokens",
        entry_type=MemoryEntryType.WORLD,
        description="Auth uses JWT",
        entities=["auth", "jwt"],
    )

    # Entity files should be created
    entities_dir = Path(tmp_workspace) / "bank" / "entities"
    assert entities_dir.exists()
    entity_files = list(entities_dir.glob("*.md"))
    assert len(entity_files) >= 2


def test_get_daily_logs(tmp_workspace):
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    fm.append_daily_log("Worked on memory system today")
    fm.append_daily_log("## Retain\n- W: Implemented hybrid memory with FTS5 + sqlite-vec")

    logs = fm.get_daily_logs(days=2)
    assert len(logs) >= 1
    assert logs[0]["retain"] != ""
    assert "Implemented" in logs[0]["retain"]
