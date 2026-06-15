"""Utility functions for NexusAgent framework.

This module is a compatibility shim. The actual implementations live in:
- ``nexusagent.infrastructure.utils.retry`` — retry decorators
- ``nexusagent.infrastructure.utils.circuit`` — circuit breaker

All public symbols are re-exported here for backward compatibility.
"""

from nexusagent.infrastructure.utils.circuit import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
)
from nexusagent.infrastructure.utils.retry import retry_on_false, retry_with_backoff

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitState",
    "retry_on_false",
    "retry_with_backoff",
]
