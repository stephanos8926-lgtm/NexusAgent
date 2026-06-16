# src/nexusagent/memory/memory_manager.py
"""MemoryManager — lifecycle management for Memory instances."""

import logging
import sqlite3
from typing import Any

import sqlite_vec

from nexusagent.llm.models import MemoryScope
from nexusagent.memory.index import EMBED_DIM
from nexusagent.memory.memory_bank import Memory

logger = logging.getLogger(__name__)


class MemoryManager:
    """Create and manage Memory instances backed by a single SQLite file."""

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize the memory manager.

        Args:
            db_path: Path to the SQLite database file. Defaults to
                ``:memory:`` for an in-memory database.
        """
        self.db_path = db_path
        self._memories: dict[str, Memory] = {}

    async def create(
        self,
        memory_id: str,
        scope: MemoryScope = MemoryScope.ISOLATED,
        parent_memory_id: str | None = None,
    ) -> Memory:
        """Create a new Memory instance and initialise its DB if needed."""
        mem = Memory(
            memory_id=memory_id,
            scope=scope,
            db_path=self.db_path,
            parent_memory_id=parent_memory_id,
        )
        mem._conn = self._init_db(self.db_path)
        self._memories[memory_id] = mem
        return mem

    @staticmethod
    def _init_db(db_path: str) -> Any:
        """Open (or create) the SQLite DB and ensure the schema + vec index exist."""
        conn = sqlite3.connect(db_path)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)

        conn.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "id TEXT PRIMARY KEY, "
            "memory_id TEXT NOT NULL, "
            "content TEXT NOT NULL, "
            "metadata TEXT DEFAULT '{}', "
            "created_at TEXT NOT NULL, "
            "embedding BLOB)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_memory_id ON memories (memory_id)")

        # sqlite-vec virtual table — we shadow the base table for vector search
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories USING vec0("
            f"embedding float[{EMBED_DIM}], "
            f"id text, "
            f"memory_id text, "
            f"content text, "
            f"metadata text, "
            f"created_at text)"
        )

        # Keep vec_memories in sync via triggers
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_memories_insert AFTER INSERT ON memories "
            "BEGIN "
            "INSERT INTO vec_memories (id, embedding, memory_id, content, metadata, created_at) "
            "VALUES (new.id, new.embedding, new.memory_id, new.content, new.metadata, new.created_at); "
            "END"
        )
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_memories_delete AFTER DELETE ON memories "
            "BEGIN "
            "DELETE FROM vec_memories WHERE id = old.id; "
            "END"
        )
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_memories_update AFTER UPDATE ON memories "
            "BEGIN "
            "DELETE FROM vec_memories WHERE id = old.id; "
            "INSERT INTO vec_memories (id, embedding, memory_id, content, metadata, created_at) "
            "VALUES (new.id, new.embedding, new.memory_id, new.content, new.metadata, new.created_at); "
            "END"
        )

        conn.commit()
        return conn

    def get(self, memory_id: str) -> Memory | None:
        """Retrieve a previously created Memory instance by ID.

        Args:
            memory_id: The unique identifier of the memory bank.

        Returns:
            The ``Memory`` instance if found, otherwise ``None``.
        """
        return self._memories.get(memory_id)

    async def close(self) -> None:
        """Close all managed memory connections and clear the registry."""
        for mem in self._memories.values():
            if mem._conn is not None:
                mem._conn.close()
                mem._conn = None
        self._memories.clear()
