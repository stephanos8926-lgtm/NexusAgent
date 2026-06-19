import os
import tempfile

import pytest

from nexusagent.infrastructure.db import DatabaseManager, SessionRepository


@pytest.fixture
async def session_repo():
    """Create a SessionRepository with a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db_manager = DatabaseManager(db_url=f"sqlite+aiosqlite:///{db_path}")
        await db_manager.init_db()
        repo = SessionRepository(db_manager)
        yield repo


@pytest.mark.asyncio
async def test_create_session(session_repo: SessionRepository):
    sid = await session_repo.create_session(working_dir="/tmp/work", memory_id="mem-1")
    assert sid is not None
    assert len(sid) == 36

    sess = await session_repo.get_session(sid)
    assert sess is not None
    assert sess["id"] == sid
    assert sess["working_dir"] == "/tmp/work"
    assert sess["memory_id"] == "mem-1"
    assert sess["status"] == "active"
    assert sess["created_at"] is not None
    assert sess["updated_at"] is not None


@pytest.mark.asyncio
async def test_add_message(session_repo: SessionRepository):
    sid = await session_repo.create_session()

    mid1 = await session_repo.add_message(sid, "user", "Hello")
    mid2 = await session_repo.add_message(
        sid, "assistant", "Hi there!", tool_name="greet", tool_args={"name": "world"}
    )
    assert mid1 is not None
    assert mid2 is not None
    assert mid1 != mid2

    messages = await session_repo.get_messages(sid)
    assert len(messages) == 2

    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[0]["tool_name"] is None
    assert messages[0]["tool_args"] is None

    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi there!"
    assert messages[1]["tool_name"] == "greet"
    assert messages[1]["tool_args"] == {"name": "world"}


@pytest.mark.asyncio
async def test_session_status_transition(session_repo: SessionRepository):
    sid = await session_repo.create_session()
    sess = await session_repo.get_session(sid)
    assert sess["status"] == "active"

    await session_repo.update_status(sid, "idle")
    sess = await session_repo.get_session(sid)
    assert sess["status"] == "idle"

    await session_repo.update_status(sid, "closed")
    sess = await session_repo.get_session(sid)
    assert sess["status"] == "closed"


@pytest.mark.asyncio
async def test_find_sessions_by_working_dir(session_repo: SessionRepository):
    # Create sessions in two different working directories
    sid1 = await session_repo.create_session(working_dir="/project/foo", memory_id="m1")
    sid2 = await session_repo.create_session(working_dir="/project/foo", memory_id="m2")
    sid3 = await session_repo.create_session(working_dir="/project/bar", memory_id="m3")
    sid4 = await session_repo.create_session(working_dir="/project/foo", memory_id="m4")

    # Should return only sessions for /project/foo, ordered by created_at desc
    results = await session_repo.find_sessions_by_working_dir("/project/foo")
    assert len(results) == 3
    ids = [r["id"] for r in results]
    assert sid1 in ids
    assert sid2 in ids
    assert sid4 in ids
    assert sid3 not in ids

    # All results should have the correct working_dir
    for r in results:
        assert r["working_dir"] == "/project/foo"

    # Should return only sessions for /project/bar
    results_bar = await session_repo.find_sessions_by_working_dir("/project/bar")
    assert len(results_bar) == 1
    assert results_bar[0]["id"] == sid3

    # Exclude should filter out the given session ID
    results_excl = await session_repo.find_sessions_by_working_dir(
        "/project/foo", exclude=sid4
    )
    ids_excl = [r["id"] for r in results_excl]
    assert sid4 not in ids_excl
    assert len(results_excl) == 2

    # Limit should cap results
    results_limited = await session_repo.find_sessions_by_working_dir(
        "/project/foo", limit=2
    )
    assert len(results_limited) == 2

    # Non-matching directory returns empty list
    results_empty = await session_repo.find_sessions_by_working_dir("/no/such/dir")
    assert results_empty == []
