"""Providers package — provider abstraction, fallback chain, and implementations.

Provider-agnostic architecture with:
- Abstract provider interfaces (LLMProvider, EmbeddingProvider, RerankerProvider)
- ProviderRegistry for registration and resolution
- FallbackChain with error routing, circuit breakers, and budget gates
- Standardized UpstreamError taxonomy
"""
from __future__ import annotations

from nexusagent.infrastructure.errors import (
    UpstreamError,
    UpstreamErrorCode,
    is_retryable,
    is_auth_related,
    is_budget_related,
)

from .base import (
    EmbeddingProvider,
    LLMProvider,
    ProviderConfig,
    ProviderMetadata,
    ProviderRegistry,
    ProviderResult,
    RerankerProvider,
    get_provider_registry,
)
from .chain import (
    BudgetGate,
    CircuitBreakerGate,
    ErrorTypeGate,
    FallbackChain,
    FallbackContext,
    FallbackExhaustedError,
    LogicGate,
)
from .implementations import register_providers as register_embedding_providers
from .llm_implementations import register_llm_providers

__all__ = [
    "EmbeddingProvider",
    "LLMProvider",
    "ProviderConfig",
    "ProviderMetadata",
    "ProviderRegistry",
    "ProviderResult",
    "RerankerProvider",
    "get_provider_registry",
    "BudgetGate",
    "CircuitBreakerGate",
    "ErrorTypeGate",
    "FallbackChain",
    "FallbackContext",
    "FallbackExhaustedError",
    "LogicGate",
    "UpstreamError",
    "UpstreamErrorCode",
    "is_retryable",
    "is_auth_related",
    "is_budget_related",
    "register_providers",
    "register_llm_providers",
]

# Auto-register built-in providers on import
register_embedding_providers()
register_llm_providers()