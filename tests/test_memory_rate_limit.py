"""Tests for memory tool rate limiting."""

import os
import tempfile
from unittest.mock import patch

import pytest

from nexusagent.memory.rate_limiter import MemoryRateLimiter


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp()
    yield d
    import shutil

    shutil.rmtree(d)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the global rate limiter singleton before each test."""
    import nexusagent.tools.register_all as ra

    with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
        ra._memory_rate_limiter.reset()
    yield
    with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
        ra._memory_rate_limiter.reset()


# ── Unit tests for MemoryRateLimiter ──────────────────────────────────


class TestMemoryRateLimiterUnit:
    def test_allows_within_limit(self):
        with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
            limiter = MemoryRateLimiter(max_writes_per_minute=5, max_searches_per_minute=5)
            for _ in range(5):
                assert limiter.check_write() is None
                assert limiter.check_search() is None

    def test_blocks_after_write_limit(self):
        with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
            limiter = MemoryRateLimiter(max_writes_per_minute=3, max_searches_per_minute=60)
            # First 3 should succeed
            assert limiter.check_write() is None
            assert limiter.check_write() is None
            assert limiter.check_write() is None
            # 4th should be rate-limited
            msg = limiter.check_write()
            assert msg is not None
            assert "Rate limit exceeded" in msg

    def test_blocks_after_search_limit(self):
        with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
            limiter = MemoryRateLimiter(max_writes_per_minute=60, max_searches_per_minute=2)
            assert limiter.check_search() is None
            assert limiter.check_search() is None
            msg = limiter.check_search()
            assert msg is not None
            assert "Rate limit exceeded" in msg

    def test_write_and_search_independent(self):
        with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
            limiter = MemoryRateLimiter(max_writes_per_minute=1, max_searches_per_minute=10)
            # Exhaust write limit
            assert limiter.check_write() is None
            assert limiter.check_write() is not None
            # Search should still work
            assert limiter.check_search() is None

    def test_reset(self):
        with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
            limiter = MemoryRateLimiter(max_writes_per_minute=1, max_searches_per_minute=1)
            limiter.check_write()
            limiter.check_write()  # blocked
            limiter.reset()
            # Should work again after reset
            assert limiter.check_write() is None
            assert limiter.check_search() is None


# ── Integration tests via the tool registry ───────────────────────────


@pytest.mark.asyncio
async def test_memory_write_rate_limit(tmp_workspace):
    """Flood memory_write with 40 calls — calls after 30th should be rate-limited."""
    import nexusagent.tools.register_all as ra

    with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
        # Set write limit to 30 for this test
        ra._memory_rate_limiter = MemoryRateLimiter(
            max_writes_per_minute=30, max_searches_per_minute=60
        )

        allowed = 0
        blocked = 0
        for _ in range(40):
            result = await ra.memory_write(
                content="Test memory entry",
                type="observation",
                description="Entry",
                workspace=tmp_workspace,
                dedup_threshold=0,  # disable dedup to isolate rate limiting
            )
            if "Rate limit exceeded" in result:
                blocked += 1
            else:
                allowed += 1

        assert allowed == 30, f"Expected 30 allowed writes, got {allowed}"
        assert blocked == 10, f"Expected 10 blocked writes, got {blocked}"


@pytest.mark.asyncio
async def test_memory_search_rate_limit(tmp_workspace):
    """Flood memory_search with 70 calls — calls after 60th should be rate-limited."""
    import nexusagent.tools.register_all as ra

    with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
        # Set search limit to 60 for this test
        ra._memory_rate_limiter = MemoryRateLimiter(
            max_writes_per_minute=30, max_searches_per_minute=60
        )

        allowed = 0
        blocked = 0
        for _ in range(70):
            result = await ra.memory_search(
                query="test query",
                workspace=tmp_workspace,
            )
            if "Rate limit exceeded" in result:
                blocked += 1
            else:
                allowed += 1

        assert allowed == 60, f"Expected 60 allowed searches, got {allowed}"
        assert blocked == 10, f"Expected 10 blocked searches, got {blocked}"


@pytest.mark.asyncio
async def test_write_blocked_does_not_create_file(tmp_workspace):
    """Verify that rate-limited writes don't create memory files."""
    import nexusagent.tools.register_all as ra

    with patch("nexusagent.memory.rate_limiter._clock", return_value=0.0):
        ra._memory_rate_limiter = MemoryRateLimiter(
            max_writes_per_minute=2, max_searches_per_minute=60
        )

        # Use up the limit
        await ra.memory_write(
            content="Allowed entry 1",
            type="world",
            description="First",
            workspace=tmp_workspace,
            dedup_threshold=0,
        )
        await ra.memory_write(
            content="Allowed entry 2",
            type="world",
            description="Second",
            workspace=tmp_workspace,
            dedup_threshold=0,
        )

        # Third should be blocked
        result = await ra.memory_write(
            content="Should be blocked",
            type="world",
            description="Third",
            workspace=tmp_workspace,
            dedup_threshold=0,
        )
        assert "Rate limit exceeded" in result

        # Verify only 2 files were created
        bank_dir = os.path.join(tmp_workspace, "bank")
        if os.path.exists(bank_dir):
            md_files = [f for f in os.listdir(bank_dir) if f.endswith(".md")]
            assert len(md_files) == 2, f"Expected 2 files, found {len(md_files)}"
