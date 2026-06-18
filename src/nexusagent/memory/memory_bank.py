# src/nexusagent/memory/memory_bank.py
"""Scoped memory bank backed by SQLite + sqlite-vec."""

import json
import logging
import struct
import uuid
from datetime import UTC, datetime
from typing import Any

from nexusagent.llm.models import MemoryScope
from nexusagent.memory.index import EMBED_DIM, _vec_to_blob as _embed_to_blob
from nexusagent.memory.memory_item import MemoryItem, _hash_embed

logger = logging.getLogger(__name__)


class Memory:
    """Scoped memory bank.

    - **shared**:    read/write to the shared bank (memory_id = "shared")
    - **isolated**:  read/write only own memory_id
    - **scoped**:    read from parent (if set) + self; write only to self
    """

    def __init__(
        self,
        memory_id: str,
        scope: MemoryScope,
        db_path: str,
        parent_memory_id: str | None = None,
        conn: Any = None,
    ) -> None:
        """Initialize a scoped memory bank.

        Args:
            memory_id: Unique identifier for this memory bank.
            scope: Access scope (shared, isolated, or scoped).
            db_path: Path to the SQLite database file.
            parent_memory_id: Optional parent bank ID for scoped access.
            conn: Optional existing SQLite connection to reuse.
        """
        self.memory_id = memory_id
        self.scope = scope
        self.db_path = db_path
        self.parent_memory_id = parent_memory_id
        self._conn: Any = conn  # sqlite3.Connection (set by MemoryManager or fork)

    # -- internal helpers ----------------------------------------------------

    def _get_connection(self) -> Any:
        if self._conn is None:
            raise RuntimeError("Memory not initialised — use MemoryManager.create()")
        return self._conn

    def _read_memory_ids(self) -> list[str]:
        """Return the list of memory_ids this Memory instance can read from."""
        if self.scope == MemoryScope.SHARED:
            return ["shared"]
        if self.scope == MemoryScope.ISOLATED:
            return [self.memory_id]
        # scoped: read from self first, then parent
        ids = [self.memory_id]
        if self.parent_memory_id:
            ids.append(self.parent_memory_id)
        return ids

    def _write_memory_id(self) -> str:
        """Return the memory_id this instance writes to."""
        if self.scope == MemoryScope.SHARED:
            return "shared"
        return self.memory_id

    # -- public async API ----------------------------------------------------

    async def remember(self, content: str, metadata: dict | None = None) -> str:
        """Store a new memory entry. Returns the item id."""
        conn = self._get_connection()
        item_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        meta_json = json.dumps(metadata or {})
        embedding = _hash_embed(content)
        blob = _embed_to_blob(embedding)
        write_id = self._write_memory_id()

        conn.execute(
            "INSERT INTO memories (id, memory_id, content, metadata, created_at, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, write_id, content, meta_json, now, blob),
        )
        conn.commit()
        logger.debug("Remembered [%s] in memory %s", item_id, write_id)
        return item_id

    async def recall(self, query: str, limit: int = 5) -> list[MemoryItem]:
        """Recall memories similar to *query* using vector similarity."""
        conn = self._get_connection()
        read_ids = self._read_memory_ids()
        query_embedding = _hash_embed(query)
        query_blob = _embed_to_blob(query_embedding)

        # Build parameterised IN clause
        placeholders = ",".join("?" for _ in read_ids)
        sql = (
            f"SELECT id, memory_id, content, metadata, created_at, embedding, distance "
            f"FROM vec_memories "
            f"WHERE memory_id IN ({placeholders}) AND embedding MATCH ? "
            f"ORDER BY distance LIMIT ?"
        )
        rows = conn.execute(sql, [*read_ids, query_blob, limit]).fetchall()

        results: list[MemoryItem] = []
        for row in rows:
            row_id, _mid, content, meta_json, created_at, emb_blob, _dist = row
            emb: list[float] = []
            if emb_blob:
                emb = list(struct.unpack(f"{EMBED_DIM}f", emb_blob))
            results.append(
                MemoryItem(
                    id=row_id,
                    content=content,
                    metadata=json.loads(meta_json) if meta_json else {},
                    created_at=created_at,
                    embedding=emb,
                )
            )
        return results

    async def reflect(self) -> str:
        """Return a JSON summary of all memories in this scope."""
        conn = self._get_connection()
        read_ids = self._read_memory_ids()
        placeholders = ",".join("?" for _ in read_ids)
        rows = conn.execute(
            f"SELECT id, content, metadata, created_at FROM memories "
            f"WHERE memory_id IN ({placeholders}) ORDER BY created_at",
            read_ids,
        ).fetchall()

        items = [
            {
                "id": r[0],
                "content": r[1],
                "metadata": json.loads(r[2]) if r[2] else {},
                "created_at": r[3],
            }
            for r in rows
        ]
        return json.dumps(
            {"memory_id": self.memory_id, "scope": self.scope, "count": len(items), "items": items}
        )

    async def fork(self, scope: MemoryScope = MemoryScope.SCOPED) -> "Memory":
        """Create a child memory whose parent is this memory."""
        child_id = str(uuid.uuid4())
        child = Memory(
            memory_id=child_id,
            scope=scope,
            db_path=self.db_path,
            parent_memory_id=self.memory_id,
            conn=self._conn,  # Share parent's connection — no leak
        )
        return child

    async def merge(self, child: "Memory", strategy: str = "selective") -> int:
        """Merge *child*'s memories into this memory. Returns count moved."""
        conn = self._get_connection()
        child_id = child.memory_id
        target_id = self._write_memory_id()

        if strategy == "selective":
            # Only merge items whose content does not already exist in target
            rows = conn.execute(
                "SELECT id, content, metadata, created_at, embedding FROM memories WHERE memory_id = ?",
                (child_id,),
            ).fetchall()

            # Build set of existing content in target for O(1) lookup
            existing_content = {
                r[0]
                for r in conn.execute(
                    "SELECT content FROM memories WHERE memory_id = ?", (target_id,)
                ).fetchall()
            }
            moved = 0
            for row_id, content, _meta_json, _created_at, _emb_blob in rows:
                if content not in existing_content:
                    conn.execute(
                        "UPDATE memories SET memory_id = ? WHERE id = ?",
                        (target_id, row_id),
                    )
                    existing_content.add(content)
                    moved += 1
            conn.commit()
            return moved

        # "all" strategy — move everything
        cursor = conn.execute(
            "UPDATE memories SET memory_id = ? WHERE memory_id = ?",
            (target_id, child_id),
        )
        conn.commit()
        return cursor.rowcount
