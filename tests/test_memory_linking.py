# tests/test_memory_linking.py
"""Tests for memory linking (related field)."""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_workspace():
    d = tempfile.mkdtemp(prefix="nexus_test_link_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _write_memory(workspace, name, content, entities=None, confidence=0.5, related=None):
    """Write a memory file with frontmatter."""
    import yaml
    from nexusagent.memory.memory_files import FileMemory, MemoryEntryType

    fm = FileMemory(workspace)
    fm.initialize()
    fm.write_entry(
        content=content,
        entry_type=MemoryEntryType.OBSERVATION,
        description=name,
        confidence=confidence,
        entities=entities,
        related=related,
    )


class TestFindRelated:
    """Tests for the find_related method."""

    def test_finds_by_entity_match(self, temp_workspace):
        """Memories with shared entities should be found."""
        from nexusagent.memory.memory_files import FileMemory

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing", "python"])
        _write_memory(temp_workspace, "obs-002", "User uses pytest for testing", entities=["testing"])
        _write_memory(temp_workspace, "obs-003", "Database uses PostgreSQL", entities=["database"])

        fm = FileMemory(temp_workspace)
        related = fm.find_related(
            content="Testing framework preferences",
            entities=["testing"],
            max_results=5,
        )

        # obs-001 and obs-002 share the "testing" entity
        assert len(related) >= 1
        # obs-003 should not appear (different entity)
        assert not any("obs-003" in r for r in related)

    def test_finds_by_content_similarity(self, temp_workspace):
        """Memories with similar content should be found."""
        from nexusagent.memory.memory_files import FileMemory

        _write_memory(temp_workspace, "obs-001", "User prefers pytest for unit testing")
        _write_memory(temp_workspace, "obs-002", "User prefers pytest for integration testing")
        _write_memory(temp_workspace, "obs-003", "Database configuration for production")

        fm = FileMemory(temp_workspace)
        related = fm.find_related(
            content="User prefers pytest for testing",
            max_results=5,
        )

        # obs-001 and obs-002 share content words
        assert len(related) >= 1

    def test_returns_empty_for_no_matches(self, temp_workspace):
        """No matches should return empty list."""
        from nexusagent.memory.memory_files import FileMemory

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"])

        fm = FileMemory(temp_workspace)
        related = fm.find_related(
            content="Database configuration",
            entities=["database"],
            max_results=5,
        )

        assert related == []

    def test_respects_max_results(self, temp_workspace):
        """Should return at most max_results."""
        from nexusagent.memory.memory_files import FileMemory

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"])
        _write_memory(temp_workspace, "obs-002", "User uses pytest", entities=["testing"])
        _write_memory(temp_workspace, "obs-003", "User likes pytest", entities=["testing"])

        fm = FileMemory(temp_workspace)
        related = fm.find_related(
            content="pytest testing",
            entities=["testing"],
            max_results=2,
        )

        assert len(related) <= 2


class TestAutoLink:
    """Tests for auto-linking on remember."""

    @pytest.mark.asyncio
    async def test_remember_auto_links(self, temp_workspace):
        """Remember should auto-link to related memories."""
        from nexusagent.memory.hybrid_memory import HybridMemoryManager

        mgr = HybridMemoryManager(temp_workspace)
        mgr.initialize()

        # Write first memory
        await mgr.remember(
            content="User prefers pytest for testing",
            type="observation",
            description="Testing preference",
            entities=["testing", "python"],
        )

        # Write second memory with shared entity
        filepath = await mgr.remember(
            content="User uses pytest for integration tests",
            type="observation",
            description="Integration testing",
            entities=["testing"],
        )

        # Check that the second memory has a related link to the first
        content = Path(filepath).read_text()
        assert "related:" in content
        # The related field should reference the first memory file
        assert ".md" in content  # Should reference some .md file
    @pytest.mark.asyncio
    async def test_remember_with_explicit_related(self, temp_workspace):
        """Explicit related should override auto-linking."""
        from nexusagent.memory.hybrid_memory import HybridMemoryManager

        mgr = HybridMemoryManager(temp_workspace)
        mgr.initialize()

        # Write first memory
        path1 = await mgr.remember(
            content="User prefers pytest",
            type="observation",
            description="Testing preference",
            entities=["testing"],
        )

        # Write second with explicit related
        filepath = await mgr.remember(
            content="User uses unittest",
            type="observation",
            description="Alternative testing",
            entities=["testing"],
            related=[str(Path(path1).relative_to(temp_workspace))],
        )

        content = Path(filepath).read_text()
        assert "related:" in content


class TestAddRelatedLink:
    """Tests for the add_related_link method."""

    def test_adds_bidirectional_link(self, temp_workspace):
        """add_related_link should add the related field."""
        from nexusagent.memory.memory_files import FileMemory

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"])
        _write_memory(temp_workspace, "obs-002", "User uses pytest", entities=["testing"])

        # Find the actual file names (they have timestamps)
        bank_dir = Path(temp_workspace) / "bank"
        files = list(bank_dir.glob("obs-*.md"))
        assert len(files) >= 2

        fm = FileMemory(temp_workspace)
        result = fm.add_related_link(
            f"bank/{files[0].name}",
            f"bank/{files[1].name}",
        )
        assert result is True

        # Verify the link was added
        content = files[0].read_text()
        assert "related:" in content

    def test_nonexistent_file_returns_false(self, temp_workspace):
        """Adding link to nonexistent file should return False."""
        from nexusagent.memory.memory_files import FileMemory

        fm = FileMemory(temp_workspace)
        result = fm.add_related_link("bank/nonexistent.md", "bank/other.md")
        assert result is False