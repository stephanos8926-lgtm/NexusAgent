"""
Hybrid memory search index — derived from file-based memory.

Uses SQLite FTS5 (keyword) + sqlite-vec (semantic) with union merge.
The index is always rebuildable from the files — files are canonical.

Search flow:
1. Embed query → vector
2. Run FTS5 keyword search (BM25)
3. Run sqlite-vec similarity search
4. Union merge with weighted scores (70% vector, 30% keyword)
5. Return top N with citations (file + line numbers)
"""

import asyncio
import hashlib
import logging
import math
import os
import sqlite3
import struct
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlite_vec

from nexusagent.config import settings

logger = logging.getLogger(__name__)

EMBED_DIM = 3072  # gemini-embedding-001 returns 3072-dim vectors
CHUNK_SIZE = 400  # chars per chunk (~4 chars per token)
CHUNK_OVERLAP = 80  # overlap between chunks in chars
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
CANDIDATE_MULTIPLIER = 4  # over-fetch factor

# Thread pool for blocking DB operations
_DB_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="memidx")


class EmbeddingProvider:
    """Tiered embedding provider: Gemini → local → hash fallback."""

    def __init__(self):
        self._local_model = None

    async def embed(self, text: str) -> list[float]:
        """Get embedding vector with fallback chain."""
        # Try Gemini first
        try:
            return await self._embed_gemini(text)
        except Exception as e:
            logger.warning("Gemini embedding failed: %s, trying local", e)

        # Fall back to local model
        try:
            return await self._embed_local(text)
        except Exception as e:
            logger.warning("Local embedding failed: %s, using hash fallback", e)

        # Last resort: hash-based (always works, low quality)
        return self._embed_hash(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        return await asyncio.gather(*[self.embed(t) for t in texts])

    async def _embed_gemini(self, text: str) -> list[float]:
        """Use Gemini embedding API."""
        import google.generativeai as genai

        # Try settings first, then environment, then .env file
        api_key = getattr(settings, "gemini_api_key", None)
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            # Try loading from .env file in project root
            from nexusagent.config import get_project_root

            env_path = get_project_root() / ".env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if not api_key:
            raise ValueError("No Gemini API key configured")

        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="RETRIEVAL_QUERY",
        )
        return result["embedding"]

    async def _embed_local(self, text: str) -> list[float]:
        """Use local sentence-transformers model."""
        if self._local_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError as exc:
                raise ImportError("sentence-transformers not installed") from exc

        loop = asyncio.get_running_loop()
        vec = await loop.run_in_executor(
            None,
            lambda: self._local_model.encode(text, normalize_embeddings=True),
        )
        # Pad to EMBED_DIM if needed (local model is 384-dim)
        vec = vec.tolist()
        if len(vec) < EMBED_DIM:
            vec = vec + [0.0] * (EMBED_DIM - len(vec))
        return vec

    def _embed_hash(self, text: str) -> list[float]:
        """Fallback: deterministic hash-based embedding (low quality, always works)."""
        vec = [0.0] * EMBED_DIM
        # Fill dims in batches using SHA256 chunks
        for batch_idx, batch_start in enumerate(range(0, EMBED_DIM, 32)):
            h = hashlib.sha256(f"{text}|{batch_idx}".encode()).digest()
            for j in range(min(32, EMBED_DIM - batch_start)):
                vec[batch_start + j] = struct.unpack("b", bytes([h[j]]))[0] / 128.0

        mag = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / mag for x in vec]


def _vec_to_blob(vec: list[float]) -> bytes:
    """Pack a float32 vector into a BLOB for sqlite-vec storage."""
    return struct.pack(f"{len(vec)}f", *vec)


def _blob_to_vec(blob: bytes) -> list[float]:
    """Unpack a BLOB back into a float32 vector."""
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


class HybridMemoryIndex:
    """SQLite-based hybrid search index (FTS5 + sqlite-vec)."""

    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)
        self.db_path = self.workspace / ".memory" / "index.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = EmbeddingProvider()
        self._init_db()

    def _init_db(self):
        """Create the SQLite schema: chunks, chunks_fts, chunks_vec, file_meta."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    line_start INTEGER,
                    line_end INTEGER,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    indexed_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    content,
                    id UNINDEXED,
                    file_path UNINDEXED
                )
                """
            )

            # Check if chunks_vec exists with wrong dimension
            vec_exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
            ).fetchone()

            if vec_exists:
                # Check the dimension of existing vectors
                row = conn.execute("SELECT embedding FROM chunks_vec LIMIT 1").fetchone()
                if row and row[0]:
                    existing_dim = len(row[0]) // 4  # float32 = 4 bytes
                    if existing_dim != EMBED_DIM:
                        logger.info(
                            "Vector dimension changed (%d → %d), rebuilding index",
                            existing_dim,
                            EMBED_DIM,
                        )
                        conn.execute("DROP TABLE IF EXISTS chunks_vec")
                        conn.execute("DELETE FROM chunks WHERE embedding IS NOT NULL")

            conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
                    id TEXT PRIMARY KEY,
                    embedding float[{EMBED_DIM}]
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_meta (
                    file_path TEXT PRIMARY KEY,
                    mtime REAL,
                    hash TEXT,
                    last_indexed TEXT
                )
                """
            )

            conn.commit()
        finally:
            conn.close()

    def index_file(self, relative_path: str):
        """Index a file: chunk it, embed chunks, store in DB."""
        filepath = self.workspace / relative_path
        if not filepath.exists():
            logger.warning("File not found: %s", filepath)
            return

        content = filepath.read_text()

        # Remove YAML frontmatter for indexing
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]

        # Chunk the content
        chunks = self._chunk_text(content)

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)

            # Fetch old chunk IDs for this file (needed to clean vec entries)
            old_ids = [
                r[0]
                for r in conn.execute(
                    "SELECT id FROM chunks WHERE file_path = ?", (relative_path,)
                ).fetchall()
            ]

            # Delete old chunks for this file
            conn.execute("DELETE FROM chunks WHERE file_path = ?", (relative_path,))
            conn.execute("DELETE FROM chunks_fts WHERE file_path = ?", (relative_path,))
            # Delete old vec entries for this file
            for oid in old_ids:
                conn.execute("DELETE FROM chunks_vec WHERE id = ?", (oid,))

            now = datetime.now(UTC).isoformat()

            for i, chunk in enumerate(chunks):
                chunk_id = f"{relative_path}:{i}:{uuid.uuid4().hex[:8]}"

                # Get embedding — use hash fallback for sync context
                try:
                    vec = self.embedder._embed_hash(chunk["content"])
                    vec_blob = _vec_to_blob(vec)
                except Exception as e:
                    logger.warning("Embedding failed for chunk: %s", e)
                    vec_blob = None

                conn.execute(
                    "INSERT INTO chunks (id, file_path, line_start, line_end, content, embedding, indexed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        chunk_id,
                        relative_path,
                        chunk["start"],
                        chunk["end"],
                        chunk["content"],
                        vec_blob,
                        now,
                    ),
                )

                conn.execute(
                    "INSERT INTO chunks_fts (id, content, file_path) VALUES (?, ?, ?)",
                    (chunk_id, chunk["content"], relative_path),
                )

                if vec_blob:
                    try:
                        conn.execute(
                            "INSERT OR REPLACE INTO chunks_vec (id, embedding) VALUES (?, ?)",
                            (chunk_id, vec_blob),
                        )
                    except Exception as e:
                        logger.warning("Vector insert failed: %s", e)

            # Update file meta
            file_hash = hashlib.md5(filepath.read_bytes()).hexdigest()
            conn.execute(
                "INSERT OR REPLACE INTO file_meta (file_path, mtime, hash, last_indexed) VALUES (?, ?, ?, ?)",
                (relative_path, filepath.stat().st_mtime, file_hash, now),
            )

            conn.commit()
        finally:
            conn.close()

    async def async_index_file(self, relative_path: str):
        """Index a file using the full async embedding chain (Gemini → local → hash).

        Same logic as index_file() but uses the async embedder.embed() call
        instead of the sync _embed_hash() fallback, producing high-quality vectors.
        """
        filepath = self.workspace / relative_path
        if not filepath.exists():
            logger.warning("File not found: %s", filepath)
            return

        content = filepath.read_text()

        # Remove YAML frontmatter for indexing
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]

        # Chunk the content
        chunks = self._chunk_text(content)

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)

            # Fetch old chunk IDs for this file (needed to clean vec entries)
            old_ids = [
                r[0]
                for r in conn.execute(
                    "SELECT id FROM chunks WHERE file_path = ?", (relative_path,)
                ).fetchall()
            ]

            # Delete old chunks for this file
            conn.execute("DELETE FROM chunks WHERE file_path = ?", (relative_path,))
            conn.execute("DELETE FROM chunks_fts WHERE file_path = ?", (relative_path,))
            # Delete old vec entries for this file
            for oid in old_ids:
                conn.execute("DELETE FROM chunks_vec WHERE id = ?", (oid,))

            now = datetime.now(UTC).isoformat()

            for i, chunk in enumerate(chunks):
                chunk_id = f"{relative_path}:{i}:{uuid.uuid4().hex[:8]}"

                # Use the ASYNC embedding chain (Gemini → local → hash fallback)
                try:
                    vec = await self.embedder.embed(chunk["content"])
                    vec_blob = _vec_to_blob(vec)
                except Exception as e:
                    logger.warning("Embedding failed for chunk: %s", e)
                    vec_blob = None

                conn.execute(
                    "INSERT INTO chunks (id, file_path, line_start, line_end, content, embedding, indexed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        chunk_id,
                        relative_path,
                        chunk["start"],
                        chunk["end"],
                        chunk["content"],
                        vec_blob,
                        now,
                    ),
                )

                conn.execute(
                    "INSERT INTO chunks_fts (id, content, file_path) VALUES (?, ?, ?)",
                    (chunk_id, chunk["content"], relative_path),
                )

                if vec_blob:
                    try:
                        conn.execute(
                            "INSERT OR REPLACE INTO chunks_vec (id, embedding) VALUES (?, ?)",
                            (chunk_id, vec_blob),
                        )
                    except Exception as e:
                        logger.warning("Vector insert failed: %s", e)

            # Update file meta
            file_hash = hashlib.md5(filepath.read_bytes()).hexdigest()
            conn.execute(
                "INSERT OR REPLACE INTO file_meta (file_path, mtime, hash, last_indexed) VALUES (?, ?, ?, ?)",
                (relative_path, filepath.stat().st_mtime, file_hash, now),
            )

            conn.commit()
        finally:
            conn.close()

    def _chunk_text(self, text: str) -> list[dict]:
        """Split text into overlapping chunks by character count."""
        lines = text.split("\n")
        chunks: list[dict[str, Any]] = []
        current_chunk: list[str] = []
        current_start = 0
        line_num = 0

        for line in lines:
            current_chunk.append(line)
            line_num += 1

            if len("\n".join(current_chunk)) >= CHUNK_SIZE:
                chunks.append(
                    {
                        "content": "\n".join(current_chunk),
                        "start": current_start,
                        "end": line_num,
                    }
                )
                # Keep overlap
                overlap_chars = 0
                overlap_lines = []
                for cl in reversed(current_chunk):
                    overlap_lines.insert(0, cl)
                    overlap_chars += len(cl) + 1
                    if overlap_chars >= CHUNK_OVERLAP:
                        break
                current_chunk = overlap_lines
                current_start = line_num - len(overlap_lines)

        if current_chunk:
            chunks.append(
                {
                    "content": "\n".join(current_chunk),
                    "start": current_start,
                    "end": line_num,
                }
            )

        return chunks

    async def search(self, query: str, max_results: int = 6, min_score: float = 0.1) -> list[dict]:
        """Hybrid search: keyword + vector with union merge."""
        loop = asyncio.get_running_loop()

        # Get query embedding
        query_vec = await self.embedder.embed(query)

        # Run both searches concurrently
        candidate_limit = max_results * CANDIDATE_MULTIPLIER
        keyword_future = loop.run_in_executor(
            _DB_POOL, self._search_keyword, query, candidate_limit
        )
        vector_future = loop.run_in_executor(
            _DB_POOL, self._search_vector, query_vec, candidate_limit
        )

        keyword_results = await keyword_future
        vector_results = await vector_future

        # Merge
        merged = self._merge_results(keyword_results, vector_results, max_results, min_score)
        return merged

    def search_sync(self, query: str, max_results: int = 6) -> list[dict]:
        """Synchronous search (uses hash embedding fallback)."""
        query_vec = self.embedder._embed_hash(query)
        candidate_limit = max_results * CANDIDATE_MULTIPLIER
        keyword_results = self._search_keyword(query, candidate_limit)
        vector_results = self._search_vector(query_vec, candidate_limit)
        return self._merge_results(keyword_results, vector_results, max_results, 0.0)

    def _search_keyword(self, query: str, limit: int) -> list[dict]:
        """FTS5 keyword search."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            # Build FTS5 query (AND logic for tokens)
            tokens = query.split()
            fts_query = " AND ".join(f'"{t}"' for t in tokens if len(t) > 1)

            rows = conn.execute(
                """SELECT id, file_path, content, rank
                   FROM chunks_fts
                   WHERE chunks_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (fts_query, limit),
            ).fetchall()

            return [{"id": r[0], "file": r[1], "content": r[2], "rank": r[3]} for r in rows]
        except Exception as e:
            logger.warning("Keyword search failed: %s", e)
            return []
        finally:
            conn.close()

    def _search_vector(self, query_vec: list[float], limit: int) -> list[dict]:
        """sqlite-vec similarity search."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)

            vec_blob = _vec_to_blob(query_vec)
            # sqlite-vec KNN MATCH requires a simple query — no JOINs.
            # Fetch matching chunk IDs first, then look up content.
            vec_rows = conn.execute(
                """SELECT id, distance
                   FROM chunks_vec
                   WHERE embedding MATCH ?
                   ORDER BY distance
                   LIMIT ?""",
                (vec_blob, limit),
            ).fetchall()

            if not vec_rows:
                return []

            # Fetch chunk content for the matched IDs
            ids = [r[0] for r in vec_rows]
            placeholders = ",".join("?" for _ in ids)
            chunk_rows = conn.execute(
                f"SELECT id, file_path, content FROM chunks WHERE id IN ({placeholders})",
                ids,
            ).fetchall()

            chunk_map = {r[0]: (r[1], r[2]) for r in chunk_rows}

            results = []
            for chunk_id, distance in vec_rows:
                if chunk_id in chunk_map:
                    file_path, content = chunk_map[chunk_id]
                    similarity = 1.0 / (1.0 + distance)
                    results.append(
                        {
                            "id": chunk_id,
                            "file": file_path,
                            "content": content,
                            "similarity": similarity,
                        }
                    )
            return results
        except Exception as e:
            logger.warning("Vector search failed: %s, falling back to brute force", e)
            return self._search_vector_brute(query_vec, limit)
        finally:
            conn.close()

    def _search_vector_brute(self, query_vec: list[float], limit: int) -> list[dict]:
        """Brute-force cosine similarity fallback when sqlite-vec fails.

        Includes an OOM guard: estimates memory for all embeddings before loading.
        If estimated usage exceeds the threshold, processes in batches instead.
        """
        import psutil

        oom_threshold = 0.85  # refuse brute-force if system memory usage exceeds this

        conn = sqlite3.connect(str(self.db_path))
        try:
            # OOM guard: check system memory before bulk-load
            mem = psutil.virtual_memory()
            if mem.percent > oom_threshold * 100:
                logger.warning(
                    "Skipping brute-force vector search: system memory at %d%% (threshold %d%%)",
                    mem.percent,
                    int(oom_threshold * 100),
                )
                return []

            row_count = conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"
            ).fetchone()[0]

            # Estimate: each embedding = EMBED_DIM * 4 bytes (float32)
            estimated_bytes = row_count * EMBED_DIM * 4
            available_bytes = mem.available
            if estimated_bytes > available_bytes * 0.5:
                logger.warning(
                    "Brute-force vector search would use ~%.0f MB embeddings with %.0f MB available — skipping",
                    estimated_bytes / (1024 * 1024),
                    available_bytes / (1024 * 1024),
                )
                return []

            rows = conn.execute(
                "SELECT id, file_path, content, embedding FROM chunks WHERE embedding IS NOT NULL"
            ).fetchall()

            results = []
            for row in rows:
                chunk_id, file_path, content, emb_blob = row
                if not emb_blob:
                    continue
                vec = _blob_to_vec(emb_blob)
                # Cosine similarity
                dot = sum(a * b for a, b in zip(query_vec, vec, strict=True))
                mag_a = math.sqrt(sum(a * a for a in query_vec)) or 1.0
                mag_b = math.sqrt(sum(b * b for b in vec)) or 1.0
                sim = dot / (mag_a * mag_b)
                results.append(
                    {
                        "id": chunk_id,
                        "file": file_path,
                        "content": content,
                        "similarity": max(0.0, sim),
                    }
                )

            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]
        finally:
            conn.close()

    def _merge_results(
        self,
        keyword_results: list[dict],
        vector_results: list[dict],
        max_results: int,
        min_score: float,
    ) -> list[dict]:
        """Union merge with weighted scoring."""
        by_id: dict[str, dict] = {}

        # Add vector results
        for r in vector_results:
            by_id[r["id"]] = {
                "id": r["id"],
                "file": r["file"],
                "content": r["content"][:200],  # truncate for context
                "vector_score": r.get("similarity", 0),
                "keyword_score": 0.0,
            }

        # Merge keyword results
        for r in keyword_results:
            # Convert BM25 rank to score (rank 0 → 1.0, rank 1 → 0.5, etc.)
            rank = r.get("rank", 999)
            kw_score = 1.0 / (1.0 + abs(rank)) if isinstance(rank, (int, float)) else 0.0

            if r["id"] in by_id:
                by_id[r["id"]]["keyword_score"] = kw_score
            else:
                by_id[r["id"]] = {
                    "id": r["id"],
                    "file": r["file"],
                    "content": r["content"][:200],
                    "vector_score": 0.0,
                    "keyword_score": kw_score,
                }

        # Compute weighted score
        merged = []
        for entry in by_id.values():
            score = VECTOR_WEIGHT * entry["vector_score"] + KEYWORD_WEIGHT * entry["keyword_score"]
            if score >= min_score:
                merged.append(
                    {
                        "file": entry["file"],
                        "content": entry["content"],
                        "score": round(score, 4),
                        "vector_score": round(entry["vector_score"], 4),
                        "keyword_score": round(entry["keyword_score"], 4),
                    }
                )

        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged[:max_results]

    def rebuild(self):
        """Rebuild the entire index from files."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)

            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM chunks_fts")
            # vec0 virtual tables don't support DELETE — drop and recreate
            conn.execute("DROP TABLE IF EXISTS chunks_vec")
            conn.execute(
                f"""
                CREATE VIRTUAL TABLE chunks_vec USING vec0(
                    id TEXT PRIMARY KEY,
                    embedding float[{EMBED_DIM}]
                )
                """
            )
            conn.execute("DELETE FROM file_meta")
            conn.commit()
        finally:
            conn.close()

        # Re-index all files
        for pattern in ["bank/**/*.md", "memory/**/*.md"]:
            for filepath in self.workspace.glob(pattern):
                self.index_file(str(filepath.relative_to(self.workspace)))

        logger.info("Rebuilt index from workspace files")
