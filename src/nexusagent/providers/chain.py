# SPDX-License-Identifier: MIT

"""Fallback chain orchestrator — tries providers in order until one succeeds.

Supports:
- Ordered provider chain with priority-based ordering
- Error code-based routing (retry next, retry same, fail)
- Per-provider budget guards
- Circuit breaker per-provider
- Logic gates for user-defined routing logic
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from nexusagent.infrastructure.errors import (
    UpstreamError,
    UpstreamErrorCode,
    is_retryable,
)

from .base import (
    ProviderConfig,
    ProviderResult,
    get_provider_registry,
)

logger = logging.getLogger(__name__)

T_Response = TypeVar("T_Response")


# ── Logic Gate Protocol ────────────────────────────────────────────────────────


class LogicGate(Protocol):
    """A gate that can block or allow a provider from being tried.

    Return True to ALLOW the provider, False to SKIP it.
    """

    def evaluate(self, context: FallbackContext) -> bool: ...


# ── Fallback Context ───────────────────────────────────────────────────────────


@dataclass
class FallbackContext:
    """Mutable context passed through fallback chain execution."""

    attempt: int = 0
    last_error: UpstreamError | None = None
    cumulative_cost: float = 0.0
    start_time: float = field(default_factory=time.time)
    provider_history: list[ProviderResult] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time


# ── Built-in Logic Gates ───────────────────────────────────────────────────────


class BudgetGate:
    """Reject a provider if cumulative cost exceeds per-request limit."""

    def __init__(self, max_cost_per_request: float):
        self._max = max_cost_per_request

    def evaluate(self, context: FallbackContext) -> bool:
        if context.cumulative_cost >= self._max:
            logger.warning(
                "BudgetGate: cumulative cost %.4f exceeds max %.4f",
                context.cumulative_cost,
                self._max,
            )
            return False
        return True


class ErrorTypeGate:
    """Only allow provider when last error is of an allowed type.

    This implements the pattern: "if Gemini returns QUOTA_EXCEEDED,
    skip it and try OpenRouter instead."
    """

    def __init__(
        self,
        allowed_codes: list[UpstreamErrorCode] | None = None,
        blocked_codes: list[UpstreamErrorCode] | None = None,
    ):
        self._allowed = set(allowed_codes) if allowed_codes else None
        self._blocked = set(blocked_codes) if blocked_codes else None

    def evaluate(self, context: FallbackContext) -> bool:
        if context.last_error is None:
            return True
        if self._blocked and context.last_error.code in self._blocked:
            return False
        return not (self._allowed and context.last_error.code not in self._allowed)


class CircuitBreakerGate:
    """Open circuit after N consecutive failures within cooldown window."""

    def __init__(self, name: str, failure_threshold: int = 3, cooldown_secs: float = 60.0):
        self.name = name
        self._threshold = failure_threshold
        self._cooldown = cooldown_secs
        self._failures: list[float] = []

    def evaluate(self, context: FallbackContext) -> bool:
        now = time.time()
        # Prune expired failures
        self._failures = [t for t in self._failures if now - t < self._cooldown]
        if len(self._failures) >= self._threshold:
            remaining = self._cooldown - (now - self._failures[0])
            logger.warning("CircuitBreaker[%s]: open for %.1f more seconds", self.name, remaining)
            return False
        return True

    def record_failure(self):
        self._failures.append(time.time())

    def record_success(self):
        self._failures.clear()


# ── Fallback Chain ─────────────────────────────────────────────────────────────


class FallbackExhaustedError(Exception):
    """Raised when all providers in the chain have been exhausted."""


@dataclass
class ChainStats:
    """Statistics about a fallback chain execution."""

    total_attempts: int = 0
    successful_provider: str | None = None
    last_error: UpstreamError | None = None
    total_cost: float = 0.0
    total_latency: float = 0.0
    history: list[ProviderResult] = field(default_factory=list)


class FallbackChain[T_Response]:
    """Orchestrates an ordered list of providers with fallback logic.

    Usage:
        chain = FallbackChain[dict](providers=[
            ProviderConfig(provider_type="gemini", name="gemini-primary", priority=10),
            ProviderConfig(provider_type="openrouter", name="openrouter-fallback", priority=20),
        ])
        result = await chain.execute(lambda p: p.chat(...))
    """

    def __init__(
        self,
        providers: list[ProviderConfig],
        gates: list[LogicGate] | None = None,
        max_attempts: int = 3,
    ):
        self._providers = sorted(providers, key=lambda p: p.priority)
        self._gates = gates or []
        self._max_attempts = max_attempts
        self._circuit_breakers: dict[str, CircuitBreakerGate] = {}
        self._registry = get_provider_registry()

    def add_gate(self, gate: LogicGate) -> None:
        self._gates.append(gate)

    async def execute(
        self,
        call_fn,
        provider_type: str = "llm",
        context: FallbackContext | None = None,
    ) -> ProviderResult[T_Response]:
        """Execute the chain, trying providers in order.

        Args:
            call_fn: Async callable that takes (provider_instance, config) and
                     returns ProviderResult. The chain calls this for each provider.
            provider_type: Which registry to resolve from ("llm", "embedding", "reranker").
            context: Optional existing context to continue from.

        Returns:
            ProviderResult of the first successful provider.

        Raises:
            FallbackExhaustedError: If all providers fail.
        """
        ctx = context or FallbackContext()

        for _i, config in enumerate(self._providers):
            if not config.enabled:
                continue

            # Check global gates
            if not all(g.evaluate(ctx) for g in self._gates):
                continue

            # Check per-provider budget gate
            if config.max_cost_per_request is not None:
                if ctx.cumulative_cost >= config.max_cost_per_request:
                    continue

            # Check circuit breaker
            cb = self._circuit_breakers.get(config.name)
            if cb and not cb.evaluate(ctx):
                continue

            # Resolve the provider
            provider = self._resolve_provider(config, provider_type)
            if provider is None:
                logger.warning("Provider type '%s' not registered, skipping", config.provider_type)
                continue

            logger.info(
                "Chain: trying %s (attempt %d/%d)", config.name, ctx.attempt + 1, self._max_attempts
            )
            ctx.attempt += 1

            try:
                result = await call_fn(provider, config)

                if result.success:
                    if cb:
                        cb.record_success()
                    ctx.provider_history.append(result)
                    ctx.cumulative_cost += result.cost
                    return result

                # Non-success result with error
                ctx.last_error = result.error
                ctx.provider_history.append(result)
                ctx.cumulative_cost += result.cost

                if cb:
                    cb.record_failure()

                # Route based on error code
                if result.error and not is_retryable(result.error.code):
                    # Non-retryable → fail immediately
                    raise result.error

            except UpstreamError as e:
                ctx.last_error = e
                if cb:
                    cb.record_failure()

                if not is_retryable(e.code):
                    raise

                # Retry next provider
                logger.warning("Chain: %s failed with %s, trying next", config.name, e.code.value)

            except Exception as e:
                logger.error("Chain: %s failed with unexpected error: %s", config.name, e)
                ctx.last_error = UpstreamError(
                    code=UpstreamErrorCode.UNKNOWN,
                    message=str(e),
                    provider=config.provider_type,
                    model=config.model or "unknown",
                    raw_error=e,
                )
                if cb:
                    cb.record_failure()

            if ctx.attempt >= self._max_attempts:
                break

        # All providers exhausted
        last_err = ctx.last_error
        if last_err:
            raise FallbackExhaustedError(
                f"All providers exhausted after {ctx.attempt} attempts. Last error: {last_err}"
            )
        raise FallbackExhaustedError(f"All providers exhausted after {ctx.attempt} attempts")

    def _resolve_provider(self, config: ProviderConfig, provider_type: str):
        """Resolve a provider from the registry."""
        registry = get_provider_registry()
        if provider_type == "llm":
            cls = registry.get_llm(config.provider_type)
        elif provider_type == "embedding":
            cls = registry.get_embedding(config.provider_type)
        elif provider_type == "reranker":
            cls = registry.get_reranker(config.provider_type)
        else:
            return None

        if cls is None:
            return None

        return cls(**config.config)

    def circuit_breaker(self, name: str) -> CircuitBreakerGate:
        """Get or create a circuit breaker for a provider."""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreakerGate(name=name)
        return self._circuit_breakers[name]
