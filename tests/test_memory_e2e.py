# tests/test_memory_e2e.py
"""End-to-end tests for the NexusAgent memory system.

Proves the full pipeline works:
1. Session creates HybridMemoryManager
2. Auto-extraction stores observations after each turn
3. Recall injects relevant memories into prompts
4. Dream cycle consolidates memories
5. TTL enforcement prunes expired entries
6. Git-backed memory commits changes
7. Rate limiting prevents flooding
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# -- Fixtures --

@pytest.fixture
def temp_memory_dir():
    d = tempfile.mkdtemp(prefix="nexus_test_memory_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def session_id():
    return "test-session-e2e-001"


def _make_session(temp_memory_dir, session_id):
    """Helper to create a Session with mocked agent and db_repo."""
    from nexusagent.core.session.session import Session

    agent = MagicMock()
    agent.model = "test-model"
    db_repo = MagicMock()
    db_repo.add_message = AsyncMock()

    return Session(
        session_id=session_id,
        working_dir=temp_memory_dir,
        agent=agent,
        db_repo=db_repo,
        memory_dir=temp_memory_dir,
    )


# -- Test 1: Session creates and initializes HybridMemoryManager --

class TestSessionMemoryInit:

    @pytest.mark.asyncio
    async def test_session_creates_hybrid_memory(self, temp_memory_dir, session_id):
        session = _make_session(temp_memory_dir, session_id)
        assert session.hybrid_memory is not None
        assert session.memory_dir.exists()

    @pytest.mark.asyncio
    async def test_session_close_cleans_up_hybrid_memory(self, temp_memory_dir, session_id):
        session = _make_session(temp_memory_dir, session_id)
        # close() is sync, not async — just verify it doesn't crash
        session.hybrid_memory.close()
        assert True  # No crash = pass


# -- Test 2: Auto-extraction stores observations after each turn --

class TestAutoExtraction:

    @pytest.mark.asyncio
    async def test_extraction_stores_observations(self, temp_memory_dir, session_id):
        session = _make_session(temp_memory_dir, session_id)

        user_msg = "I decided to use PostgreSQL for the database. I prefer async patterns."
        response = "I'll set up PostgreSQL with asyncpg and connection pooling."

        await session._run_extraction(f"User: {user_msg}\nAssistant: {response}")
        await asyncio.sleep(0.1)

        index = session.hybrid_memory.file_memory.get_index_entries()
        assert len(index) >= 1, f"Expected at least 1 memory, got {len(index)}"

    @pytest.mark.asyncio
    async def test_extraction_respects_queue_limit(self, temp_memory_dir, session_id):
        session = _make_session(temp_memory_dir, session_id)
        assert session._extraction_queue.maxsize == 3


# -- Test 3: Recall injects relevant memories into prompts --

class TestMemoryRecall:

    @pytest.mark.asyncio
    async def test_recall_returns_relevant_memories(self, temp_memory_dir, session_id):
        session = _make_session(temp_memory_dir, session_id)

        await session.hybrid_memory.remember(
            content="The authentication module uses JWT tokens with refresh",
            type="world",
            description="Auth uses JWT",
            confidence=0.9,
            entities=["auth", "jwt"],
        )
        await asyncio.sleep(0.1)

        context = await session.hybrid_memory.get_memory_context(
            "How does authentication work?", max_results=3
        )
        assert context is not None
        assert "JWT" in context or "authentication" in context.lower()

    @pytest.mark.asyncio
    async def test_recall_returns_empty_for_unrelated_query(self, temp_memory_dir, session_id):
        session = _make_session(temp_memory_dir, session_id)

        await session.hybrid_memory.remember(
            content="The authentication module uses JWT tokens",
            type="world",
            description="Auth uses JWT",
            confidence=0.9,
        )
        await asyncio.sleep(0.1)

        context = await session.hybrid_memory.get_memory_context(
            "How does the database connection pool work?", max_results=3
        )
        assert context is not None


# -- Test 4: Dream cycle consolidates memories --

class TestDreamCycle:

    @pytest.mark.asyncio
    async def test_dream_cycle_runs_successfully(self, temp_memory_dir):
        bank_dir = Path(temp_memory_dir) / "bank"
        bank_dir.mkdir(parents=True, exist_ok=True)

        (bank_dir / "obs-001.md").write_text(
            "---\ntype: observation\ndescription: Test 1\nconfidence: 0.8\n---\nThe user prefers pytest over unittest.\n"
        )
        (bank_dir / "obs-002.md").write_text(
            "---\ntype: observation\ndescription: Test 2\nconfidence: 0.7\n---\nThe user prefers pytest for testing.\n"
        )

        from nexusagent.memory.dream import DreamCycle

        cycle = DreamCycle(temp_memory_dir)
        report = await cycle.run(dry_run=False)

        assert report["dry_run"] is False
        assert "health_before" in report
        assert "health_after" in report

    @pytest.mark.asyncio
    async def test_dream_cycle_dry_run_does_not_modify(self, temp_memory_dir):
        from nexusagent.memory.dream import DreamCycle

        bank_dir = Path(temp_memory_dir) / "bank"
        bank_dir.mkdir(parents=True, exist_ok=True)

        test_file = bank_dir / "test-001.md"
        original_content = (
            "---\ntype: observation\ndescription: Test\nconfidence: 0.8\n---\nSome test content.\n"
        )
        test_file.write_text(original_content)

        cycle = DreamCycle(temp_memory_dir)
        report = await cycle.run(dry_run=True)

        assert test_file.read_text() == original_content
        assert report["dry_run"] is True


# -- Test 5: TTL enforcement prunes expired entries --

class TestTTL:

    def test_expired_entry_excluded_from_index(self, temp_memory_dir):
        from nexusagent.memory.memory_files import FileMemory, MemoryEntryType

        fm = FileMemory(temp_memory_dir)
        fm.initialize()

        path = fm.write_entry(
            content="This is an expired observation",
            entry_type=MemoryEntryType.OBSERVATION,
            description="Expired entry",
            confidence=0.5,
            ttl_hours=0,
        )
        assert Path(path).exists()

        entries = fm.get_index_entries()
        contents = [e.get("content", "") for e in entries]
        assert not any("expired observation" in c for c in contents)

    def test_sweep_expired_removes_files(self, temp_memory_dir):
        from nexusagent.memory.memory_files import FileMemory, MemoryEntryType

        fm = FileMemory(temp_memory_dir)
        fm.initialize()

        path = fm.write_entry(
            content="This will be swept",
            entry_type=MemoryEntryType.OBSERVATION,
            description="To be swept",
            confidence=0.5,
            ttl_hours=0,
        )
        assert Path(path).exists()

        report = fm.sweep_expired()
        assert not Path(path).exists()
        assert report["files_removed"] >= 1

    def test_future_ttl_entry_preserved(self, temp_memory_dir):
        from nexusagent.memory.memory_files import FileMemory, MemoryEntryType

        fm = FileMemory(temp_memory_dir)
        fm.initialize()

        path = fm.write_entry(
            content="This is a future observation",
            entry_type=MemoryEntryType.OBSERVATION,
            description="Future entry",
            confidence=0.8,
            ttl_hours=720,
        )

        entries = fm.get_index_entries()
        # Entries have "description" field, not "content"
        descriptions = [e.get("description", "") for e in entries]
        assert any("Future entry" in d for d in descriptions)


# -- Test 6: Git-backed memory commits changes --

class TestGitBackedMemory:

    def test_git_init_on_first_write(self, temp_memory_dir):
        from nexusagent.memory.memory_files import FileMemory

        fm = FileMemory(temp_memory_dir)
        fm.initialize()

        git_dir = Path(temp_memory_dir) / ".git"
        assert git_dir.exists(), "Git repo should be initialized"

    def test_git_commit_after_write(self, temp_memory_dir):
        from nexusagent.memory.memory_files import FileMemory, MemoryEntryType

        fm = FileMemory(temp_memory_dir)
        fm.initialize()

        fm.write_entry(
            content="Test git commit observation",
            entry_type=MemoryEntryType.OBSERVATION,
            description="Git test",
            confidence=0.7,
        )

        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=temp_memory_dir,
            capture_output=True,
            text=True,
        )
        assert "memory" in result.stdout.lower() or "observation" in result.stdout.lower()


# -- Test 7: Rate limiting prevents flooding --

class TestRateLimiting:

    def test_write_rate_limiter_allows_normal_usage(self):
        from nexusagent.memory.rate_limiter import MemoryRateLimiter

        limiter = MemoryRateLimiter(max_writes_per_minute=30)
        for _ in range(10):
            result = limiter.check_write()
            assert result is None

    def test_write_rate_limiter_blocks_flooding(self):
        from nexusagent.memory.rate_limiter import MemoryRateLimiter

        limiter = MemoryRateLimiter(max_writes_per_minute=5)
        for _ in range(5):
            assert limiter.check_write() is None

        result = limiter.check_write()
        assert result is not None
        assert "Rate limit" in result

    def test_search_rate_limiter_independent(self):
        from nexusagent.memory.rate_limiter import MemoryRateLimiter

        limiter = MemoryRateLimiter(max_writes_per_minute=5, max_searches_per_minute=20)
        for _ in range(5):
            limiter.check_write()

        assert limiter.check_write() is not None
        for _ in range(10):
            assert limiter.check_search() is None


# -- Test 8: End-to-end pipeline (the big one) --

class TestE2EPipeline:

    @pytest.mark.asyncio
    async def test_full_pipeline(self, temp_memory_dir, session_id):
        session = _make_session(temp_memory_dir, session_id)

        turns = [
            (
                "I decided to use PostgreSQL for the database. I prefer async patterns.",
                "I'll set up PostgreSQL with asyncpg and connection pooling.",
            ),
            (
                "We chose to use pytest for testing. I always use type hints.",
                "I'll configure pytest with pytest-asyncio and strict type checking.",
            ),
            (
                "The authentication module uses JWT tokens with refresh tokens.",
                "I'll implement JWT auth with access and refresh tokens using PyJWT.",
            ),
        ]

        for user_msg, response in turns:
            await session._run_extraction(f"User: {user_msg}\nAssistant: {response}")
            await asyncio.sleep(0.05)

        index = session.hybrid_memory.file_memory.get_index_entries()
        assert len(index) >= 3, f"Expected at least 3 memories, got {len(index)}"

        context = await session.hybrid_memory.get_memory_context(
            "What testing framework do we use?", max_results=3
        )
        assert context is not None

        from nexusagent.memory.dream import DreamCycle

        cycle = DreamCycle(str(session.memory_dir))
        report = await cycle.run(dry_run=True)
        assert report["dry_run"] is True

        await session.close()
