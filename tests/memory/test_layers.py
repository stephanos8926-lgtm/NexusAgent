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
    manager = LayerMemoryManager(tmp_workspace)
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


@pytest.mark.anyio
async def test_hybrid_memory_manager_layer_integration(tmp_workspace):
    from nexusagent.memory.hybrid_memory import HybridMemoryManager
    from nexusagent.memory.layers import MemoryLayer
    from nexusagent.core.trust import TrustLevel

    mgr = HybridMemoryManager(tmp_workspace)
    mgr.initialize()

    # Route semantic memory from trusted system source
    filepath = await mgr.remember(
        content="Stable system parameters configured.",
        type="semantic",
        source_session_id="system",
        confidence=0.8,
    )
    assert filepath is not None

    # Check that it exists in the LayerMemoryManager SEMANTIC backend
    semantic_items = mgr.layer_manager.query("Stable system", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_items) == 1
    assert semantic_items[0].provenance.authority == TrustLevel.TRUSTED
    assert semantic_items[0].confidence == 0.8

    # Route working/ephemeral memory
    filepath_work = await mgr.remember(
        content="Current action step executed.",
        type="working",
        source_session_id="session-123",
        confidence=0.9,
    )
    assert filepath_work is not None

    working_items = mgr.layer_manager.query("Current action", layer=MemoryLayer.WORKING)
    assert len(working_items) == 1
    assert working_items[0].provenance.authority == TrustLevel.UNTRUSTED
    assert working_items[0].confidence == 0.9

    await mgr.close()


def test_jaccard_similarity_direct():
    from nexusagent.memory.layer_manager import jaccard_similarity

    assert jaccard_similarity("hello world", "hello world") == 1.0
    assert jaccard_similarity("hello world", "world hello") == 1.0
    assert jaccard_similarity("quick brown fox", "lazy dog") == 0.0
    assert jaccard_similarity("the quick brown fox", "quick brown fox jumps") == 3 / 5


def test_layer_memory_manager_confidence_boosting_and_promotion(tmp_workspace):
    from nexusagent.memory.layers import MemoryLayer
    from nexusagent.core.trust import TrustLevel

    manager = LayerMemoryManager(tmp_workspace)

    # 1. Store first episodic memory with trusted source, initial confidence 0.7
    item_id = manager.remember(
        content="Developer delivered the feature successfully.",
        layer=MemoryLayer.EPISODIC,
        source="system",
        authority=TrustLevel.TRUSTED,
        confidence=0.7,
    )
    assert item_id is not None

    # Retrieve and check initial confidence
    item = manager.get(MemoryLayer.EPISODIC, item_id)
    assert item.confidence == 0.7

    # 2. Store highly similar episodic memory (should boost confidence by 0.15 to 0.85)
    item_id_2 = manager.remember(
        content="Developer delivered the feature successfully!",
        layer=MemoryLayer.EPISODIC,
        source="system",
        authority=TrustLevel.TRUSTED,
        confidence=0.7,
    )
    assert item_id_2 == item_id

    item = manager.get(MemoryLayer.EPISODIC, item_id)
    assert item.confidence == 0.85

    # 3. Store third highly similar memory (should boost to 1.0 and promote to SEMANTIC)
    item_id_3 = manager.remember(
        content="developer delivered the feature successfully.",
        layer=MemoryLayer.EPISODIC,
        source="system",
        authority=TrustLevel.TRUSTED,
        confidence=0.7,
    )
    assert item_id_3 == item_id

    item = manager.get(MemoryLayer.EPISODIC, item_id)
    assert item.confidence == 1.0

    # Verify automatic promotion to Semantic layer
    semantic_items = manager.query("Developer delivered the feature", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_items) == 1
    assert semantic_items[0].confidence == 1.0
    assert semantic_items[0].provenance.authority == TrustLevel.TRUSTED
