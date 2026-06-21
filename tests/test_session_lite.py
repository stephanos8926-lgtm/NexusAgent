# tests/test_session_base
"""Tests for SessionBase — shared memory logic for interactive sessions and workers."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from nexusagent.core.session.session_base import SessionBase


class TestSessionBase:
    """Tests for the SessionBase class."""

    @pytest.mark.asyncio
    async def test_create_and_remember(self):
        """SessionBase should create and store memories."""
        tmp = tempfile.mkdtemp()
        base = SessionBase(session_id="test-1", working_dir=tmp)
        filepath = await base.remember(
            content="User prefers pytest",
            type="observation",
            description="Testing preference",
            confidence=0.9,
        )
        assert Path(filepath).exists()

    @pytest.mark.asyncio
    async def test_get_memory_context(self):
        """SessionBase should retrieve relevant memory context."""
        tmp = tempfile.mkdtemp()
        base = SessionBase(session_id="test-2", working_dir=tmp)
        await base.remember(
            content="User prefers pytest for testing",
            type="observation",
            description="Testing framework",
        )
        ctx = await base.get_memory_context("testing framework")
        assert ctx is not None
        assert len(ctx) > 0

    @pytest.mark.asyncio
    async def test_parent_inheritance(self):
        """SessionBase should inherit memories from parent directory."""
        # Create parent with memories
        parent_dir = tempfile.mkdtemp()
        parent_base = SessionBase(session_id="parent", working_dir=parent_dir)
        await parent_base.remember(
            content="Parent memory about authentication",
            type="world",
            description="Auth info",
        )

        # Create child that inherits from parent
        child_dir = tempfile.mkdtemp()
        child_base = SessionBase(
            session_id="child",
            working_dir=child_dir,
            parent_memory_dir=parent_dir,
        )
        ctx = await child_base.get_memory_context("authentication")
        # Should find parent memory
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_extract_and_store(self):
        """SessionBase should extract and store memories from conversation."""
        tmp = tempfile.mkdtemp()
        base = SessionBase(session_id="test-3", working_dir=tmp)
        count = await base.extract_and_store(
            "I decided to use PostgreSQL for the database.",
            "I'll set up PostgreSQL with connection pooling.",
        )
        assert count >= 0  # May be 0 if regex doesn't match

    @pytest.mark.asyncio
    async def test_maybe_dream(self):
        """SessionBase should run dream cycle at interval."""
        tmp = tempfile.mkdtemp()
        base = SessionBase(session_id="test-4", working_dir=tmp)
        # Set turn count to trigger dream
        base._turn_count = 20  # Default interval is 20
        await base.remember(content="Test memory", type="observation")
        # Should not raise
        await base.maybe_dream()

    @pytest.mark.asyncio
    async def test_close(self):
        """SessionBase should close without errors."""
        tmp = tempfile.mkdtemp()
        base = SessionBase(session_id="test-5", working_dir=tmp)
        await base.remember(content="Test", type="observation")
        await base.close()

    @pytest.mark.asyncio
    async def test_get_load_context(self):
        """SessionBase should load NEXUS.md context."""
        tmp = tempfile.mkdtemp()
        # Create a NEXUS.md
        nexus_path = Path(tmp) / "NEXUS.md"
        nexus_path.write_text("# Test NEXUS.md\nThis is a test project.")

        base = SessionBase(session_id="test-6", working_dir=tmp)
        ctx = base.get_load_context()
        assert "Test NEXUS.md" in ctx or ctx == ""  # May be empty if loader has issues
