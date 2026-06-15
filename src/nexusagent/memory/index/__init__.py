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
    "CANDIDATE_MULTIPLIER",
    "CHUNK_OVERLAP",
    "CHUNK_SIZE",
    # Constants
    "EMBED_DIM",
    "KEYWORD_WEIGHT",
    "VECTOR_WEIGHT",
    "_DB_POOL",
    # Classes
    "EmbeddingProvider",
    "HybridMemoryIndex",
    "_blob_to_vec",
    # Helpers
    "_vec_to_blob",
]
