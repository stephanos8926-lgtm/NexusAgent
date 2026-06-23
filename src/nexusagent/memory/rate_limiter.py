"""Token-bucket rate limiter for memory tools.

Prevents buggy loops from flooding the DB with low-value observations.
Write operations (write, update, delete, prune, consolidate) are limited
separately from read operations (search, get, list).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

# Default clock — can be overridden in tests
_clock: Callable[[], float] = time.monotonic


@dataclass
class _Bucket:
    """Simple token bucket."""

    max_tokens: int
    refill_per_second: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.max_tokens)
        self.last_refill = _clock()

    def consume(self) -> bool:
        """Try to consume one token. Returns True if allowed."""
        now = _clock()
        elapsed = now - self.last_refill
        self.last_refill = now
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_per_second)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class MemoryRateLimiter:
    """Token-bucket rate limiter for memory tool calls.

    Two independent buckets:
    - writes: memory_write, memory_update, memory_delete, memory_prune, memory_consolidate
    - searches: memory_search, memory_get, memory_list

    Args:
        max_writes_per_minute: Maximum write operations per minute (default: 30).
        max_searches_per_minute: Maximum search/read operations per minute (default: 60).
    """

    def __init__(
        self,
        max_writes_per_minute: int = 30,
        max_searches_per_minute: int = 60,
    ) -> None:
        self._write_bucket = _Bucket(
            max_tokens=max_writes_per_minute,
            refill_per_second=max_writes_per_minute / 60.0,
        )
        self._search_bucket = _Bucket(
            max_tokens=max_searches_per_minute,
            refill_per_second=max_searches_per_minute / 60.0,
        )

    # ── Public API ──────────────────────────────────────────────────────

    def check_write(self) -> str | None:
        """Check if a write operation is allowed.

        Returns:
            None if allowed, or a warning message string if rate-limited.
        """
        if not self._write_bucket.consume():
            return (
                "⚠️  Rate limit exceeded for memory write operations "
                f"(max {self._write_bucket.max_tokens:.0f}/min). "
                "Please wait before writing again."
            )
        return None

    def check_search(self) -> str | None:
        """Check if a search/read operation is allowed.

        Returns:
            None if allowed, or a warning message string if rate-limited.
        """
        if not self._search_bucket.consume():
            return (
                "⚠️  Rate limit exceeded for memory search operations "
                f"(max {self._search_bucket.max_tokens:.0f}/min). "
                "Please wait before searching again."
            )
        return None

    def reset(self) -> None:
        """Reset both buckets (useful for testing)."""
        self._write_bucket = _Bucket(
            max_tokens=self._write_bucket.max_tokens,
            refill_per_second=self._write_bucket.max_tokens / 60.0,
        )
        self._search_bucket = _Bucket(
            max_tokens=self._search_bucket.max_tokens,
            refill_per_second=self._search_bucket.max_tokens / 60.0,
        )
