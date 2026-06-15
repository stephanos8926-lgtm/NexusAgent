"""Retry decorators with exponential backoff.

Provides two retry strategies:
- ``retry_with_backoff``: retries on specified exceptions
- ``retry_on_false``: retries when the decorated function returns a falsy value

Both support sync and async functions, exponential backoff with jitter,
and optional retry callbacks.
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
    """Retry decorator with exponential backoff.

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
    """Retry decorator that retries when function returns False or None.

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
                for attempt in range(max_attempts):
                    result = func(*args, **kwargs)
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
