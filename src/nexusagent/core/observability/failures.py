# SPDX-License-Identifier: MIT

# src/nexusagent/core/observability/failures.py
"""Failure classification logic for resilient execution and automated recovery."""

from __future__ import annotations

from enum import Enum


class FailureType(Enum):
    """Categories of execution failures."""

    TRANSIENT = "transient"  # Network timeout, provider unavailable, rate limit, retriable
    DETERMINISTIC = "deterministic"  # Validation failed, missing config, syntax, non-retriable
    SECURITY = "security"  # Policy denial, unauthorized capability request


class FailureClassifier:
    """Classifies application exceptions into actionable failure types."""

    @staticmethod
    def classify(exc: Exception) -> FailureType:
        """Categorize a given exception into FailureType."""
        exc_name = exc.__class__.__name__.lower()
        exc_str = str(exc).lower()

        # 1. Security/Authorization Failures
        security_keywords = [
            "security",
            "unauthorized",
            "permission",
            "policy",
            "accessdenied",
            "denied",
            "forbidden",
            "access denied",
        ]
        if any(kw in exc_name or kw in exc_str for kw in security_keywords):
            return FailureType.SECURITY

        # 2. Transient/Retriable Failures
        transient_keywords = [
            "timeout",
            "timeouterror",
            "connection",
            "http_status_5",
            "rate_limit",
            "quota",
            "resource_exhausted",
            "natserror",
            "socket",
            "busy",
            "unavailable",
        ]
        if any(kw in exc_name or kw in exc_str for kw in transient_keywords):
            return FailureType.TRANSIENT

        # 3. Default to Deterministic/Remediable
        return FailureType.DETERMINISTIC
