# src/nexusagent/utils.py
"""
Utility functions for NexusAgent framework.
"""

import asyncio
import functools
import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[BaseException, int], None] | None = None,
):
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including initial try)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delay
        exceptions: Tuple of exceptions to catch and retry on
        on_retry: Callback function called on each retry (exception, attempt_number)

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                last_exception: BaseException | None = None
                for attempt in range(max_attempts):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt == max_attempts - 1:  # Last attempt
                            logger.error(
                                f"Function {func.__name__} failed after {max_attempts} attempts. "
                                f"Last error: {e!s}"
                            )
                            raise

                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (exponential_base**attempt), max_delay)

                        # Add jitter if enabled
                        if jitter:
                            delay *= 0.5 + random.random() * 0.5  # 0.5 to 1.0 multiplier

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e!s}. "
                            f"Retrying in {delay:.2f}s..."
                        )

                        if on_retry:
                            on_retry(e, attempt + 1)

                        await asyncio.sleep(delay)

                # This should never be reached, but just in case
                if last_exception is not None:
                    raise last_exception
                else:
                    raise RuntimeError("Unexpected state in retry logic")

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                last_exception: BaseException | None = None
                for attempt in range(max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt == max_attempts - 1:  # Last attempt
                            logger.error(
                                f"Function {func.__name__} failed after {max_attempts} attempts. "
                                f"Last error: {e!s}"
                            )
                            raise

                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (exponential_base**attempt), max_delay)

                        # Add jitter if enabled
                        if jitter:
                            delay *= 0.5 + random.random() * 0.5  # 0.5 to 1.0 multiplier

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e!s}. "
                            f"Retrying in {delay:.2f}s..."
                        )

                        if on_retry:
                            on_retry(e, attempt + 1)

                        time.sleep(delay)

                # This should never be reached, but just in case
                if last_exception is not None:
                    raise last_exception
                else:
                    raise RuntimeError("Unexpected state in retry logic")

            return sync_wrapper

    return decorator


def retry_on_false(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    on_retry: Callable[[Any, int], None] | None = None,
):
    """
    Retry decorator that retries when function returns False or None.

    Args:
        max_attempts: Maximum number of attempts (including initial try)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delay
        on_retry: Callback function called on each retry (result, attempt_number)

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                last_result: Any = None
                for attempt in range(max_attempts):
                    result = await func(*args, **kwargs)
                    last_result = result
                    if result:  # Truthy value means success
                        return result

                    if attempt == max_attempts - 1:  # Last attempt
                        logger.error(
                            f"Function {func.__name__} returned falsy value after {max_attempts} attempts. "
                            f"Last result: {result}"
                        )
                        return result

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    # Add jitter if enabled
                    if jitter:
                        delay *= 0.5 + random.random() * 0.5  # 0.5 to 1.0 multiplier

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} returned falsy for {func.__name__}: {result}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    if on_retry:
                        on_retry(result, attempt + 1)

                    await asyncio.sleep(delay)

                return last_result

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                last_result: Any = None
                for attempt in range(max_attempts):
                    result = func(*args, **kwargs)
                    last_result = result
                    if result:  # Truthy value means success
                        return result

                    if attempt == max_attempts - 1:  # Last attempt
                        logger.error(
                            f"Function {func.__name__} returned falsy value after {max_attempts} attempts. "
                            f"Last result: {result}"
                        )
                        return result

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    # Add jitter if enabled
                    if jitter:
                        delay *= 0.5 + random.random() * 0.5  # 0.5 to 1.0 multiplier

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} returned falsy for {func.__name__}: {result}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    if on_retry:
                        on_retry(result, attempt + 1)

                    time.sleep(delay)

        return decorator


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class CircuitState:
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreakerError(Exception):
    """Raised when the circuit breaker is open and calls are rejected."""

    def __init__(self, name: str, state: str):
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

    Usage:
        breaker = CircuitBreaker("nats", failure_threshold=3, recovery_timeout=30)

        # As a decorator:
        @breaker
        async def call_nats():
            ...

        # Or as a context manager:
        async with breaker:
            await nats_call()
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ):
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
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def _reset(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")

    def _trip(self) -> None:
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
        async with self._lock:
            if not await self._check_recovery():
                raise CircuitBreakerError(self.name, self._state)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
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
