"""Hybrid memory search index — FTS5 + sqlite-vec with union merge."""

from .embeddings import (
    _DB_POOL,
    CANDIDATE_MULTIPLIER,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBED_DIM,
    KEYWORD_WEIGHT,
    VECTOR_WEIGHT,
    EmbeddingProvider,
    _blob_to_vec,
    _vec_to_blob,
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
