"""Hybrid memory search index — FTS5 + sqlite-vec with union merge."""

from .embeddings import (
    EMBED_DIM,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    VECTOR_WEIGHT,
    KEYWORD_WEIGHT,
    CANDIDATE_MULTIPLIER,
    _DB_POOL,
    _vec_to_blob,
    _blob_to_vec,
    EmbeddingProvider,
)
from .index import HybridMemoryIndex

__all__ = [
    # Constants
    "EMBED_DIM",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "VECTOR_WEIGHT",
    "KEYWORD_WEIGHT",
    "CANDIDATE_MULTIPLIER",
    # Classes
    "EmbeddingProvider",
    "HybridMemoryIndex",
    # Helpers
    "_vec_to_blob",
    "_blob_to_vec",
    "_DB_POOL",
]
