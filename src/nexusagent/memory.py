"""Scoped memory system with fork/merge/recall/remember.

Uses SQLite for storage with sqlite-vec for vector similarity search on embeddings.
"""

import hashlib
import json
import logging
import struct
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlite_vec
from pydantic import BaseModel, Field

from nexusagent.models import MemoryScope

logger = logging.getLogger(__name__)

EMBED_DIM = 3072  # Must match memory_index.py for cross-compatibility

# ---------------------------------------------------------------------------
# Deterministic hash-based embedding (placeholder)
# NOTE: This should be replaced with a real embedding model in production.
# ---------------------------------------------------------------------------


def _hash_embed(text: str) -> list[float]:
    """Deterministic hash-based embedding function.

    Produces a unit-normalised vector of dimension EMBED_DIM from the input text.
    This is a placeholder — replace with a proper embedding model in production.
    """
    import struct as _struct

    vec = [0.0] * EMBED_DIM
    # Fill dims in batches of 32 using SHA256
    for batch_idx, batch_start in enumerate(range(0, EMBED_DIM, 32)):
        h = hashlib.sha256(f"{text}|{batch_idx}".encode()).digest()
        for j in range(min(32, EMBED_DIM - batch_start)):
            vec[batch_start + j] = _struct.unpack("b", bytes([h[j]]))[0] / 128.0

    # Normalise to unit length
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _embed_to_blob(vec: list[float]) -> bytes:
    """Pack a float32 vector into a BLOB for sqlite-vec storage."""
    return struct.pack(f"{len(vec)}f", *vec)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class MemoryItem(BaseModel):
    """A single memory entry."""

    id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    embedding: list[float] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Memory — a scoped memory bank backed by SQLite + sqlite-vec
# ---------------------------------------------------------------------------


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

    async def remember(self, content: str, metadata: dict[str, Any] | None = None) -> str:
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

            existing = {
                r[0]
                for r in conn.execute(
                    "SELECT content FROM memories WHERE memory_id = ?", (target_id,)
                ).fetchall()
            }
            moved = 0
            for row_id, content, _meta_json, _created_at, _emb_blob in rows:
                if content not in existing:
                    conn.execute(
                        "UPDATE memories SET memory_id = ? WHERE id = ?",
                        (target_id, row_id),
                    )
                    existing.add(content)
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


# ---------------------------------------------------------------------------
# MemoryManager — lifecycle management
# ---------------------------------------------------------------------------


class MemoryManager:
    """Create and manage Memory instances backed by a single SQLite file."""

    def __init__(self, db_path: str = ":memory:") -> None:
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
        import sqlite3

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
        return self._memories.get(memory_id)

    async def close(self) -> None:
        for mem in self._memories.values():
            if mem._conn is not None:
                mem._conn.close()
                mem._conn = None
        self._memories.clear()


# ---------------------------------------------------------------------------
# HybridMemoryManager — combines FileMemory + HybridMemoryIndex
# ---------------------------------------------------------------------------


class HybridMemoryManager:
    """Combines file-based memory (canonical) with hybrid search index (derived).

    This is the top-level memory interface for the hybrid memory system.
    Files are the source of truth; the SQLite index is rebuilt from them.
    """

    def __init__(self, workspace_dir: str):
        from nexusagent.memory_files import FileMemory
        from nexusagent.memory_index import HybridMemoryIndex

        self.workspace_dir = workspace_dir
        self.file_memory = FileMemory(workspace_dir)
        self.index = HybridMemoryIndex(workspace_dir)

    def initialize(self):
        """Initialize the file memory layer."""
        self.file_memory.initialize()

    async def remember(
        self,
        content: str,
        type: str,
        description: str,
        confidence: float | None = None,
        entities: list[str] | None = None,
    ) -> str:
        """Write a memory entry and index it using the full async embedding chain.

        Returns the file path of the written entry.
        """
        from nexusagent.memory_files import MemoryEntryType

        entry_type = MemoryEntryType(type)
        filepath = self.file_memory.write_entry(
            content=content,
            entry_type=entry_type,
            description=description,
            confidence=confidence,
            entities=entities,
        )
        # Index the file that was just written — async with Gemini embeddings
        rel_path = filepath.replace(self.workspace_dir, "").lstrip("/")
        await self.index.async_index_file(rel_path)
        return filepath

    async def recall(self, query: str, max_results: int = 6) -> list[dict]:
        """Search memory using hybrid keyword + vector search.

        Returns results with citations (file, content, score).
        """
        return await self.index.search(query, max_results=max_results)

    def get_memory_context(self, query: str, max_results: int = 5) -> str:
        """Format recall results as a context string for prompt injection.

        Includes source citations in the format 'Source: bank/filename.md'.
        """
        results = self.index.search_sync(query, max_results=max_results)
        if not results:
            return ""

        lines = ["## Relevant Memories\n"]
        for r in results:
            source = r.get("file", "unknown")
            content = r.get("content", "").strip()
            score = r.get("score", 0)
            lines.append(f"Source: {source} (score: {score:.2f})")
            lines.append(f"{content}\n")

        return "\n".join(lines)

    async def flush(self, session_summary: str):
        """Persist a session summary to the daily log and re-index.

        Uses async embedding (Gemini → local → hash fallback) for the re-index
        step so that stored vectors match query vectors.
        """
        self.file_memory.append_daily_log(session_summary)
        # Re-index the daily log file — async with full embedding chain
        from datetime import UTC, datetime

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        rel_path = f"memory/{today}.md"
        await self.index.async_index_file(rel_path)
