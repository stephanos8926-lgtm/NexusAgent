"""Tests for SessionManager — focused on TOCTOU race safety."""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.infrastructure.db import DatabaseManager, SessionRepository
from nexusagent.core.session import Session, SessionManager


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
async def db_and_repo():
    """Create a temporary DatabaseManager + SessionRepository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db_manager = DatabaseManager(db_url=f"sqlite+aiosqlite:///{db_path}")
        await db_manager.init_db()
        repo = SessionRepository(db_manager)
        yield db_manager, repo


@pytest.fixture
def mock_agent():
    """A mock agent that returns a simple string."""
    agent = MagicMock()
    agent.return_value = "Hello from agent"
    return agent


@pytest.fixture
def mock_memory():
    """A mock memory with async recall/remember."""
    mem = AsyncMock()
    mem.recall = AsyncMock(return_value=[])
    mem.remember = AsyncMock(return_value="mem-123")
    return mem


# ── Tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_or_create_concurrent(db_and_repo, mock_agent, mock_memory):
    """Concurrent get_or_create() calls return the same session with no leak.

    Exercises the _creating guard: when N coroutines race to create the same
    session_id, exactly one Session is created and all callers receive it.
    Any losing session is close()-ed to prevent a leak.
    """
    _, repo = db_and_repo
    manager = SessionManager()

    sid = "test-concurrent-race"
    results = []

    async def create_session():
        s = await manager.get_or_create(
            session_id=sid,
            working_dir="/tmp/work",
            agent=mock_agent,
            db_repo=repo,
        )
        results.append(s)

    # Launch many concurrent creations to maximize chance of hitting the race
    await asyncio.gather(*[create_session() for _ in range(20)])

    # All 20 callers must have received the exact same Session object
    assert len(results) == 20
    for r in results:
        assert r is results[0]

    # Only one session should be cached
    assert manager.active_count == 1

    # The winning session must be active
    assert results[0].status == "active"

    # _creating set must be clean (no stale entries)
    assert sid not in manager._creating
