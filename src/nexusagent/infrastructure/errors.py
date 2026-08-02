"""Upstream error taxonomy — standardized error codes across all providers.

Provides a unified error classification system that maps provider-specific
errors to canonical error codes, enabling consistent fallback logic and
error handling across all LLM and embedding providers.
"""

from __future__ import annotations

from enum import Enum


class UpstreamErrorCode(str, Enum):
    """Canonical error codes for upstream provider failures.

    These codes are provider-agnostic and map to specific error conditions
    that should trigger specific fallback behaviors.
    """

    # Rate limiting & quotas
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"          # HTTP 429 with Retry-After
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"                    # Daily/monthly quota exhausted
    DAILY_LIMIT_EXCEEDED = "DAILY_LIMIT_EXCEEDED"        # Daily request limit
    MONTHLY_LIMIT_EXCEEDED = "MONTHLY_LIMIT_EXCEEDED"    # Monthly request limit

    # Authentication & authorization
    AUTH_FAILED = "AUTH_FAILED"                          # Generic auth failure
    INVALID_API_KEY = "INVALID_API_KEY"                  # Invalid/expired API key
    PERMISSION_DENIED = "PERMISSION_DENIED"              # HTTP 403
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"  # Scope/role issues

    # Model availability
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"              # Model not found/not deployed
    MODEL_DEPRECATED = "MODEL_DEPRECATED"                # Model sunset/deprecated
    MODEL_OVERLOADED = "MODEL_OVERLOADED"                # Model at capacity

    # Request validation
    INVALID_REQUEST = "INVALID_REQUEST"                  # HTTP 400 - bad request
    CONTEXT_TOO_LONG = "CONTEXT_TOO_LONG"                # Token limit exceeded
    CONTENT_FILTERED = "CONTENT_FILTERED"                # Safety/content filter
    INVALID_PARAMETERS = "INVALID_PARAMETERS"            # Invalid request parameters

    # Infrastructure
    TIMEOUT = "TIMEOUT"                                   # Request timeout
    NETWORK_ERROR = "NETWORK_ERROR"                      # DNS, connection refused, etc.
    INTERNAL_ERROR = "INTERNAL_ERROR"                    # HTTP 500
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"          # HTTP 503
    GATEWAY_TIMEOUT = "GATEWAY_TIMEOUT"                  # HTTP 504

    # Budget & cost
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"                  # User-defined budget exceeded
    COST_THRESHOLD_EXCEEDED = "COST_THRESHOLD_EXCEEDED"  # Cost threshold breached

    # Unknown/fallback
    UNKNOWN = "UNKNOWN"                                   # Unclassified error


class UpstreamError(Exception):
    """Standardized upstream provider error with canonical error code.

    All provider-specific exceptions should be wrapped in this exception
    to enable consistent fallback logic across providers.
    """

    def __init__(
        self,
        code: UpstreamErrorCode,
        message: str,
        provider: str,
        model: str,
        raw_error: Exception | None = None,
        retry_after: float | None = None,
        metadata: dict | None = None,
    ):
        self.code = code
        self.provider = provider
        self.model = model
        self.raw_error = raw_error
        self.retry_after = retry_after
        self.metadata = metadata or {}
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"UpstreamError(code={self.code.value}, provider={self.provider}, "
            f"model={self.model}, retry_after={self.retry_after})"
        )


# Error classification helpers
RETRYABLE_CODES = frozenset({
    UpstreamErrorCode.RATE_LIMIT_EXCEEDED,
    UpstreamErrorCode.QUOTA_EXCEEDED,
    UpstreamErrorCode.DAILY_LIMIT_EXCEEDED,
    UpstreamErrorCode.MONTHLY_LIMIT_EXCEEDED,
    UpstreamErrorCode.MODEL_OVERLOADED,
    UpstreamErrorCode.TIMEOUT,
    UpstreamErrorCode.NETWORK_ERROR,
    UpstreamErrorCode.INTERNAL_ERROR,
    UpstreamErrorCode.SERVICE_UNAVAILABLE,
    UpstreamErrorCode.GATEWAY_TIMEOUT,
    UpstreamErrorCode.MODEL_UNAVAILABLE,
})

NON_RETRYABLE_CODES = frozenset({
    UpstreamErrorCode.INVALID_API_KEY,
    UpstreamErrorCode.PERMISSION_DENIED,
    UpstreamErrorCode.INSUFFICIENT_PERMISSIONS,
    UpstreamErrorCode.INVALID_REQUEST,
    UpstreamErrorCode.CONTENT_FILTERED,
    UpstreamErrorCode.INVALID_PARAMETERS,
    UpstreamErrorCode.CONTENT_FILTERED,
})

AUTH_RELATED_CODES = frozenset({
    UpstreamErrorCode.AUTH_FAILED,
    UpstreamErrorCode.INVALID_API_KEY,
    UpstreamErrorCode.PERMISSION_DENIED,
    UpstreamErrorCode.INSUFFICIENT_PERMISSIONS,
})

BUDGET_RELATED_CODES = frozenset({
    UpstreamErrorCode.BUDGET_EXCEEDED,
    UpstreamErrorCode.COST_THRESHOLD_EXCEEDED,
})


def is_retryable(code: UpstreamErrorCode) -> bool:
    """Check if an error code should trigger a retry/fallback."""
    return code in RETRYABLE_CODES


def is_auth_related(code: UpstreamErrorCode) -> bool:
    """Check if error is authentication/authorization related."""
    return code in AUTH_RELATED_CODES


def is_budget_related(code: UpstreamErrorCode) -> bool:
    """Check if error is budget/cost related."""
    return code in BUDGET_RELATED_CODES