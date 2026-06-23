# tests/test_memory_contradiction.py
"""Tests for contradiction detection in the memory system."""

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_workspace():
    d = tempfile.mkdtemp(prefix="nexus_test_contra_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _write_memory(workspace, name, content, entities=None, confidence=0.5):
    """Write a memory file with frontmatter."""
    import yaml
    bank_dir = Path(workspace) / "bank"
    bank_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "name": name,
        "description": name,
        "type": "observation",
        "confidence": confidence,
    }
    if entities:
        frontmatter["entities"] = entities
    content_str = "---\n" + yaml.dump(frontmatter) + "---\n\n" + content
    (bank_dir / f"{name}.md").write_text(content_str)


class TestContradictionDetection:
    """Tests for the contradiction detection feature."""

    def test_no_contradiction_single_memory(self, temp_workspace):
        """Single memory should never have contradictions."""
        from nexusagent.memory.refinement import LLMRefinement

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"], confidence=0.8)

        refinement = LLMRefinement(llm_call=None)
        memories = [{"content": "User prefers pytest", "entities": ["testing"], "confidence": 0.8}]

        result = asyncio.run(refinement.detect_contradictions(memories))
        assert result == []

    def test_heuristic_detects_confidence_gap(self, temp_workspace):
        """Heuristic should flag memories with large confidence gaps for same entity."""
        from nexusagent.memory.refinement import LLMRefinement

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"], confidence=0.9)
        _write_memory(temp_workspace, "obs-002", "User prefers unittest", entities=["testing"], confidence=0.3)

        refinement = LLMRefinement(llm_call=None)
        memories = [
            {"content": "User prefers pytest", "entities": ["testing"], "confidence": 0.9},
            {"content": "User prefers unittest", "entities": ["testing"], "confidence": 0.3},
        ]

        result = asyncio.run(refinement.detect_contradictions(memories))
        assert len(result) >= 1
        assert result[0]["entity"] == "testing"

    def test_no_contradiction_different_entities(self, temp_workspace):
        """Memories about different entities should not conflict."""
        from nexusagent.memory.refinement import LLMRefinement

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"], confidence=0.8)
        _write_memory(temp_workspace, "obs-002", "User prefers PostgreSQL", entities=["database"], confidence=0.8)

        refinement = LLMRefinement(llm_call=None)
        memories = [
            {"content": "User prefers pytest", "entities": ["testing"], "confidence": 0.8},
            {"content": "User prefers PostgreSQL", "entities": ["database"], "confidence": 0.8},
        ]

        result = asyncio.run(refinement.detect_contradictions(memories))
        assert result == []

    def test_no_contradiction_similar_confidence(self, temp_workspace):
        """Memories with similar confidence should not be flagged by heuristic."""
        from nexusagent.memory.refinement import LLMRefinement

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"], confidence=0.7)
        _write_memory(temp_workspace, "obs-002", "User prefers unittest", entities=["testing"], confidence=0.6)

        refinement = LLMRefinement(llm_call=None)
        memories = [
            {"content": "User prefers pytest", "entities": ["testing"], "confidence": 0.7},
            {"content": "User prefers unittest", "entities": ["testing"], "confidence": 0.6},
        ]

        result = asyncio.run(refinement.detect_contradictions(memories))
        # Confidence gap is only 0.1, below 0.3 threshold
        assert result == []

    @pytest.mark.asyncio
    async def test_llm_detects_contradiction(self, temp_workspace):
        """LLM should detect obvious contradictions."""
        from nexusagent.memory.refinement import LLMRefinement

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"], confidence=0.9)
        _write_memory(temp_workspace, "obs-002", "User prefers unittest", entities=["testing"], confidence=0.3)

        # Mock LLM that detects contradiction
        async def mock_llm_call(system, user, **kwargs):
            return '{"has_contradiction": true, "resolution": "pytest is more common", "keep": 0, "remove": [1]}'

        refinement = LLMRefinement(llm_call=mock_llm_call)
        memories = [
            {"content": "User prefers pytest", "entities": ["testing"], "confidence": 0.9},
            {"content": "User prefers unittest", "entities": ["testing"], "confidence": 0.3},
        ]

        result = await refinement.detect_contradictions(memories)
        assert len(result) >= 1
        assert result[0]["entity"] == "testing"

    @pytest.mark.asyncio
    async def test_llm_no_contradiction(self, temp_workspace):
        """LLM should return no contradiction for compatible memories."""
        from nexusagent.memory.refinement import LLMRefinement

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"], confidence=0.8)
        _write_memory(temp_workspace, "obs-002", "User uses type hints", entities=["coding-style"], confidence=0.8)

        # Mock LLM that finds no contradiction
        async def mock_llm_call(system, user, **kwargs):
            return '{"has_contradiction": false}'

        refinement = LLMRefinement(llm_call=mock_llm_call)
        memories = [
            {"content": "User prefers pytest", "entities": ["testing"], "confidence": 0.8},
            {"content": "User uses type hints", "entities": ["coding-style"], "confidence": 0.8},
        ]

        result = await refinement.detect_contradictions(memories)
        assert result == []


class TestDreamCycleContradiction:
    """Tests for contradiction detection integrated into DreamCycle."""

    @pytest.mark.asyncio
    async def test_dream_cycle_resolves_contradictions(self, temp_workspace):
        """Dream cycle should resolve contradictions during consolidation."""
        from nexusagent.memory.dream import DreamCycle

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"], confidence=0.9)
        _write_memory(temp_workspace, "obs-002", "User prefers unittest", entities=["testing"], confidence=0.3)
        _write_memory(temp_workspace, "obs-003", "User uses type hints", entities=["coding-style"], confidence=0.8)

        cycle = DreamCycle(temp_workspace, llm_refinement=True)
        report = await cycle.run(dry_run=False)

        assert "contradictions_resolved" in report["phase3_consolidate"]
        # Heuristic should have resolved the testing contradiction
        assert report["phase3_consolidate"]["contradictions_resolved"] >= 1

    @pytest.mark.asyncio
    async def test_dry_run_does_not_resolve(self, temp_workspace):
        """Dry run should not actually remove contradicted memories."""
        from nexusagent.memory.dream import DreamCycle

        _write_memory(temp_workspace, "obs-001", "User prefers pytest", entities=["testing"], confidence=0.9)
        _write_memory(temp_workspace, "obs-002", "User prefers unittest", entities=["testing"], confidence=0.3)

        cycle = DreamCycle(temp_workspace, llm_refinement=False)
        report = await cycle.run(dry_run=True)

        assert report["dry_run"] is True
        # Files should still exist
        assert (Path(temp_workspace) / "bank" / "obs-001.md").exists()
        assert (Path(temp_workspace) / "bank" / "obs-002.md").exists()
