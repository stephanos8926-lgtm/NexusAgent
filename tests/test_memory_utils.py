# SPDX-License-Identifier: MIT

"""Tests for memory_utils module."""

import pytest

from nexusagent.memory.memory_utils import (
    is_expired,
    parse_expiry,
    parse_frontmatter,
    serialize_frontmatter,
    strip_frontmatter,
)


def test_memory_utils_exports_all_public_functions():
    """memory_utils should define __all__ with all public functions."""
    import nexusagent.memory.memory_utils as mu

    assert hasattr(mu, "__all__")
    expected = {
        "parse_expiry",
        "is_expired",
        "parse_frontmatter",
        "serialize_frontmatter",
        "strip_frontmatter",
    }
    assert set(mu.__all__) == expected


def test_serialize_frontmatter_handles_none_body():
    """serialize_frontmatter should treat None body as empty string."""
    fm = {"name": "test", "type": "world"}
    result = serialize_frontmatter(fm, None)
    assert "None" not in result
    assert result.endswith("\n\n")


def test_serialize_frontmatter_handles_empty_string():
    """serialize_frontmatter should handle empty string body correctly."""
    fm = {"name": "test", "type": "world"}
    result = serialize_frontmatter(fm, "")
    assert result.endswith("\n\n")


def test_parse_expiry_valid():
    """parse_expiry should parse valid ISO format expires_at."""
    fm = {"expires_at": "2025-12-31T23:59:59+00:00"}
    result = parse_expiry(fm)
    assert result is not None


def test_parse_expiry_invalid():
    """parse_expiry should return None for invalid expires_at."""
    fm = {"expires_at": "not-a-date"}
    result = parse_expiry(fm)
    assert result is None


def test_parse_expiry_missing():
    """parse_expiry should return None when expires_at is missing."""
    fm = {}
    result = parse_expiry(fm)
    assert result is None


def test_is_expired_past():
    """is_expired should return True for past expires_at."""
    from datetime import UTC, datetime, timedelta

    past = datetime.now(UTC) - timedelta(hours=1)
    fm = {"expires_at": past.isoformat()}
    assert is_expired(fm) is True


def test_is_expired_future():
    """is_expired should return False for future expires_at."""
    from datetime import UTC, datetime, timedelta

    future = datetime.now(UTC) + timedelta(hours=1)
    fm = {"expires_at": future.isoformat()}
    assert is_expired(fm) is False


def test_is_expired_missing():
    """is_expired should return False when expires_at is missing."""
    fm = {}
    assert is_expired(fm) is False


def test_parse_frontmatter_valid():
    """parse_frontmatter should parse valid YAML frontmatter."""
    content = "---\nname: test\ntype: world\n---\n\nbody content"
    result = parse_frontmatter(content)
    assert result["name"] == "test"
    assert result["type"] == "world"


def test_parse_frontmatter_invalid_yaml():
    """parse_frontmatter should return empty dict for invalid YAML."""
    content = "---\nname: test\ninvalid: [unclosed\n---\n\nbody"
    result = parse_frontmatter(content)
    assert result == {}


def test_parse_frontmatter_no_frontmatter():
    """parse_frontmatter should return empty dict when no frontmatter."""
    content = "just body content"
    result = parse_frontmatter(content)
    assert result == {}


def test_strip_frontmatter_valid():
    """strip_frontmatter should return body without frontmatter."""
    content = "---\nname: test\n---\n\nbody content"
    result = strip_frontmatter(content)
    assert result == "body content"


def test_strip_frontmatter_no_frontmatter():
    """strip_frontmatter should return original content when no frontmatter."""
    content = "just body content"
    result = strip_frontmatter(content)
    assert result == "just body content"


def test_serialize_frontmatter_basic():
    """serialize_frontmatter should produce valid markdown with frontmatter."""
    fm = {"name": "test", "type": "world", "created": "2024-01-01T00:00:00+00:00"}
    body = "Test content"
    result = serialize_frontmatter(fm, body)
    assert result.startswith("---\n")
    assert "name: test" in result
    assert "type: world" in result
    assert result.endswith(f"\n\n{body}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
