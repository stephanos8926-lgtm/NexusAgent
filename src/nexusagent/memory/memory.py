# src/nexusagent/memory/memory.py
"""Memory system compatibility shim.

Exports all public memory classes for backwards compatibility.
"""

from nexusagent.memory.hybrid_memory import HybridMemoryManager
from nexusagent.memory.index import EMBED_DIM
from nexusagent.memory.index import _vec_to_blob as _embed_to_blob
from nexusagent.memory.memory_item import MemoryItem, _hash_embed

__all__ = [
    "HybridMemoryManager",
    "MemoryItem",
    "EMBED_DIM",
    "_embed_to_blob",
    "_hash_embed",
]
