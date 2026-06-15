"""Compat shim — imports from memory/index/ subpackage.

All existing ``from nexusagent.memory.memory_index import ...`` usage
continues to work. New code should import from ``nexusagent.memory.index``
(the subpackage) directly.
"""

from nexusagent.memory.index import *  # noqa: F403
from nexusagent.memory.index import (
    EMBED_DIM,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    CANDIDATE_MULTIPLIER,
    KEYWORD_WEIGHT,
    VECTOR_WEIGHT,
    _blob_to_vec,
    _vec_to_blob,
    EmbeddingProvider,
    HybridMemoryIndex,
)

__all__ = [
    "CANDIDATE_MULTIPLIER",
    "CHUNK_OVERLAP",
    "CHUNK_SIZE",
    "EMBED_DIM",
    "KEYWORD_WEIGHT",
    "VECTOR_WEIGHT",
    "_DB_POOL",
    "EmbeddingProvider",
    "HybridMemoryIndex",
    "_blob_to_vec",
    "_vec_to_blob",
]
