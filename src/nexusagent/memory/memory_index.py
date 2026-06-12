"""Compat shim — imports from memory/index/ subpackage.

All existing ``from nexusagent.memory.memory_index import ...`` usage
continues to work. New code should import from ``nexusagent.memory.index``
(the subpackage) directly.
"""

from nexusagent.memory.index import *  # noqa: F401,F403
from nexusagent.memory.index import (  # noqa: E401
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
    "EMBED_DIM",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "VECTOR_WEIGHT",
    "KEYWORD_WEIGHT",
    "CANDIDATE_MULTIPLIER",
    "EmbeddingProvider",
    "HybridMemoryIndex",
    "_vec_to_blob",
    "_blob_to_vec",
    "_DB_POOL",
]
