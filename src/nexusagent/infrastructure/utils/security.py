"""Secrets scanning and sanitization utilities for NexusAgent."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# Standard secret pattern regexes
SECRET_PATTERNS = [
    # Google / Gemini API Keys
    re.compile(r"AIzaSy[A-Za-z0-9_-]{35}"),
    # OpenAI, Anthropic, OpenRouter API Keys
    re.compile(r"sk-[A-Za-z0-9]{32,}"),
    re.compile(r"sk-or-v1-[A-Za-z0-9]{64}"),
    # HuggingFace token
    re.compile(r"hf_[A-Za-z0-9]{34}"),
    # Generic bearer tokens/auth header patterns
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    # Password / secret assignments in string representations (e.g. env files, dictionaries)
    re.compile(r"(?i)(password|passwd|api_key|secret_key|master_secret|token|client_secret)\s*[:=]\s*['\"][^'\"\r\n]{3,}['\"]"),
]


def sanitize_secrets(value: Any) -> Any:
    """Scan and redact potential secrets (API keys, passwords, bearer tokens) from input value.

    Supports strings, lists, dicts, and recursively sanitizes nested structures.
    Uses regex patterns and exact-match checks against known active secrets.
    """
    if isinstance(value, dict):
        return {k: sanitize_secrets(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_secrets(v) for v in value]
    if isinstance(value, tuple):
        return tuple(sanitize_secrets(v) for v in value)
    if isinstance(value, set):
        return {sanitize_secrets(v) for v in value}
    if not isinstance(value, str):
        return value

    sanitized = value

    # 1. Apply regex patterns to replace matching credentials with [REDACTED]
    for pattern in SECRET_PATTERNS:
        # For assignment regexes, we want to redact just the secret part, not the whole key=value assignment
        if "[:=]" in pattern.pattern or "assignment" in str(pattern):
            def redact_match(match):
                matched_str = match.group(0)
                # Find the delimiter and redact whatever is inside the quotes
                for delim in (":", "="):
                    if delim in matched_str:
                        prefix, rest = matched_str.split(delim, 1)
                        # Retain quotes if present
                        quote_char = ""
                        for q in ("'", '"'):
                            if q in rest:
                                quote_char = q
                                break
                        if quote_char:
                            return f"{prefix}{delim}{quote_char}[REDACTED]{quote_char}"
                        else:
                            return f"{prefix}{delim}[REDACTED]"
                return "[REDACTED]"
            sanitized = pattern.sub(redact_match, sanitized)
        else:
            sanitized = pattern.sub("[REDACTED]", sanitized)

    # 2. Gather active secrets dynamically from runtime configuration and auth keystores
    active_secrets: set[str] = set()

    # Collect from environment variables
    for env_key in [
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "EXA_API_KEY",
        "TAVILY_API_KEY",
        "NEXUS_CLIENT__API_KEY",
        "NEXUS_AUTH_MASTER_SECRET",
    ]:
        val = os.environ.get(env_key)
        if val and len(val) >= 8:
            active_secrets.add(val)

    # Collect from settings configuration
    try:
        from nexusagent.infrastructure.config import settings
        if settings.agent.gemini_api_key and len(settings.agent.gemini_api_key) >= 8:
            active_secrets.add(settings.agent.gemini_api_key)
        if settings.client.api_key and len(settings.client.api_key) >= 8:
            active_secrets.add(settings.client.api_key)
    except Exception:
        pass

    # Collect decrypted keys from keystore
    try:
        from nexusagent.infrastructure.auth import get_auth_manager
        auth_mgr = get_auth_manager()
        for svc in ["api", "gemini", "openrouter"]:
            key = auth_mgr.get_key(svc)
            if key and len(key) >= 8:
                active_secrets.add(key)
    except Exception:
        pass

    # Perform exact substring redaction for all gathered active secrets
    for secret in sorted(active_secrets, key=len, reverse=True):
        if secret in sanitized:
            sanitized = sanitized.replace(secret, "[REDACTED]")

    return sanitized
