"""Memory item data model and deterministic hash embedding."""

from __future__ import annotations

import hashlib
import math
import struct
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from nexusagent.memory.index import EMBED_DIM


def _hash_embed(text: str) -> list[float]:
    """Deterministic hash-based embedding placeholder."""
    vec = [0.0] * EMBED_DIM
    for batch_idx, batch_start in enumerate(range(0, EMBED_DIM, 32)):
        h = hashlib.sha256(f"{text}|{batch_idx}".encode()).digest()
        for j in range(min(32, EMBED_DIM - batch_start)):
            vec[batch_start + j] = struct.unpack("b", bytes([h[j]]))[0] / 128.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class MemoryItem(BaseModel):
    """A single memory entry."""

    id: str = Field(default_factory=lambda: MemoryItem.generate_id())
    content: str = ""
    metadata: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: MemoryItem.now_iso())
    embedding: list[float] = Field(default_factory=list)

    @staticmethod
    def generate_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()
