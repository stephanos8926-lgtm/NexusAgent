# SPDX-License-Identifier: MIT

"""Embedding provider integration for memory index.

Uses the new provider system from nexusagent.providers.
Memory-specific constants and serialization remain here.
"""

from __future__ import annotations

import logging
import struct
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

from nexusagent.infrastructure.config import settings
from nexusagent.providers import get_provider_registry

# Re-export for backward compatibility
from nexusagent.providers.implementations import (
    HashEmbeddingProvider,
)

logger = logging.getLogger(__name__)

# ── Memory-specific constants ─────────────────────────────────────────────────

# Target dimension for storage (Gemini default)
EMBED_DIM = 3072
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
CANDIDATE_MULTIPLIER = 4

# Thread pool for blocking DB operations
_DB_POOLS: dict[str, ThreadPoolExecutor] = {}
_DB_POOL_LOCK = threading.Lock()


def _get_db_pool(tenant_id: str = "default") -> ThreadPoolExecutor:
    with _DB_POOL_LOCK:
        pool = _DB_POOLS.get(tenant_id)
        if pool is None:
            pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix=f"memidx-{tenant_id}")
            _DB_POOLS[tenant_id] = pool
        return pool


_DB_POOL = _get_db_pool("default")


# ── Embedding Provider Protocol ────────────────────────────────────────────────


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers (backward compat)."""

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


# ── Provider Factory ───────────────────────────────────────────────────────────


def create_embedding_provider():
    """Create embedding provider based on config, using provider registry.

    Returns an embedding provider instance or None if unavailable.
    Falls back to hash provider if configured provider fails.
    """
    from nexusagent.providers.implementations import HashEmbeddingProvider

    # Get provider name from config
    provider_name = getattr(settings.embedding, "provider", "gemini").lower()

    registry = get_provider_registry()
    provider_cls = registry.get_embedding(provider_name)

    if provider_cls is None:
        logger.warning("Embedding provider '%s' not found, trying hash fallback", provider_name)
        return HashEmbeddingProvider()

    # Create provider instance
    try:
        if provider_name == "gemini":
            return provider_cls()
        elif provider_name == "rw_ie":
            rw_ie_config = getattr(settings.embedding, "rw_ie", None)
            base_url = (
                getattr(rw_ie_config, "base_url", "http://100.122.246.112:8300")
                if rw_ie_config
                else "http://100.122.246.112:8300"
            )
            timeout = getattr(rw_ie_config, "timeout_secs", 30) if rw_ie_config else 30
            batch_size = getattr(rw_ie_config, "batch_size", 32) if rw_ie_config else 32
            return provider_cls(base_url=base_url, timeout=timeout, batch_size=batch_size)
        elif provider_name == "local":
            local_config = getattr(settings.embedding, "local", None)
            model_name = (
                getattr(local_config, "model", "all-MiniLM-L6-v2")
                if local_config
                else "all-MiniLM-L6-v2"
            )
            return provider_cls(model_name=model_name)
        elif provider_name == "hash":
            return provider_cls()
        elif provider_name == "openai_compatible":
            openai_config = getattr(settings.embedding, "openai_compatible", None)
            base_url = (
                getattr(openai_config, "base_url", "https://api.openai.com/v1")
                if openai_config
                else "https://api.openai.com/v1"
            )
            api_key = getattr(openai_config, "api_key", None) if openai_config else None
            model = (
                getattr(openai_config, "model", "text-embedding-3-small")
                if openai_config
                else "text-embedding-3-small"
            )
            dims = getattr(openai_config, "dims", 1536) if openai_config else 1536
            return provider_cls(base_url=base_url, api_key=api_key, model=model, dims=dims)
        else:
            return provider_cls()
    except Exception as e:
        logger.warning("Failed to create '%s' provider: %s, trying hash fallback", provider_name, e)
        return HashEmbeddingProvider()


# ── Fallback Chain ────────────────────────────────────────────────────────────


class ChainedEmbeddingProvider(EmbeddingProvider):
    """Chains multiple providers with fallback."""

    def __init__(self, providers: list):
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
                result = await provider.embed(text)
                if result.error:
                    raise result.error
                vec = result.response
                if len(vec) != self._primary_dims:
                    vec = self._adjust_dim(vec)
                return vec
            except Exception as e:
                logger.warning(f"{provider.name} embedding failed: {e}, trying next")
        raise RuntimeError("All embedding providers failed")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        for provider in self.providers:
            try:
                result = await provider.embed_batch(texts)
                if result.error:
                    raise result.error
                vecs = result.response
                return [self._adjust_dim(v) for v in vecs]
            except Exception as e:
                logger.warning(f"{provider.name} batch embedding failed: {e}, trying next")
        raise RuntimeError("All embedding providers failed")

    def _adjust_dim(self, vec: list[float]) -> list[float]:
        if len(vec) < self._primary_dims:
            return vec + [0.0] * (self._primary_dims - len(vec))
        return vec[: self._primary_dims]

    def _embed_hash(self, text: str) -> list[float]:
        """Sync hash fallback for synchronous search methods."""
        return self._hash_provider._embed_hash(text)


def create_chained_embedding_provider() -> EmbeddingProvider:
    """Create chained provider based on config, with fallback chain."""
    primary = create_embedding_provider()

    # Build fallback chain: primary → local → hash
    fallbacks = []

    if primary.name != "local":
        from nexusagent.providers.implementations import LocalEmbeddingProvider

        fallbacks.append(LocalEmbeddingProvider())
    if primary.name != "hash":
        fallbacks.append(HashEmbeddingProvider())

    return ChainedEmbeddingProvider([primary, *fallbacks])


# ── Vector Serialization ──────────────────────────────────────────────────────


def _vec_to_blob(vec: list[float]) -> bytes:
    """Pack a float32 vector into a BLOB for sqlite-vec storage."""
    return struct.pack(f"{len(vec)}f", *vec)


def _blob_to_vec(blob: bytes) -> list[float]:
    """Unpack a BLOB back into a float32 vector."""
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


# ── Public API ─────────────────────────────────────────────────────────────────

__all__ = [
    "CANDIDATE_MULTIPLIER",
    "CHUNK_OVERLAP",
    "CHUNK_SIZE",
    "EMBED_DIM",
    "KEYWORD_WEIGHT",
    "VECTOR_WEIGHT",
    "_DB_POOL",
    "ChainedEmbeddingProvider",
    "EmbeddingProvider",
    "_blob_to_vec",
    "_vec_to_blob",
    "create_chained_embedding_provider",
    "create_embedding_provider",
]
