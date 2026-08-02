"""Registered concrete provider implementations.

All providers register themselves into the global ProviderRegistry.
New providers just need to implement the abstract interface + call register.

Providers are organized:
- Embeddings: Gemini, RW_IE, Local, Hash, OpenAI-compatible
- LLM: OpenAI-compatible, Gemini, OpenRouter (in llm_implementations.py)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import struct
from pathlib import Path
from typing import Any

import httpx

from nexusagent.infrastructure.errors import UpstreamError, UpstreamErrorCode

from .base import EmbeddingProvider, ProviderMetadata, ProviderResult, get_provider_registry

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Embedding Providers
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiEmbeddingProvider(EmbeddingProvider):
    """Gemini embedding API (gemini-embedding-001, 3072-dim)."""

    @property
    def name(self) -> str:
        """Backward compat: provider identifier."""
        return "gemini"

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="gemini", display_name="Google Gemini",
            description="Gemini embedding API (gemini-embedding-001, 3072-dim)",
            provider_type="embedding", env_vars=("GEMINI_API_KEY",),
            base_url="https://generativelanguage.googleapis.com",
            default_model="gemini-embedding-001",
        )

    @property
    def dims(self) -> int:
        return 3072

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or self._resolve_key()

    def _resolve_key(self) -> str:
        key = os.environ.get("GEMINI_API_KEY")
        if key:
            return key
        key = getattr(__import__("nexusagent.infrastructure.config", fromlist=["settings"]).settings, "gemini_api_key", None)
        if key:
            return key
        for env_path in [Path.home() / ".nexusagent" / ".env"]:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        raise UpstreamError(code=UpstreamErrorCode.INVALID_API_KEY,
                            message="No Gemini API key configured",
                            provider="gemini", model="gemini-embedding-001")

    async def embed(self, text: str) -> ProviderResult[list[float]]:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text, task_type="RETRIEVAL_QUERY",
            )
            return ProviderResult(provider="gemini", model="gemini-embedding-001",
                                  response=result["embedding"])
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                code = UpstreamErrorCode.QUOTA_EXCEEDED
            elif "401" in err_str or "unauthorized" in err_str or "apikey" in err_str:
                code = UpstreamErrorCode.INVALID_API_KEY
            else:
                code = UpstreamErrorCode.UNKNOWN
            return ProviderResult(
                provider="gemini", model="gemini-embedding-001", response=None,
                error=UpstreamError(code=code, message=str(e), provider="gemini",
                                    model="gemini-embedding-001", raw_error=e),
            )

    async def embed_batch(self, texts: list[str]) -> ProviderResult[list[list[float]]]:
        results = await asyncio.gather(*[self.embed(t) for t in texts])
        embeddings = [r.response for r in results if r.response]
        errors = [r.error for r in results if r.error]
        if errors:
            return ProviderResult(provider="gemini", model="gemini-embedding-001",
                                  response=embeddings or None, error=errors[0])
        return ProviderResult(provider="gemini", model="gemini-embedding-001", response=embeddings)


class RWIEEmbeddingProvider(EmbeddingProvider):
    """RW_InferenceEngine HTTP embedding (BERT ONNX, 384-dim)."""

    @property
    def name(self) -> str:
        """Backward compat: provider identifier."""
        return "rw_ie"

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="rw_ie", display_name="RW Inference Engine",
            description="Self-hosted ONNX embedding (BERT, 384-dim)",
            provider_type="embedding", base_url="http://100.122.246.112:8300",
        )

    @property
    def dims(self) -> int:
        return 384

    def __init__(self, base_url: str = "http://100.122.246.112:8300",
                 timeout: int = 30, batch_size: int = 32):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._batch_size = batch_size
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url, timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def embed(self, text: str) -> ProviderResult[list[float]]:
        client = await self._get_client()
        try:
            resp = await client.post("/embed", json={"texts": [text]})
            resp.raise_for_status()
            data = resp.json()
            return ProviderResult(provider="rw_ie", model="bert-embedding",
                                  response=data["embeddings"][0])
        except Exception as e:
            return ProviderResult(
                provider="rw_ie", model="bert-embedding", response=None,
                error=UpstreamError(code=UpstreamErrorCode.UNKNOWN, message=str(e),
                                    provider="rw_ie", model="bert-embedding", raw_error=e),
            )

    async def embed_batch(self, texts: list[str]) -> ProviderResult[list[list[float]]]:
        client = await self._get_client()
        try:
            resp = await client.post("/embed", json={"texts": texts})
            resp.raise_for_status()
            data = resp.json()
            return ProviderResult(provider="rw_ie", model="bert-embedding",
                                  response=data["embeddings"])
        except Exception as e:
            return ProviderResult(
                provider="rw_ie", model="bert-embedding", response=None,
                error=UpstreamError(code=UpstreamErrorCode.UNKNOWN, message=str(e),
                                    provider="rw_ie", model="bert-embedding", raw_error=e),
            )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers (all-MiniLM-L6-v2, 384-dim → padded to 3072)."""

    @property
    def name(self) -> str:
        """Backward compat: provider identifier."""
        return "local"

    EMBED_DIM = 3072

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="local", display_name="Local (sentence-transformers)",
            description="Local sentence-transformers (all-MiniLM-L6-v2, 384-dim)",
            provider_type="embedding",
        )

    @property
    def dims(self) -> int:
        return 384

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model: Any = None

    async def embed(self, text: str) -> ProviderResult[list[float]]:
        try:
            if self._model is None:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
            loop = asyncio.get_running_loop()
            vec = await loop.run_in_executor(
                None, lambda: self._model.encode(text, normalize_embeddings=True)
            )
            vec_list = vec.tolist()
            if len(vec_list) < self.EMBED_DIM:
                vec_list = vec_list + [0.0] * (self.EMBED_DIM - len(vec_list))
            return ProviderResult(provider="local", model=self._model_name,
                                  response=vec_list[:self.EMBED_DIM])
        except Exception as e:
            return ProviderResult(
                provider="local", model=self._model_name, response=None,
                error=UpstreamError(code=UpstreamErrorCode.UNKNOWN, message=str(e),
                                    provider="local", model=self._model_name, raw_error=e),
            )

    async def embed_batch(self, texts: list[str]) -> ProviderResult[list[list[float]]]:
        results = await asyncio.gather(*[self.embed(t) for t in texts])
        embeddings = [r.response for r in results if r.response]
        errors = [r.error for r in results if r.error]
        if errors:
            return ProviderResult(provider="local", model=self._model_name,
                                  response=embeddings or None, error=errors[0])
        return ProviderResult(provider="local", model=self._model_name, response=embeddings)


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash-based fallback (always works, low quality)."""

    @property
    def name(self) -> str:
        """Backward compat: provider identifier."""
        return "hash"

    EMBED_DIM = 3072

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="hash", display_name="Hash Fallback",
            description="Deterministic hash-based embedding (low quality, always works)",
            provider_type="embedding",
        )

    @property
    def dims(self) -> int:
        return self.EMBED_DIM

    async def embed(self, text: str) -> ProviderResult[list[float]]:
        return ProviderResult(provider="hash", model="sha256", response=self._embed_hash(text))

    async def embed_batch(self, texts: list[str]) -> ProviderResult[list[list[float]]]:
        return ProviderResult(provider="hash", model="sha256",
                              response=[self._embed_hash(t) for t in texts])

    def _embed_hash(self, text: str) -> list[float]:
        vec = [0.0] * self.EMBED_DIM
        for batch_idx, batch_start in enumerate(range(0, self.EMBED_DIM, 32)):
            h = hashlib.sha256(f"{text}|{batch_idx}".encode()).digest()
            for j in range(min(32, self.EMBED_DIM - batch_start)):
                vec[batch_start + j] = struct.unpack("b", bytes([h[j]]))[0] / 128.0
        mag = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / mag for x in vec]


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible embedding (works with any OpenAI-compatible /v1/embeddings endpoint)."""

    @property
    def name(self) -> str:
        """Backward compat: provider identifier."""
        return "openai_compatible"

    def __init__(self, base_url: str = "https://api.openai.com/v1",
                 api_key: str | None = None, model: str = "text-embedding-3-small",
                 dims: int = 1536, timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model
        self._dims = dims
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="openai_compatible", display_name="OpenAI-compatible",
            description=f"OpenAI-compatible embedding endpoint ({self._base_url})",
            provider_type="embedding", base_url=self._base_url,
        )

    @property
    def dims(self) -> int:
        return self._dims

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self._base_url, timeout=httpx.Timeout(self._timeout),
                headers=headers,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def embed(self, text: str) -> ProviderResult[list[float]]:
        client = await self._get_client()
        try:
            resp = await client.post("/embeddings", json={"model": self._model, "input": [text]})
            resp.raise_for_status()
            data = resp.json()
            return ProviderResult(provider="openai_compatible", model=self._model,
                                  response=data["data"][0]["embedding"])
        except Exception as e:
            return ProviderResult(
                provider="openai_compatible", model=self._model, response=None,
                error=UpstreamError(code=UpstreamErrorCode.UNKNOWN, message=str(e),
                                    provider="openai_compatible", model=self._model, raw_error=e),
            )

    async def embed_batch(self, texts: list[str]) -> ProviderResult[list[list[float]]]:
        client = await self._get_client()
        try:
            resp = await client.post("/embeddings", json={"model": self._model, "input": texts})
            resp.raise_for_status()
            data = resp.json()
            return ProviderResult(provider="openai_compatible", model=self._model,
                                  response=[d["embedding"] for d in data["data"]])
        except Exception as e:
            return ProviderResult(
                provider="openai_compatible", model=self._model, response=None,
                error=UpstreamError(code=UpstreamErrorCode.UNKNOWN, message=str(e),
                                    provider="openai_compatible", model=self._model, raw_error=e),
            )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ═══════════════════════════════════════════════════════════════════════════════
# Registration
# ═══════════════════════════════════════════════════════════════════════════════

def register_providers():
    """Register all built-in providers with the global registry."""
    registry = get_provider_registry()
    
    # Embedding providers
    registry.register_embedding("gemini", GeminiEmbeddingProvider)
    registry.register_embedding("rw_ie", RWIEEmbeddingProvider)
    registry.register_embedding("local", LocalEmbeddingProvider)
    registry.register_embedding("hash", HashEmbeddingProvider)
    registry.register_embedding("openai_compatible", OpenAICompatibleEmbeddingProvider)
    logger.info("Registered %d embedding providers", 5)