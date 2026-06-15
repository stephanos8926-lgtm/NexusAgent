"""Embedding provider — Gemini → local → hash fallback chain.

Also provides vector serialization helpers (_vec_to_blob, _blob_to_vec).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import struct
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import sqlite_vec

from nexusagent.infrastructure.config import settings

logger = logging.getLogger(__name__)

EMBED_DIM = 3072  # gemini-embedding-001 returns 3072-dim vectors
CHUNK_SIZE = 400  # chars per chunk (~4 chars per token)
CHUNK_OVERLAP = 80  # overlap between chunks in chars
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
CANDIDATE_MULTIPLIER = 4  # over-fetch factor

# Thread pool for blocking DB operations
# Per-tenant pool cache — keyed by tenant_id (db_path_str)
_DB_POOLS: dict[str, ThreadPoolExecutor] = {}
_DB_POOL_LOCK = __import__("threading").Lock()


def _get_db_pool(tenant_id: str = "default") -> ThreadPoolExecutor:
    """Get or create a per-tenant thread pool for blocking DB operations.

    Each tenant (workspace) gets its own pool so that index operations
    on different workspaces don't contend on a single executor.

    Args:
        tenant_id: Unique tenant/workspace identifier. Defaults to ``"default"``.

    Returns:
        A ``ThreadPoolExecutor`` dedicated to this tenant.
    """
    with _DB_POOL_LOCK:
        pool = _DB_POOLS.get(tenant_id)
        if pool is None:
            pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix=f"memidx-{tenant_id}")
            _DB_POOLS[tenant_id] = pool
    return pool


# Backward-compatible module-level pool (uses tenant "default")
_DB_POOL = _get_db_pool("default")


class EmbeddingProvider:
    """Tiered embedding provider: Gemini → local → hash fallback."""

    def __init__(self):
        """Initialize the embedding provider.

        The local model is lazily loaded on first use to avoid
        importing heavy dependencies unless needed.
        """
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
            # Try loading from ~/.nexusagent/.env first, then project root .env
            env_path = Path.home() / ".nexusagent" / ".env"
            if not env_path.exists():
                from nexusagent.infrastructure.config import get_project_root
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
        # Pad to EMBED_DIM if needed (local model is 384 dim)
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
