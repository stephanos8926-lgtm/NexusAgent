"""Tests for Phase 9 Memory Evolution - HybridMemoryManager and LayerMemoryManager Integration."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from nexusagent.core.trust import TrustLevel
from nexusagent.memory.hybrid_memory import HybridMemoryManager
from nexusagent.memory.layers import MemoryLayer


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d)


@pytest.mark.asyncio
async def test_modern_types_mapping_no_value_error(tmp_workspace):
    """Test that modern types map to legacy types without throwing ValueError."""
    mgr = HybridMemoryManager(tmp_workspace)
    mgr.initialize()

    # Should not throw ValueError because 'semantic' maps to legacy 'world'
    filepath_semantic = await mgr.remember(
        content="President Lincoln gave Gettysburg Address in 1863",
        type="semantic",
        description="Gettysburg Address year",
        confidence=0.9,
    )
    assert filepath_semantic is not None
    assert "gettysburg-address" in filepath_semantic

    # Should not throw ValueError because 'working' maps to legacy 'observation'
    filepath_working = await mgr.remember(
        content="Intermediate result: x=42",
        type="working",
        description="Intermediate calculation",
        confidence=0.8,
    )
    assert filepath_working is not None
    assert "intermediate-calculation" in filepath_working


@pytest.mark.asyncio
async def test_layer_routing(tmp_workspace):
    """Test that memories are routed to the correct layer in the 4-layer backend."""
    mgr = HybridMemoryManager(tmp_workspace)
    mgr.initialize()

    # Route "world" / "fact" / "semantic" -> SEMANTIC
    await mgr.remember(
        content="Quantum entanglement is real",
        type="semantic",
        description="Quantum fact",
        confidence=0.9,
        authority=TrustLevel.TRUSTED,
    )
    # Check if it was written to LayerMemoryManager's SEMANTIC layer
    semantic_results = mgr.layer_manager.query("Quantum entanglement", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) == 1
    assert semantic_results[0].item.content == "Quantum entanglement is real"

    # Route "procedural" / "procedure" / "skill" -> PROCEDURAL
    await mgr.remember(
        content="Steps to run tests: pytest tests/",
        type="procedural",
        description="Run tests skill",
        confidence=0.8,
    )
    procedural_results = mgr.layer_manager.query("Steps to run tests", layer=MemoryLayer.PROCEDURAL)
    assert len(procedural_results) == 1
    assert "Steps to run tests" in procedural_results[0].item.content

    # Route "working" / "ephemeral" -> WORKING
    await mgr.remember(
        content="Active step: verify frontend",
        type="working",
        description="Active task progress",
        confidence=0.8,
    )
    working_results = mgr.layer_manager.query("verify frontend", layer=MemoryLayer.WORKING)
    assert len(working_results) == 1
    assert "verify frontend" in working_results[0].item.content

    # Route other types -> EPISODIC
    await mgr.remember(
        content="The worker failed to complete the task.",
        type="observation",
        description="Failed worker",
        confidence=0.7,
    )
    episodic_results = mgr.layer_manager.query("worker failed", layer=MemoryLayer.EPISODIC)
    assert len(episodic_results) == 1
    assert "failed" in episodic_results[0].metadata.get("description", "").lower()


@pytest.mark.asyncio
async def test_trust_aware_ingestion_semantic(tmp_workspace):
    """Test that the trust-aware ingestion policy rejects direct writes to Semantic layer from unverified sources."""
    mgr = HybridMemoryManager(tmp_workspace)
    mgr.initialize()

    # Untrusted write to semantic layer should be rejected
    await mgr.remember(
        content="Unverified information from untrusted source",
        type="semantic",
        description="Untrusted rumor",
        confidence=0.9,
        authority=TrustLevel.UNTRUSTED,
    )
    semantic_results = mgr.layer_manager.query("Unverified information", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) == 0

    # Low confidence write to semantic layer should be rejected
    await mgr.remember(
        content="Verified source but low confidence",
        type="semantic",
        description="Low confidence fact",
        confidence=0.3,
        authority=TrustLevel.TRUSTED,
    )
    semantic_results = mgr.layer_manager.query("Verified source but", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) == 0


@pytest.mark.asyncio
async def test_system_internal_sources_authority(tmp_workspace):
    """Test that system-internal sources ('system', 'framework', 'internal') are mapped to TrustLevel.TRUSTED."""
    mgr = HybridMemoryManager(tmp_workspace)
    mgr.initialize()

    # Pass 'system' as source, which should map to TRUSTED and successfully write to SEMANTIC
    await mgr.remember(
        content="System generated constant value config",
        type="semantic",
        description="System config",
        confidence=0.9,
        source="system",
    )
    semantic_results = mgr.layer_manager.query("System generated", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) == 1
    assert semantic_results[0].provenance.authority == TrustLevel.TRUSTED

    # Pass 'framework' as source, should map to TRUSTED
    await mgr.remember(
        content="Framework core bootstrap event",
        type="semantic",
        description="Framework bootstrap",
        confidence=0.9,
        source="framework",
    )
    semantic_results = mgr.layer_manager.query("Framework core", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) == 1
    assert semantic_results[0].provenance.authority == TrustLevel.TRUSTED
