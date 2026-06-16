# src/nexusagent/memory/memory.py
"""Scoped memory system with fork/merge/recall/remember.

Uses SQLite for storage with sqlite-vec for vector similarity search on embeddings.

Compatibility shim — imports from subpackages:
- memory_item: MemoryItem, _hash_embed
- memory_bank: Memory (scoped memory bank)
- memory_manager: MemoryManager (lifecycle management)
- hybrid_memory: HybridMemoryManager (file + index)
- memory.index: EMBED_DIM, _vec_to_blob (re-exported for test compatibility)
"""

from nexusagent.llm.models import MemoryScope
from nexusagent.memory.hybrid_memory import HybridMemoryManager
from nexusagent.memory.index import EMBED_DIM
from nexusagent.memory.index import _vec_to_blob as _embed_to_blob
from nexusagent.memory.memory_bank import Memory
from nexusagent.memory.memory_item import MemoryItem, _hash_embed
from nexusagent.memory.memory_manager import MemoryManager

__all__ = [
    "EMBED_DIM",
    "HybridMemoryManager",
    "Memory",
    "MemoryItem",
    "MemoryManager",
    "MemoryScope",
    "_embed_to_blob",
    "_hash_embed",
]
