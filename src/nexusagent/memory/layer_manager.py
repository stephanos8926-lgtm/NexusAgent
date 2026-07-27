"""4-layer memory manager for Phase 9.

Wraps the existing ``HybridMemoryManager`` with a trust-aware layer router.
All legacy APIs stay intact; new behavior is opt-in via ``MemoryLayer``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nexusagent.core.trust import TrustLevel
from nexusagent.memory.layer_backends import (
    EpisodicMemoryBackend,
    ProceduralMemoryBackend,
    SemanticMemoryBackend,
    WorkingMemoryBackend,
)
from nexusagent.memory.layers import (
    ConfidenceAction,
    LayerMemoryItem,
    MemoryLayer,
    MemoryProvenance,
)


def jaccard_similarity(str1: str, str2: str) -> float:
    """Compute token-overlap Jaccard similarity between two strings."""
    tokens1 = set(str1.lower().split())
    tokens2 = set(str2.lower().split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)


class LayerMemoryManager:
    """Orchestrates four memory layer backends."""

    def __init__(self, workspace_dir: str | Path) -> None:
        self.workspace_dir = str(workspace_dir)
        self._backends: dict[MemoryLayer, Any] = {
            MemoryLayer.WORKING: WorkingMemoryBackend(workspace_dir),
            MemoryLayer.EPISODIC: EpisodicMemoryBackend(workspace_dir),
            MemoryLayer.SEMANTIC: SemanticMemoryBackend(workspace_dir),
            MemoryLayer.PROCEDURAL: ProceduralMemoryBackend(workspace_dir),
        }
        self._min_confidence: dict[MemoryLayer, float] = {
            MemoryLayer.WORKING: 0.0,
            MemoryLayer.EPISODIC: 0.1,
            MemoryLayer.SEMANTIC: 0.6,
            MemoryLayer.PROCEDURAL: 0.4,
        }

    def remember(
        self,
        content: str,
        layer: MemoryLayer = MemoryLayer.EPISODIC,
        *,
        source: str = "",
        authority: TrustLevel = TrustLevel.UNTRUSTED,
        confidence: float = 0.5,
        session_id: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        min_confidence: float | None = None,
    ) -> str | None:
        """Write a memory item to the requested layer."""
        from nexusagent.memory.memory_item import MemoryItem

        backend = self._backends[layer]

        # Confidence scoring detects similar/identical observations (via token-overlap Jaccard similarity)
        existing_items = self.query("", layer=layer, limit=50)
        similar_item: LayerMemoryItem | None = None
        for ext in existing_items:
            sim = jaccard_similarity(content, ext.item.content)
            if sim >= 0.7:
                similar_item = ext
                break

        if similar_item is not None:
            # Repeated observations increment confidence by +0.15 (up to 1.0)
            new_confidence = min(similar_item.confidence + 0.15, 1.0)
            similar_item.confidence = new_confidence

            # Re-verify and save back to backend
            item_id = backend.put(similar_item)

            # Auto-promotion of EPISODIC to SEMANTIC layer on confidence >= 0.9 and TRUSTED authority
            if (
                item_id
                and similar_item.layer == MemoryLayer.EPISODIC
                and similar_item.confidence >= 0.9
                and similar_item.provenance.authority == TrustLevel.TRUSTED
            ):
                self.remember(
                    content=similar_item.item.content,
                    layer=MemoryLayer.SEMANTIC,
                    source=similar_item.provenance.source,
                    authority=similar_item.provenance.authority,
                    confidence=similar_item.confidence,
                    session_id=similar_item.provenance.session_id,
                    tags=similar_item.tags,
                    metadata=similar_item.metadata,
                )
            return item_id or None

        item = MemoryItem(
            id=MemoryItem.generate_id(),
            content=content,
            metadata=metadata or {},
        )
        provenance = MemoryProvenance(
            source=source,
            authority=authority,
            session_id=session_id,
        )
        layer_item = LayerMemoryItem(
            item=item,
            layer=layer,
            provenance=provenance,
            confidence=confidence,
            min_confidence=min_confidence if min_confidence is not None else self._min_confidence[layer],
            tags=tags or [],
            metadata=item.metadata,
        )
        item_id = backend.put(layer_item)

        # Trigger initial auto-promotion check if created directly with high confidence and TRUSTED authority
        if (
            item_id
            and layer == MemoryLayer.EPISODIC
            and confidence >= 0.9
            and authority == TrustLevel.TRUSTED
        ):
            self.remember(
                content=content,
                layer=MemoryLayer.SEMANTIC,
                source=source,
                authority=authority,
                confidence=confidence,
                session_id=session_id,
                tags=tags,
                metadata=metadata,
            )

        return item_id or None

    def get(self, layer: MemoryLayer, item_id: str) -> LayerMemoryItem | None:
        backend = self._backends[layer]
        return backend.get(item_id)

    def query(self, text: str, *, layer: MemoryLayer | None = None, limit: int = 10) -> list[LayerMemoryItem]:
        results: list[LayerMemoryItem] = []
        layers = [layer] if layer else list(self._backends)
        for mem_layer in layers:
            backend = self._backends[mem_layer]
            results.extend(backend.query(text, limit=limit))
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:limit]

    def evaluate_confidence(self, layer_item: LayerMemoryItem) -> ConfidenceAction:
        if layer_item.confidence < layer_item.min_confidence:
            return ConfidenceAction.REJECT
        if layer_item.layer == MemoryLayer.SEMANTIC and layer_item.confidence >= 0.9:
            return ConfidenceAction.PROMOTE
        if layer_item.confidence >= layer_item.min_confidence:
            return ConfidenceAction.ACCEPT
        return ConfidenceAction.NEEDS_REVIEW
