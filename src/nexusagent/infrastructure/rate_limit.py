"""Rate limiting for NexusAgent API endpoints.

Implements a token bucket rate limiter shared across all requests.
Each client (identified by API key or IP) has its own bucket.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    """Token bucket for a single client."""
    tokens: float
    last_refill: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# Global rate limit config
_RATE_LIMIT_ENABLED = True
_RATE_LIMIT_TOKENS = 60      # max tokens per bucket
_RATE_LIMIT_REFILL = 60      # refill period in seconds
_RATE_LIMIT_PER_CLIENT = {}   # client_id -> _Bucket
_RATE_LIMIT_CLEANUP = 300     # cleanup interval for stale buckets


def _get_bucket(client_id: str) -> _Bucket:
    """Get or create a token bucket for a client."""
    now = time.monotonic()
    if client_id not in _RATE_LIMIT_PER_CLIENT:
        _RATE_LIMIT_PER_CLIENT[client_id] = _Bucket(
            tokens=float(_RATE_LIMIT_TOKENS),
            last_refill=now,
        )
    return _RATE_LIMIT_PER_CLIENT[client_id]


async def check_rate_limit(client_id: str) -> tuple[bool, dict]:
    """Check if a request is within rate limits.

    Args:
        client_id: API key or IP address identifying the client.

    Returns:
        (allowed: bool, headers: dict with rate limit headers)
    """
    if not _RATE_LIMIT_ENABLED:
        return True, {}

    bucket = _get_bucket(client_id)
    now = time.monotonic()

    async with bucket.lock:
        # Refill tokens
        elapsed = now - bucket.last_refill
        refill_rate = _RATE_LIMIT_TOKENS / _RATE_LIMIT_REFILL
        bucket.tokens = min(_RATE_LIMIT_TOKENS, bucket.tokens + elapsed * refill_rate)
        bucket.last_refill = now

        # Check if we have a token
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            remaining = int(bucket.tokens)
            reset = int(bucket.last_refill + _RATE_LIMIT_REFILL)
            return True, {
                "X-RateLimit-Limit": str(_RATE_LIMIT_TOKENS),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset),
            }
        else:
            retry_after = int((1 - bucket.tokens) / refill_rate) + 1
            return False, {
                "X-RateLimit-Limit": str(_RATE_LIMIT_TOKENS),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(retry_after),
            }


def rate_limit_middleware_enabled() -> bool:
    """Check if rate limiting is enabled."""
    return _RATE_LIMIT_ENABLED


def configure_rate_limit(enabled: bool = True, tokens: int = 60, refill_seconds: int = 60):
    """Configure rate limit parameters."""
    global _RATE_LIMIT_ENABLED, _RATE_LIMIT_TOKENS, _RATE_LIMIT_REFILL
    _RATE_LIMIT_ENABLED = enabled
    _RATE_LIMIT_TOKENS = tokens
    _RATE_LIMIT_REFILL = refill_seconds
