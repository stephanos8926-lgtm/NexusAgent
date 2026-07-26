"""Unit tests verifying Phase 8 Memory Evolution requirements.

Specifically verifies:
1. Layer separation and independent queryability.
2. Trust-aware ingestion (rejection of low-trust content in high-trust layers).
3. Source provenance preservation (source, confidence, authority, timestamp).
4. Confidence promotion on repeated observations.
5. Safe promotion to Semantic layer for trusted content, and prevention of poisoning for untrusted content.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from nexusagent.core.trust import TrustLevel
from nexusagent.memory.layer_manager import LayerMemoryManager
from nexusagent.memory.layers import MemoryLayer


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_layer_separation_and_queryability(tmp_workspace):
    """Verify that each memory layer is independently queryable."""
    manager = LayerMemoryManager(tmp_workspace)

    # Ingest different contents to different layers
    manager.remember(
        content="Our deployment target is AWS ECS.",
        layer=MemoryLayer.SEMANTIC,
        authority=TrustLevel.TRUSTED,
        confidence=0.8,
    )
    manager.remember(
        content="Current active branch is feature-memory.",
        layer=MemoryLayer.WORKING,
        authority=TrustLevel.TRUSTED,
        confidence=0.9,
    )
    manager.remember(
        content="Encountered standard division by zero exception.",
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.TOOL_INTERNAL,
        confidence=0.7,
    )

    # Query independently
    semantic_results = manager.query("ECS", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) == 1
    assert "AWS ECS" in semantic_results[0].item.content

    working_results = manager.query("branch", layer=MemoryLayer.WORKING)
    assert len(working_results) == 1
    assert "feature-memory" in working_results[0].item.content

    episodic_results = manager.query("division", layer=MemoryLayer.EPISODIC)
    assert len(episodic_results) == 1
    assert "division by zero" in episodic_results[0].item.content

    # Querying Working layer for ECS should yield nothing
    assert len(manager.query("ECS", layer=MemoryLayer.WORKING)) == 0


def test_trust_aware_ingestion_and_poisoning_prevention(tmp_workspace):
    """Verify that low-trust content cannot create/pollute high-trust memories."""
    manager = LayerMemoryManager(tmp_workspace)

    # Ingest low-trust content directly into semantic layer — should be rejected (returns None)
    low_trust_id = manager.remember(
        content="Poisonous unverified instruction",
        layer=MemoryLayer.SEMANTIC,
        authority=TrustLevel.UNTRUSTED,
        confidence=0.9,
    )
    assert low_trust_id is None

    # Ingest medium-trust (TOOL_EXTERNAL) content into semantic layer — should be rejected
    external_id = manager.remember(
        content="Some unverified external package version",
        layer=MemoryLayer.SEMANTIC,
        authority=TrustLevel.TOOL_EXTERNAL,
        confidence=0.9,
    )
    assert external_id is None

    # High-trust (TRUSTED) content should be successfully ingested
    trusted_id = manager.remember(
        content="Python 3.13 is the standard language runtime.",
        layer=MemoryLayer.SEMANTIC,
        authority=TrustLevel.TRUSTED,
        confidence=0.9,
    )
    assert trusted_id is not None

    # Verify that the rejected ones are indeed missing from semantic search
    assert len(manager.query("Poisonous", layer=MemoryLayer.SEMANTIC)) == 0
    assert len(manager.query("Python 3.13", layer=MemoryLayer.SEMANTIC)) == 1


def test_source_provenance_preservation(tmp_workspace):
    """Verify that every memory item is tagged with source, authority, confidence, and timestamp."""
    manager = LayerMemoryManager(tmp_workspace)

    item_id = manager.remember(
        content="The system uses LangGraph for task scheduling.",
        layer=MemoryLayer.EPISODIC,
        source="agent:coder",
        authority=TrustLevel.TOOL_INTERNAL,
        confidence=0.75,
        session_id="session-test-01",
    )

    assert item_id is not None
    stored_item = manager.get(MemoryLayer.EPISODIC, item_id)
    assert stored_item is not None

    # Verify all provenance details
    assert stored_item.provenance.source == "agent:coder"
    assert stored_item.provenance.authority == TrustLevel.TOOL_INTERNAL
    assert stored_item.provenance.session_id == "session-test-01"
    assert stored_item.confidence == 0.75
    assert stored_item.provenance.timestamp is not None
    assert len(stored_item.provenance.timestamp) > 0


def test_confidence_promotion_on_repeated_observation(tmp_workspace):
    """Verify that repeated observations promote memory confidence by +0.15."""
    manager = LayerMemoryManager(tmp_workspace)

    # First observation starts with confidence 0.4
    content = "The API key must be specified in the dotenv config."
    id_1 = manager.remember(
        content=content,
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.TOOL_INTERNAL,
        confidence=0.4,
    )
    assert id_1 is not None

    item_1 = manager.get(MemoryLayer.EPISODIC, id_1)
    assert pytest.approx(item_1.confidence) == 0.4

    # Second identical observation should promote confidence to 0.55
    id_2 = manager.remember(
        content=content,
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.TOOL_INTERNAL,
        confidence=0.4,
    )
    # Returns the same item ID
    assert id_2 == id_1

    item_2 = manager.get(MemoryLayer.EPISODIC, id_1)
    assert pytest.approx(item_2.confidence) == 0.55

    # Third observation (similar wording/substring) should promote to 0.70
    similar_content = "API key must be specified in the dotenv config"
    id_3 = manager.remember(
        content=similar_content,
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.TOOL_INTERNAL,
        confidence=0.4,
    )
    assert id_3 == id_1

    item_3 = manager.get(MemoryLayer.EPISODIC, id_1)
    assert pytest.approx(item_3.confidence) == 0.70


def test_safe_promotion_to_semantic_layer(tmp_workspace):
    """Verify safe promotion of trusted memories to Semantic layer upon repeated observation."""
    manager = LayerMemoryManager(tmp_workspace)

    # Trusted memory starts with 0.8 confidence in Episodic layer
    content = "Verified design: use local SQlite for vector caching."
    id_1 = manager.remember(
        content=content,
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.TRUSTED,
        confidence=0.8,
    )
    assert id_1 is not None

    # Verify it is not in the Semantic layer yet
    assert len(manager.query("SQlite", layer=MemoryLayer.SEMANTIC)) == 0

    # Repeated observation pushes confidence from 0.8 to 0.95 (crosses 0.9 threshold)
    manager.remember(
        content=content,
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.TRUSTED,
        confidence=0.8,
    )

    # Verify that it has been promoted to the Semantic layer!
    semantic_results = manager.query("SQlite", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) == 1
    assert "SQlite for vector caching" in semantic_results[0].item.content


def test_no_promotion_to_semantic_for_untrusted_content(tmp_workspace):
    """Verify that untrusted content is never promoted to Semantic layer even with high confidence."""
    manager = LayerMemoryManager(tmp_workspace)

    content = "Unverified preference: always run build with --no-verify."

    # First observation with UNTRUSTED authority
    manager.remember(
        content=content,
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.UNTRUSTED,
        confidence=0.8,
    )

    # Second observation pushes confidence to 0.95
    manager.remember(
        content=content,
        layer=MemoryLayer.EPISODIC,
        authority=TrustLevel.UNTRUSTED,
        confidence=0.8,
    )

    # Verify that it is NOT promoted to the Semantic layer (poisoning prevented)
    semantic_results = manager.query("--no-verify", layer=MemoryLayer.SEMANTIC)
    assert len(semantic_results) == 0
