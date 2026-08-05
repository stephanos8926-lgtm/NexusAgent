# SPDX-License-Identifier: MIT

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
    item = manager._backends[MemoryLayer.SEMANTIC]._from_payload(
        {
            "item": {"id": "x", "content": "test", "created_at": "2026-01-01T00:00:00+00:00"},
            "layer": MemoryLayer.SEMANTIC.value,
            "provenance": {
                "source": "",
                "authority": TrustLevel.TRUSTED.value,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "session_id": "",
            },
            "confidence": 0.9,
            "min_confidence": 0.6,
            "tags": [],
            "metadata": {},
        }
    )
    assert item is not None
    action = manager.evaluate_confidence(item)
    assert action == ConfidenceAction.PROMOTE
