# SPDX-License-Identifier: MIT

"""Concrete memory layer backends for Phase 9.

Each backend stores memories in its own subdirectory under
``<workspace>/.nexusagent/layers/<layer>/``.  This preserves the existing
``bank/`` and ``memory/`` layout while adding the 4-layer trust boundary
required by the spec.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from nexusagent.core.trust import TrustLevel
from nexusagent.memory.layers import (
    LayerMemoryItem,
    MemoryLayer,
    MemoryProvenance,
)

logger = logging.getLogger(__name__)

# Minimum confidence floor per layer
_MIN_CONFIDENCE = {
    MemoryLayer.WORKING: 0.0,
    MemoryLayer.EPISODIC: 0.1,
    MemoryLayer.SEMANTIC: 0.6,
    MemoryLayer.PROCEDURAL: 0.4,
}

_LAYER_DIR = Path(".nexusagent") / "layers"


class FileBackedLayer:
    """File-backed memory layer with trust/confidence enforcement."""

    def __init__(self, workspace_dir: str | Path, layer: MemoryLayer) -> None:
        self.layer = layer
        self._workspace = Path(workspace_dir)
        self._dir = self._workspace / _LAYER_DIR / layer.value
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.json"

    def _load_index(self) -> dict[str, dict[str, Any]]:
        if self._index_path.exists():
            try:
                import typing

                return typing.cast(
                    dict[str, dict[str, Any]], json.loads(self._index_path.read_text())
                )
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_index(self, index: dict[str, dict[str, Any]]) -> None:
        try:
            self._index_path.write_text(json.dumps(index, indent=2))
        except OSError as exc:
            logger.warning("Failed to write layer index: %s", exc)

    def put(self, item: LayerMemoryItem) -> str:
        """Persist a memory item. Returns the item id."""
        if item.confidence < _MIN_CONFIDENCE[self.layer]:
            return ""

        if self.layer == MemoryLayer.SEMANTIC:
            if item.provenance.authority.value < TrustLevel.TRUSTED.value:
                return ""
            if not item.can_promote():
                return ""

        item_id = str(item.item.id)
        entry_file = self._dir / f"{item_id}.json"
        payload = {
            "item": item.item.model_dump(),
            "layer": self.layer.value,
            "provenance": item.provenance.to_dict(),
            "confidence": item.confidence,
            "min_confidence": item.min_confidence,
            "tags": item.tags,
            "metadata": item.metadata,
        }
        try:
            entry_file.write_text(json.dumps(payload, indent=2, default=str))
        except OSError as exc:
            logger.warning("Failed to write layer entry %s: %s", item_id, exc)
            return ""

        index = self._load_index()
        index[item_id] = {
            "created_at": item.item.created_at,
            "confidence": item.confidence,
            "layer": self.layer.value,
        }
        self._save_index(index)
        return item_id

    def get(self, item_id: str) -> LayerMemoryItem | None:
        entry_file = self._dir / f"{item_id}.json"
        if not entry_file.exists():
            return None
        try:
            payload = json.loads(entry_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        return self._from_payload(payload)

    def query(self, text: str, *, limit: int = 10) -> list[LayerMemoryItem]:
        results: list[LayerMemoryItem] = []
        try:
            entries = sorted(
                self._dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return results

        for entry_file in entries:
            if entry_file.name == "index.json":
                continue
            try:
                payload = json.loads(entry_file.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            content = ""
            try:
                content = payload.get("item", {}).get("content", "")
            except AttributeError:
                continue
            if text.lower() in content.lower():
                wrapped = self._from_payload(payload)
                if wrapped is not None:
                    results.append(wrapped)
            if len(results) >= limit:
                break
        return results

    def delete(self, item_id: str) -> bool:
        if self.layer in {MemoryLayer.EPISODIC, MemoryLayer.SEMANTIC}:
            return False
        entry_file = self._dir / f"{item_id}.json"
        if not entry_file.exists():
            return False
        try:
            entry_file.unlink()
        except OSError:
            return False
        index = self._load_index()
        index.pop(item_id, None)
        self._save_index(index)
        return True

    def _from_payload(self, payload: dict[str, Any]) -> LayerMemoryItem | None:
        try:
            item_data = payload.get("item", {})
            from nexusagent.memory.memory_item import MemoryItem  # local import avoids cycles

            item = MemoryItem(**item_data)
            provenance = MemoryProvenance.from_dict(payload.get("provenance", {}))
            return LayerMemoryItem(
                item=item,
                layer=MemoryLayer(payload.get("layer", self.layer.value)),
                provenance=provenance,
                confidence=float(payload.get("confidence", 0.5)),
                min_confidence=float(payload.get("min_confidence", _MIN_CONFIDENCE[self.layer])),
                tags=list(payload.get("tags", [])),
                metadata=dict(payload.get("metadata", {})),
            )
        except Exception as exc:
            logger.debug("Failed to decode layer entry: %s", exc)
            return None


class WorkingMemoryBackend(FileBackedLayer):
    """Ephemeral session-scoped memory."""

    def __init__(self, workspace_dir: str | Path) -> None:
        super().__init__(workspace_dir, MemoryLayer.WORKING)


class EpisodicMemoryBackend(FileBackedLayer):
    """Append-only historical event memory."""

    def __init__(self, workspace_dir: str | Path) -> None:
        super().__init__(workspace_dir, MemoryLayer.EPISODIC)

    def delete(self, item_id: str) -> bool:
        return False


class SemanticMemoryBackend(FileBackedLayer):
    """Curated high-confidence factual memory."""

    def __init__(self, workspace_dir: str | Path) -> None:
        super().__init__(workspace_dir, MemoryLayer.SEMANTIC)

    def put(self, item: LayerMemoryItem) -> str:
        if not item.can_promote() or item.confidence < 0.6:
            return ""
        if item.provenance.authority.value < TrustLevel.TRUSTED.value:
            return ""
        return super().put(item)

    def delete(self, item_id: str) -> bool:
        return False


class ProceduralMemoryBackend(FileBackedLayer):
    """Evolved skills/workflows memory."""

    def __init__(self, workspace_dir: str | Path) -> None:
        super().__init__(workspace_dir, MemoryLayer.PROCEDURAL)
