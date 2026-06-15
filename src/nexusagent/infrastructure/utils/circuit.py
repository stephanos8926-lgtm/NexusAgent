"""Circuit breaker pattern for protecting against cascading failures.

Provides a stateful circuit breaker with three states:
- CLOSED: Normal operation, calls pass through
- OPEN: Failing, calls are rejected immediately
- HALF_OPEN: Testing if the underlying service has recovered

Usage::

    breaker = CircuitBreaker("nats", failure_threshold=3, recovery_timeout=30)

    # As a decorator:
    @breaker
    async def call_nats():
        ...

    # Or as a context manager:
    async with breaker:
        await nats_call()
"""

import asyncio
import functools
import logging
import time

logger = logging.getLogger(__name__)


class CircuitState:
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreakerError(Exception):
    """Raised when the circuit breaker is open and calls are rejected."""

    def __init__(self, name: str, state: str):
        """Initialize the error with circuit breaker details.

        Args:
            name: Name of the circuit breaker that rejected the call.
            state: Current state of the circuit breaker (e.g. ``"open"``).
        """
        self.name = name
        self.state = state
        super().__init__(
            f"Circuit breaker '{name}' is {state}. Call rejected to prevent cascading failures."
        )


class CircuitBreaker:
    """
    Stateful circuit breaker for protecting against cascading failures.

    States:
      - CLOSED: Normal operation. Calls pass through. Failures are counted.
      - OPEN: Threshold exceeded. Calls are rejected immediately.
                After recovery_timeout, transitions to HALF_OPEN.
      - HALF_OPEN: Allows a single test call. Success -> CLOSED, Failure -> OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ):
        """Initialize the circuit breaker.

        Args:
            name: Human-readable name for this circuit breaker (used in logs
                and error messages).
            failure_threshold: Number of consecutive failures before the
                circuit trips open.
            recovery_timeout: Seconds to wait in OPEN state before
                transitioning to HALF_OPEN for a test call.
            expected_exceptions: Tuple of exception types that count as
                failures. Other exceptions pass through uncounted.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        """Return the current circuit breaker state.

        Returns:
            One of ``CircuitState.CLOSED``, ``CircuitState.OPEN``, or
            ``CircuitState.HALF_OPEN``.
        """
        return self._state

    @property
    def failure_count(self) -> int:
        """Return the current consecutive failure count.

        Returns:
            Number of consecutive failures since the last reset.
        """
        return self._failure_count

    def _reset(self) -> None:
        """Reset the circuit breaker to CLOSED with zero failures."""
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")

    def _trip(self) -> None:
        """Record a failure and trip the circuit open if threshold is reached."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker '{self.name}' tripped to OPEN "
                f"after {self._failure_count} failures. "
                f"Recovery in {self.recovery_timeout}s"
            )

    async def _check_recovery(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if self._state != CircuitState.OPEN:
            return True
        if time.time() - self._last_failure_time >= self.recovery_timeout:
            self._state = CircuitState.HALF_OPEN
            logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")
            return True
        return False

    async def __aenter__(self) -> "CircuitBreaker":
        """Enter the circuit breaker context.

        Returns:
            The circuit breaker instance.

        Raises:
            CircuitBreakerError: If the circuit is open and recovery timeout
                has not yet elapsed.
        """
        async with self._lock:
            if not await self._check_recovery():
                raise CircuitBreakerError(self.name, self._state)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the circuit breaker context, recording success or failure.

        Args:
            exc_type: Exception type if an exception was raised, else None.
            exc_val: Exception value if an exception was raised, else None.
            exc_tb: Exception traceback if an exception was raised, else None.

        Returns:
            False — exceptions are never suppressed.
        """
        async with self._lock:
            if exc_type is None:
                # Success
                if self._state == CircuitState.HALF_OPEN:
                    self._reset()
                elif self._state == CircuitState.CLOSED:
                    self._failure_count = max(0, self._failure_count - 1)
                return False
            else:
                # Failure
                if issubclass(exc_type, self.expected_exceptions):
                    self._trip()
                return False

    def __call__(self, func):
        """Use as a decorator on async functions."""

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with self:
                return await func(*args, **kwargs)

        return wrapper
