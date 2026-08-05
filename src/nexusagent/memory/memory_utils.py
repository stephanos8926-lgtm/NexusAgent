# SPDX-License-Identifier: MIT

"""Shared utilities for file-based memory operations.

Extracted from memory_files.py to reduce module size and deduplicate
frontmatter parsing/serialization logic.
"""

import logging
from datetime import UTC, datetime

import yaml

logger = logging.getLogger(__name__)

__all__ = [
    "is_expired",
    "parse_expiry",
    "parse_frontmatter",
    "serialize_frontmatter",
    "strip_frontmatter",
]


def parse_expiry(frontmatter: dict) -> datetime | None:
    """Parse expires_at from frontmatter, returning None if absent or unparseable."""
    expires_at = frontmatter.get("expires_at")
    if not expires_at:
        return None
    try:
        return datetime.fromisoformat(expires_at)
    except (ValueError, TypeError):
        return None


def is_expired(frontmatter: dict) -> bool:
    """Return True if the entry has an expires_at that is in the past."""
    expiry = parse_expiry(frontmatter)
    if expiry is None:
        return False
    return datetime.now(UTC) > expiry


def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a memory file."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def serialize_frontmatter(frontmatter: dict, body: str = "") -> str:
    """Serialize frontmatter and optional body into markdown format."""
    body = body or ""
    return f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{body}"


def strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from a memory file, returning just the body."""
    if not content.startswith("---"):
        return content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return content
    return parts[2].strip()
