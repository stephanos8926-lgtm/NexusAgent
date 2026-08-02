"""Provider abstraction — factory/abstract factory pattern for LLM providers.

NexusAgent is provider-agnostic. All LLM, embedding, and reranker providers
follow the same abstract interfaces below. Concrete implementations register
themselves via the factory at `registry.py`.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar

from nexusagent.infrastructure.errors import UpstreamError, UpstreamErrorCode


# ── Type Variables ─────────────────────────────────────────────────────────────

T_Config = TypeVar("T_Config", contravariant=True)
T_Request = TypeVar("T_Request", contravariant=True)
T_Response = TypeVar("T_Response", covariant=True)


# ── Provider Metadata ──────────────────────────────────────────────────────────

@dataclass
class ProviderMetadata:
    """Metadata about a provider implementation."""
    name: str                             # Canonical identifier (e.g. "gemini", "openrouter", "rw_ie")
    display_name: str                     # Human-readable name (e.g. "Google Gemini")
    description: str                      # Short description
    provider_type: str                    # "llm" | "embedding" | "reranker"
    env_vars: tuple[str, ...] = ()        # Required env vars in priority order
    base_url: str | None = None           # Default endpoint
    models: tuple[str, ...] = ()          # Known models for this provider
    default_model: str | None = None      # Default model if not specified
    auth_type: str = "api_key"            # api_key | oauth | none
    version: str = "1.0.0"                # Provider implementation version


# ── Result Types ───────────────────────────────────────────────────────────────

@dataclass
class ProviderResult(Generic[T_Response]):
    """Result from a provider execution attempt."""
    provider: str
    model: str
    response: T_Response | None
    error: UpstreamError | None = None
    cost: float = 0.0
    tokens: int = 0
    latency_ms: float = 0.0
    cached: bool = False

    @property
    def success(self) -> bool:
        return self.error is None and self.response is not None


# ── Abstract Provider Interfaces ──────────────────────────────────────────────

class LLMProvider(ABC):
    """Abstract interface for LLM (chat completion) providers."""

    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ProviderResult[dict[str, Any]]:
        ...


class EmbeddingProvider(ABC):
    """Abstract interface for embedding providers."""

    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        ...

    @property
    @abstractmethod
    def dims(self) -> int:
        """Native embedding dimension."""
        ...

    @abstractmethod
    async def embed(self, text: str) -> ProviderResult[list[float]]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> ProviderResult[list[list[float]]]:
        ...


class RerankerProvider(ABC):
    """Abstract interface for reranker providers."""

    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        ...

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> ProviderResult[list[tuple[int, float]]]:
        ...


# ── Provider Configuration ────────────────────────────────────────────────────

@dataclass
class ProviderConfig:
    """Configuration for a single provider in a fallback chain."""
    provider_type: str
    name: str
    model: str | None = None
    config: dict = field(default_factory=dict)
    enabled: bool = True
    priority: int = 100

    # Budget guard per-provider
    max_cost_per_request: float | None = None
    max_calls_per_minute: int | None = None


# ── Provider Factory ───────────────────────────────────────────────────────────

class ProviderFactory(ABC, Generic[T_Response]):
    """Abstract factory for creating providers from config."""

    @abstractmethod
    def create(self, config: ProviderConfig) -> object:
        ...


# ── Simple Provider Registry ──────────────────────────────────────────────────

class ProviderRegistry:
    """Simple registry of provider factories, keyed by provider type."""

    def __init__(self):
        self._llm: dict[str, type[LLMProvider]] = {}
        self._embedding: dict[str, type[EmbeddingProvider]] = {}
        self._reranker: dict[str, type[RerankerProvider]] = {}

    def register_llm(self, name: str, cls: type[LLMProvider]):
        self._llm[name] = cls

    def register_embedding(self, name: str, cls: type[EmbeddingProvider]):
        self._embedding[name] = cls

    def register_reranker(self, name: str, cls: type[RerankerProvider]):
        self._reranker[name] = cls

    def get_llm(self, name: str) -> type[LLMProvider] | None:
        return self._llm.get(name)

    def get_embedding(self, name: str) -> type[EmbeddingProvider] | None:
        return self._embedding.get(name)

    def get_reranker(self, name: str) -> type[RerankerProvider] | None:
        return self._reranker.get(name)

    def list_llm(self) -> list[str]:
        return list(self._llm.keys())

    def list_embedding(self) -> list[str]:
        return list(self._embedding.keys())

    def list_reranker(self) -> list[str]:
        return list(self._reranker.keys())


# Singleton registry
_registry = ProviderRegistry()


def get_provider_registry() -> ProviderRegistry:
    return _registry