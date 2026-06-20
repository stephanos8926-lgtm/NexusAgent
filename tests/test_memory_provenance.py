"""Tests for provenance tracking in the memory system.

Verifies that ``source_session_id`` and ``derived_from`` are correctly
stored in and read from YAML frontmatter of memory files.
"""

from pathlib import Path

import pytest
import yaml

from nexusagent.memory.memory_files import FileMemory, MemoryEntryType


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace with memory directories."""
    workspace = str(tmp_path)
    fm = FileMemory(workspace)
    fm.initialize()
    return fm, workspace


class TestSourceSessionId:
    """Tests for the source_session_id provenance field."""

    def test_write_with_source_session_id(self, tmp_workspace):
        fm, _workspace = tmp_workspace
        filepath = fm.write_entry(
            content="The project uses Python 3.13",
            entry_type=MemoryEntryType.WORLD,
            description="python version",
            source_session_id="test-session-123",
        )
        content = Path(filepath).read_text()
        assert "source_session_id: test-session-123" in content

    def test_source_session_id_in_frontmatter(self, tmp_workspace):
        fm, _workspace = tmp_workspace
        filepath = fm.write_entry(
            content="Decided to use pytest for testing",
            entry_type=MemoryEntryType.EXPERIENCE,
            description="testing framework choice",
            source_session_id="test-session-123",
        )
        # Parse the frontmatter
        raw = Path(filepath).read_text()
        parts = raw.split("---", 2)
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["source_session_id"] == "test-session-123"

    def test_no_source_session_id_when_not_provided(self, tmp_workspace):
        fm, _workspace = tmp_workspace
        filepath = fm.write_entry(
            content="Some generic observation about the codebase",
            entry_type=MemoryEntryType.OBSERVATION,
            description="generic observation",
        )
        raw = Path(filepath).read_text()
        parts = raw.split("---", 2)
        frontmatter = yaml.safe_load(parts[1])
        assert "source_session_id" not in frontmatter


class TestDerivedFrom:
    """Tests for the derived_from provenance field."""

    def test_write_with_derived_from(self, tmp_workspace):
        fm, _workspace = tmp_workspace
        filepath = fm.write_entry(
            content="Consolidated error patterns from multiple sessions",
            entry_type=MemoryEntryType.OBSERVATION,
            description="error pattern summary",
            derived_from=["bank/test-001.md"],
        )
        content = Path(filepath).read_text()
        assert "derived_from" in content
        assert "bank/test-001.md" in content

    def test_derived_from_in_frontmatter(self, tmp_workspace):
        fm, _workspace = tmp_workspace
        filepath = fm.write_entry(
            content="Merged preference from two prior memories",
            entry_type=MemoryEntryType.OPINION,
            description="merged preference",
            confidence=0.9,
            derived_from=["bank/test-001.md", "bank/test-002.md"],
        )
        raw = Path(filepath).read_text()
        parts = raw.split("---", 2)
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["derived_from"] == ["bank/test-001.md", "bank/test-002.md"]

    def test_no_derived_from_when_not_provided(self, tmp_workspace):
        fm, _workspace = tmp_workspace
        filepath = fm.write_entry(
            content="A standalone memory with no derivation",
            entry_type=MemoryEntryType.WORLD,
            description="standalone fact",
        )
        raw = Path(filepath).read_text()
        parts = raw.split("---", 2)
        frontmatter = yaml.safe_load(parts[1])
        assert "derived_from" not in frontmatter


class TestProvenanceCombined:
    """Tests for both provenance fields together."""

    def test_both_fields_present(self, tmp_workspace):
        fm, _workspace = tmp_workspace
        filepath = fm.write_entry(
            content="Derived insight from session analysis",
            entry_type=MemoryEntryType.OBSERVATION,
            description="session insight",
            source_session_id="test-session-123",
            derived_from=["bank/test-001.md"],
        )
        raw = Path(filepath).read_text()
        parts = raw.split("---", 2)
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["source_session_id"] == "test-session-123"
        assert frontmatter["derived_from"] == ["bank/test-001.md"]

    def test_roundtrip_preserves_all_fields(self, tmp_workspace):
        fm, _workspace = tmp_workspace
        filepath = fm.write_entry(
            content="Full provenance test entry with all fields",
            entry_type=MemoryEntryType.EXPERIENCE,
            description="full provenance test",
            confidence=0.85,
            entities=["ProjectAlpha"],
            source_session_id="test-session-123",
            derived_from=["bank/test-001.md", "bank/test-002.md"],
        )
        raw = Path(filepath).read_text()
        parts = raw.split("---", 2)
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter["source_session_id"] == "test-session-123"
        assert frontmatter["derived_from"] == ["bank/test-001.md", "bank/test-002.md"]
        assert frontmatter["confidence"] == 0.85
        assert frontmatter["entities"] == ["ProjectAlpha"]
        assert frontmatter["type"] == "experience"
