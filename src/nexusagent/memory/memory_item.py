# src/nexusagent/memory/memory_item.py
"""MemoryItem data model and hash-based embedding helper."""

import hashlib
import math
import struct

from pydantic import BaseModel, Field

from nexusagent.memory.index import EMBED_DIM, _vec_to_blob as _embed_to_blob


def _hash_embed(text: str) -> list[float]:
    """Deterministic hash-based embedding function.

    Produces a unit-normalised vector of dimension EMBED_DIM from the input text.
    This is a placeholder — replace with a proper embedding model in production.
    """
    vec = [0.0] * EMBED_DIM
    # Fill dims in batches of 32 using SHA256
    for batch_idx, batch_start in enumerate(range(0, EMBED_DIM, 32)):
        h = hashlib.sha256(f"{text}|{batch_idx}".encode()).digest()
        for j in range(min(32, EMBED_DIM - batch_start)):
            vec[batch_start + j] = struct.unpack("b", bytes([h[j]]))[0] / 128.0

    # Normalise to unit length
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class MemoryItem(BaseModel):
    """A single memory entry.

    Attributes:
        id: Unique identifier (UUID string).
        content: The memory text content.
        metadata: Arbitrary key-value metadata attached to the entry.
        created_at: ISO-8601 timestamp of when the entry was created.
        embedding: Optional embedding vector for similarity search.
    """

    id: str
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: str
    embedding: list[float] = Field(default_factory=list)
