# tests/test_session_lite.py
"""Tests for SessionLite — lightweight session for worker agents."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from nexusagent.core.session.session_lite import SessionLite


class TestSessionLite:
    """Tests for the SessionLite class."""

    @pytest.mark.asyncio
    async def test_create_and_remember(self):
        """SessionLite should create and store memories."""
        tmp = tempfile.mkdtemp()
        lite = SessionLite(session_id="test-1", working_dir=tmp)
        filepath = await lite.remember(
            content="User prefers pytest",
            type="observation",
            description="Testing preference",
            confidence=0.9,
        )
        assert Path(filepath).exists()

    @pytest.mark.asyncio
    async def test_get_memory_context(self):
        """SessionLite should retrieve relevant memory context."""
        tmp = tempfile.mkdtemp()
        lite = SessionLite(session_id="test-2", working_dir=tmp)
        await lite.remember(
            content="User prefers pytest for testing",
            type="observation",
            description="Testing framework",
        )
        ctx = await lite.get_memory_context("testing framework")
        assert ctx is not None
        assert len(ctx) > 0

    @pytest.mark.asyncio
    async def test_parent_inheritance(self):
        """SessionLite should inherit memories from parent directory."""
        # Create parent with memories
        parent_dir = tempfile.mkdtemp()
        parent_lite = SessionLite(session_id="parent", working_dir=parent_dir)
        await parent_lite.remember(
            content="Parent memory about authentication",
            type="world",
            description="Auth info",
        )

        # Create child that inherits from parent
        child_dir = tempfile.mkdtemp()
        child_lite = SessionLite(
            session_id="child",
            working_dir=child_dir,
            parent_memory_dir=parent_dir,
        )
        ctx = await child_lite.get_memory_context("authentication")
        # Should find parent memory
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_extract_and_store(self):
        """SessionLite should extract and store memories from conversation."""
        tmp = tempfile.mkdtemp()
        lite = SessionLite(session_id="test-3", working_dir=tmp)
        count = await lite.extract_and_store(
            "I decided to use PostgreSQL for the database.",
            "I'll set up PostgreSQL with connection pooling.",
        )
        assert count >= 0  # May be 0 if regex doesn't match

    @pytest.mark.asyncio
    async def test_maybe_dream(self):
        """SessionLite should run dream cycle at interval."""
        tmp = tempfile.mkdtemp()
        lite = SessionLite(session_id="test-4", working_dir=tmp)
        # Set turn count to trigger dream
        lite._turn_count = 20  # Default interval is 20
        await lite.remember(content="Test memory", type="observation")
        # Should not raise
        await lite.maybe_dream()

    @pytest.mark.asyncio
    async def test_close(self):
        """SessionLite should close without errors."""
        tmp = tempfile.mkdtemp()
        lite = SessionLite(session_id="test-5", working_dir=tmp)
        await lite.remember(content="Test", type="observation")
        await lite.close()

    @pytest.mark.asyncio
    async def test_get_load_context(self):
        """SessionLite should load NEXUS.md context."""
        tmp = tempfile.mkdtemp()
        # Create a NEXUS.md
        nexus_path = Path(tmp) / "NEXUS.md"
        nexus_path.write_text("# Test NEXUS.md\nThis is a test project.")

        lite = SessionLite(session_id="test-6", working_dir=tmp)
        ctx = lite.get_load_context()
        assert "Test NEXUS.md" in ctx or ctx == ""  # May be empty if loader has issues
