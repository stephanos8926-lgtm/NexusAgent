"""Tests for the Phase 9 4-layer memory system."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from nexusagent.core.trust import TrustLevel
from nexusagent.memory.layer_manager import LayerMemoryManager
from nexusagent.memory.layers import ConfidenceAction, MemoryLayer


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def test_layer_manager_initializes(tmp_workspace):
    LayerMemoryManager(tmp_workspace)
    for layer in MemoryLayer:
        assert (Path(tmp_workspace) / ".nexusagent" / "layers" / layer.value).exists()


def test_remember_accepts_episodic(tmp_workspace):
    manager = LayerMemoryManager(tmp_workspace)
    item_id = manager.remember(
        "User asked for Phase 9",
        layer=MemoryLayer.EPISODIC,
        source="session:abc",
        authority=TrustLevel.TOOL_INTERNAL,
        confidence=0.7,
    )
    assert item_id is not None


def test_semantic_rejects_low_confidence(tmp_workspace):
    manager = LayerMemoryManager(tmp_workspace)
    low_id = manager.remember(
        "Unverified fact",
        layer=MemoryLayer.SEMANTIC,
        confidence=0.3,
    )
    assert low_id is None


def test_semantic_requires_trusted_authority(tmp_workspace):
    manager = LayerMemoryManager(tmp_workspace)
    untrusted_id = manager.remember(
        "External claim",
        layer=MemoryLayer.SEMANTIC,
        authority=TrustLevel.UNTRUSTED,
        confidence=0.9,
    )
    assert untrusted_id is None


def test_query_returns_results(tmp_workspace):
    manager = LayerMemoryManager(tmp_workspace)
    manager.remember("Phase 9 memory evolution", layer=MemoryLayer.EPISODIC, confidence=0.8)
    results = manager.query("Phase 9", layer=MemoryLayer.EPISODIC)
    assert len(results) == 1
    assert results[0].item.content == "Phase 9 memory evolution"


def test_confidence_evaluation(tmp_workspace):
    manager = LayerMemoryManager(tmp_workspace)
    item = manager._backends[MemoryLayer.SEMANTIC]._from_payload({
        "item": {"id": "x", "content": "test", "created_at": "2026-01-01T00:00:00+00:00"},
        "layer": MemoryLayer.SEMANTIC.value,
        "provenance": {"source": "", "authority": TrustLevel.TRUSTED.value, "timestamp": "2026-01-01T00:00:00+00:00", "session_id": ""},
        "confidence": 0.9,
        "min_confidence": 0.6,
        "tags": [],
        "metadata": {},
    })
    assert item is not None
    action = manager.evaluate_confidence(item)
    assert action == ConfidenceAction.PROMOTE


def test_trust_aware_ingestion_semantic_rejection(tmp_workspace):
    """Verify trust-aware ingestion policy rejects direct writes to semantic backend from content with authority level below TrustLevel.TRUSTED."""
    manager = LayerMemoryManager(tmp_workspace)

    # Low trust / authority (unverified user message)
    item_id = manager.remember(
        "Poisoning factual semantic knowledge with untrusted user text",
        layer=MemoryLayer.SEMANTIC,
        source="user_chat",
        authority=TrustLevel.UNTRUSTED,
        confidence=0.8,
    )
    # The direct write to Semantic layer should be rejected and return None
    assert item_id is None

    # Try with TOOL_EXTERNAL
    item_id_ext = manager.remember(
        "External tool response fact",
        layer=MemoryLayer.SEMANTIC,
        source="mcp_tool",
        authority=TrustLevel.TOOL_EXTERNAL,
        confidence=0.8,
    )
    assert item_id_ext is None


def test_jaccard_similarity_confidence_increment(tmp_workspace):
    """Verify confidence scoring detects similar/identical observations via token-overlap Jaccard similarity and increments confidence by +0.15."""
    manager = LayerMemoryManager(tmp_workspace)

    # First write
    item_id1 = manager.remember(
        "PostgreSQL database should be used for production scalability",
        layer=MemoryLayer.EPISODIC,
        confidence=0.5,
    )
    assert item_id1 is not None

    # Second write: very similar wording (Jaccard similarity >= 0.7)
    item_id2 = manager.remember(
        "PostgreSQL database should be used for production scalability",
        layer=MemoryLayer.EPISODIC,
        confidence=0.5,
    )

    # Should update the existing entry rather than creating a new one
    assert item_id2 == item_id1

    # Check updated entry confidence
    retrieved = manager.get(MemoryLayer.EPISODIC, item_id1)
    assert retrieved is not None
    # Confidence incremented by +0.15 (0.5 + 0.15 = 0.65)
    assert abs(retrieved.confidence - 0.65) < 0.01


def test_episodic_to_semantic_autopromotion(tmp_workspace):
    """Verify that if an EPISODIC memory's confidence reaches >= 0.9 and has a TRUSTED authority, it is automatically promoted to the SEMANTIC layer."""
    manager = LayerMemoryManager(tmp_workspace)

    # Write episodic memory with high confidence and TRUSTED authority
    # Start at 0.8
    item_id = manager.remember(
        "The server is running on port 8080",
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.TRUSTED,
        confidence=0.8,
    )
    assert item_id is not None

    # Re-observe the exact same or highly similar fact to trigger confidence increment to >= 0.9
    item_id2 = manager.remember(
        "The server is running on port 8080",
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.TRUSTED,
        confidence=0.8,
    )
    assert item_id2 == item_id

    # Verify the episodic entry updated confidence to 0.95 (0.8 + 0.15)
    retrieved = manager.get(MemoryLayer.EPISODIC, item_id)
    assert retrieved.confidence >= 0.9

    # Verify it has been promoted to the Semantic layer
    semantic_results = manager.query("The server is running on port 8080", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) >= 1
    assert semantic_results[0].item.content == "The server is running on port 8080"


@pytest.mark.asyncio
async def test_hybrid_memory_integration(tmp_workspace):
    """Verify HybridMemoryManager remember propagates to the LayerMemoryManager."""
    from nexusagent.memory.hybrid_memory import HybridMemoryManager

    hmm = HybridMemoryManager(tmp_workspace)
    hmm.initialize()

    # Calling remember with a 'world' type should route to SEMANTIC layer
    # Since authority defaults to TRUSTED for system/empty source, it should succeed
    filepath = await hmm.remember(
        content="System architecture specification phase 9",
        type="world",
        confidence=0.8,
    )
    assert filepath is not None

    # Verify it was stored in Semantic backend
    semantic_results = hmm.layer_manager.query("System architecture specification phase 9", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) == 1
    assert semantic_results[0].item.content == "System architecture specification phase 9"

    await hmm.close()
