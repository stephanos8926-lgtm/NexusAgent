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


def jaccard_similarity(text1: str, text2: str) -> float:
    """Compute token-overlap Jaccard similarity between text1 and text2."""
    import re
    def get_tokens(text: str) -> set[str]:
        tokens = re.findall(r'\w+', text.lower())
        return set(tokens)

    set1 = get_tokens(text1)
    set2 = get_tokens(text2)
    if not set1 or not set2:
        return 0.0
    intersection = set1.intersection(set2)
    union = set1.union(set2)
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

        # Check for similar existing memories in the target layer via token-overlap Jaccard similarity
        if layer == MemoryLayer.EPISODIC:
            backend = self._backends[layer]
            try:
                for entry_file in backend._dir.glob("*.json"):
                    if entry_file.name == "index.json":
                        continue
                    try:
                        import json
                        payload = json.loads(entry_file.read_text())
                        existing_item = backend._from_payload(payload)
                        if existing_item is not None:
                            # Compute Jaccard similarity
                            sim = jaccard_similarity(content, existing_item.item.content)
                            if sim >= 0.8:
                                # Found a highly similar/identical observation!
                                new_confidence = min(existing_item.confidence + 0.15, 1.0)
                                existing_item.confidence = round(new_confidence, 2)

                                # Check for automatic promotion to SEMANTIC layer
                                if (
                                    existing_item.confidence >= 0.9
                                    and existing_item.provenance.authority == TrustLevel.TRUSTED
                                ):
                                    # Promote to SEMANTIC layer
                                    semantic_item = LayerMemoryItem(
                                        item=existing_item.item,
                                        layer=MemoryLayer.SEMANTIC,
                                        provenance=existing_item.provenance,
                                        confidence=existing_item.confidence,
                                        min_confidence=0.6,
                                        tags=existing_item.tags,
                                        metadata=existing_item.metadata,
                                    )
                                    self._backends[MemoryLayer.SEMANTIC].put(semantic_item)

                                # Save the updated episodic memory
                                backend.put(existing_item)
                                return existing_item.item.id
                    except Exception:
                        continue
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Error checking similar episodic memories: %s", exc)

        backend = self._backends[layer]
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
