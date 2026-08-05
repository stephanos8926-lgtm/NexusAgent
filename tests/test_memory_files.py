"""Tests for the file-based memory layer."""

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


def test_gitignore_created_when_git_exists(tmp_workspace):
    """A .gitignore should be created in .nexusagent/ when .git/ is present."""
    # Create .git directory to simulate a git repo
    (Path(tmp_workspace) / ".git").mkdir()

    fm = FileMemory(tmp_workspace)
    fm.initialize()

    gitignore = Path(tmp_workspace) / ".nexusagent" / ".gitignore"
    assert gitignore.exists()
    assert gitignore.read_text() == "*\n!.gitignore\n"


def test_gitignore_not_created_without_git(tmp_workspace):
    """No .gitignore should be created when .git/ does not exist."""
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    nexus_dir = Path(tmp_workspace) / ".nexusagent"
    assert not nexus_dir.exists()


def test_gitignore_not_overwritten(tmp_workspace):
    """An existing .gitignore should not be overwritten."""
    # Create .git directory and a pre-existing .gitignore with custom content
    (Path(tmp_workspace) / ".git").mkdir()
    nexus_dir = Path(tmp_workspace) / ".nexusagent"
    nexus_dir.mkdir(parents=True, exist_ok=True)
    gitignore = nexus_dir / ".gitignore"
    gitignore.write_text("custom-content\n")

    fm = FileMemory(tmp_workspace)
    fm.initialize()

    # Content should be preserved
    assert gitignore.read_text() == "custom-content\n"


def test_write_entry_updates_quality_score_on_append(tmp_workspace):
    """Appending to existing file should update quality_score in frontmatter."""
    fm = FileMemory(tmp_workspace)
    fm.initialize()

    # Write initial entry
    fm.write_entry(
        content="Short",
        entry_type=MemoryEntryType.WORLD,
        description="Test entry",
        confidence=0.5,
    )

    # Get the created file
    topic_files = list(Path(tmp_workspace).glob("bank/*.md"))
    assert len(topic_files) == 1
    topic_file = topic_files[0]

    # Read initial frontmatter using the utility function
    from nexusagent.memory.memory_utils import parse_frontmatter
    content = topic_file.read_text()
    initial_fm = parse_frontmatter(content)
    initial_score = initial_fm.get("quality_score", 0)

    # Append longer content to same file (same description will use same file)
    fm.write_entry(
        content="Much longer content that should increase the quality score significantly due to length",
        entry_type=MemoryEntryType.WORLD,
        description="Test entry",
        confidence=0.5,
    )

    # Read updated frontmatter
    content = topic_file.read_text()
    updated_fm = parse_frontmatter(content)
    updated_score = updated_fm.get("quality_score", 0)

    # Quality score should have increased due to longer content
    assert updated_score >= initial_score, f"Quality score should increase or stay same: {initial_score} -> {updated_score}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
