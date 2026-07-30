"""Embedding provider abstraction and implementations.

Providers are selected via config: `embedding.provider = "gemini" | "rw_ie" | "local" | "hash"`
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import struct
import typing
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from nexusagent.infrastructure.config import settings

logger = logging.getLogger(__name__)

# Target dimension for storage (Gemini default)
EMBED_DIM = 3072
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
CANDIDATE_MULTIPLIER = 4

# Thread pool for blocking DB operations
_DB_POOLS: dict[str, ThreadPoolExecutor] = {}
_DB_POOL_LOCK = __import__("threading").Lock()


def _get_db_pool(tenant_id: str = "default") -> ThreadPoolExecutor:
    with _DB_POOL_LOCK:
        pool = _DB_POOLS.get(tenant_id)
        if pool is None:
            pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix=f"memidx-{tenant_id}")
            _DB_POOLS[tenant_id] = pool
        return pool


_DB_POOL = _get_db_pool("default")


# ── Embedding Provider Protocol ──────────────────────────────────────────────

class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier."""
        pass
    
    @property
    @abstractmethod
    def dims(self) -> int:
        """Native embedding dimension."""
        pass
    
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        pass


# ── Provider Implementations ─────────────────────────────────────────────────

class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash-based fallback (always works, low quality)."""
    
    @property
    def name(self) -> str:
        return "hash"
    
    @property
    def dims(self) -> int:
        return EMBED_DIM
    
    async def embed(self, text: str) -> list[float]:
        return self._embed_hash(text)
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_hash(t) for t in texts]
    
    def _embed_hash(self, text: str) -> list[float]:
        vec = [0.0] * EMBED_DIM
        for batch_idx, batch_start in enumerate(range(0, EMBED_DIM, 32)):
            h = hashlib.sha256(f"{text}|{batch_idx}".encode()).digest()
            for j in range(min(32, EMBED_DIM - batch_start)):
                vec[batch_start + j] = struct.unpack("b", bytes([h[j]]))[0] / 128.0
        mag = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / mag for x in vec]


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers model (all-MiniLM-L6-v2, 384-dim)."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model: typing.Any = None
        self._model_dims = 384
    
    @property
    def name(self) -> str:
        return "local"
    
    @property
    def dims(self) -> int:
        return self._model_dims
    
    async def embed(self, text: str) -> list[float]:
        return await self._embed_local(text)
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
            except ImportError as exc:
                raise ImportError("sentence-transformers not installed") from exc
        
        loop = asyncio.get_running_loop()
        vecs = await loop.run_in_executor(
            None,
            lambda: self._model.encode(texts, normalize_embeddings=True).tolist()
        )
        return [self._pad(v) for v in vecs]
    
    async def _embed_local(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]
    
    def _pad(self, vec: list[float]) -> list[float]:
        if len(vec) < EMBED_DIM:
            return vec + [0.0] * (EMBED_DIM - len(vec))
        return vec[:EMBED_DIM]


class RWIEEmbeddingProvider(EmbeddingProvider):
    """RW_InferenceEngine HTTP embedding provider (BERT, 384-dim)."""
    
    def __init__(
        self,
        base_url: str = "http://100.122.246.112:8300",
        timeout: int = 30,
        batch_size: int = 32,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.batch_size = batch_size
        self._client: httpx.AsyncClient | None = None
    
    @property
    def name(self) -> str:
        return "rw_ie"
    
    @property
    def dims(self) -> int:
        return 384  # BERT hidden_size
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client
    
    async def embed(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            resp = await client.post(
                "/embed",
                json={"texts": batch, "batch_size": self.batch_size},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            all_embeddings.extend(embeddings)
        
        return all_embeddings
    
    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Gemini embedding API provider (gemini-embedding-001, 3072-dim)."""
    
    def __init__(self, api_key: str | None = None):
        self._api_key = api_key
        self._genai = None
    
    @property
    def name(self) -> str:
        return "gemini"
    
    @property
    def dims(self) -> int:
        return 3072
    
    async def _get_genai(self):
        if self._genai is None:
            import google.generativeai as genai
            
            # Resolve API key
            api_key = self._api_key
            if not api_key:
                api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                api_key = getattr(settings, "gemini_api_key", None)
            if not api_key:
                # Try loading from ~/.nexusagent/.env then project root .env
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
            self._genai = genai
        
        return self._genai
    
    async def embed(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        genai = await self._get_genai()
        
        all_embeddings = []
        for text in texts:
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="RETRIEVAL_QUERY",
            )
            all_embeddings.append(result["embedding"])
        
        return all_embeddings


# ── Provider Factory ──────────────────────────────────────────────────────────

def create_embedding_provider() -> EmbeddingProvider:
    """Create embedding provider based on config."""
    provider_name = getattr(settings.embedding, "provider", "gemini").lower()
    
    if provider_name == "rw_ie":
        rw_ie_config = getattr(settings.embedding, "rw_ie", None)
        if rw_ie_config:
            return RWIEEmbeddingProvider(
                base_url=getattr(rw_ie_config, "base_url", "http://100.122.246.112:8300"),
                timeout=getattr(rw_ie_config, "timeout_secs", 30),
                batch_size=getattr(rw_ie_config, "batch_size", 32),
            )
        return RWIEEmbeddingProvider()
    
    elif provider_name == "local":
        local_config = getattr(settings.embedding, "local", None)
        model_name = getattr(local_config, "model", "all-MiniLM-L6-v2")
        return LocalEmbeddingProvider(model_name=model_name)
    
    elif provider_name == "hash":
        return HashEmbeddingProvider()
    
    # Default: Gemini
    return GeminiEmbeddingProvider()


# ── Fallback Chain ────────────────────────────────────────────────────────────

class ChainedEmbeddingProvider(EmbeddingProvider):
    """Chains multiple providers with fallback."""
    
    def __init__(self, providers: list[EmbeddingProvider]):
        self.providers = providers
        # Use first provider's dims as canonical
        self._primary_dims = providers[0].dims if providers else EMBED_DIM
        # Store hash provider for sync fallback
        self._hash_provider = HashEmbeddingProvider()
    
    @property
    def name(self) -> str:
        return "chained:" + ",".join(p.name for p in self.providers)
    
    @property
    def dims(self) -> int:
        return self._primary_dims
    
    async def embed(self, text: str) -> list[float]:
        for provider in self.providers:
            try:
                vec = await provider.embed(text)
                if len(vec) != self._primary_dims:
                    vec = self._adjust_dim(vec)
                return vec
            except Exception as e:
                logger.warning(f"{provider.name} embedding failed: {e}, trying next")
        raise RuntimeError("All embedding providers failed")
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        for provider in self.providers:
            try:
                vecs = await provider.embed_batch(texts)
                return [self._adjust_dim(v) for v in vecs]
            except Exception as e:
                logger.warning(f"{provider.name} batch embedding failed: {e}, trying next")
        raise RuntimeError("All embedding providers failed")
    
    def _adjust_dim(self, vec: list[float]) -> list[float]:
        if len(vec) < self._primary_dims:
            return vec + [0.0] * (self._primary_dims - len(vec))
        return vec[:self._primary_dims]
    
    def _embed_hash(self, text: str) -> list[float]:
        """Sync hash fallback for synchronous search methods."""
        return self._hash_provider._embed_hash(text)
    
    # ── Provider Factory ──────────────────────────────────────────────────────────

def create_embedding_provider() -> EmbeddingProvider:
    """Create embedding provider based on config."""
    provider_name = getattr(settings.embedding, "provider", "gemini").lower()
    
    if provider_name == "rw_ie":
        rw_ie_config = getattr(settings.embedding, "rw_ie", None)
        if rw_ie_config:
            return RWIEEmbeddingProvider(
                base_url=getattr(rw_ie_config, "base_url", "http://100.122.246.112:8300"),
                timeout=getattr(rw_ie_config, "timeout_secs", 30),
                batch_size=getattr(rw_ie_config, "batch_size", 32),
            )
        return RWIEEmbeddingProvider()
    
    elif provider_name == "local":
        local_config = getattr(settings.embedding, "local", None)
        model_name = getattr(local_config, "model", "all-MiniLM-L6-v2")
        return LocalEmbeddingProvider(model_name=model_name)
    
    elif provider_name == "hash":
        return HashEmbeddingProvider()
    
    # Default: Gemini
    return GeminiEmbeddingProvider()


# ── Fallback Chain ────────────────────────────────────────────────────────────

def create_chained_embedding_provider() -> EmbeddingProvider:
    """Create chained provider based on config, with fallback chain."""
    primary = create_embedding_provider()
    
    # Build fallback chain: primary → local → hash
    fallbacks = []
    
    if primary.name != "local":
        fallbacks.append(LocalEmbeddingProvider())
    if primary.name != "hash":
        fallbacks.append(HashEmbeddingProvider())
    
    return ChainedEmbeddingProvider([primary] + fallbacks)


# ── Vector Serialization ──────────────────────────────────────────────────────

def _vec_to_blob(vec: list[float]) -> bytes:
    """Pack a float32 vector into a BLOB for sqlite-vec storage."""
    return struct.pack(f"{len(vec)}f", *vec)


def _blob_to_vec(blob: bytes) -> list[float]:
    """Unpack a BLOB back into a float32 vector."""
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))