"""Unit tests for capability audit trail logging."""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from nexusagent.infrastructure.db import DatabaseManager
from nexusagent.infrastructure.events.event_store import EventStore, set_event_store
from nexusagent.security.audit import (
    audit_denial,
    audit_denial_sync,
    audit_grant,
    audit_grant_sync,
)


@pytest.fixture(autouse=True)
async def temp_event_store():
    """Hermetic file-backed SQLite DatabaseManager and EventStore for testing."""
    fd, temp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    manager = DatabaseManager(db_url=f"sqlite+aiosqlite:///{temp_path}")
    await manager.init_db()
    store = EventStore(db_manager=manager)
    store._initialized = True

    # Save original and restore it after
    from nexusagent.infrastructure.events.event_store import _event_store

    original_store = _event_store
    set_event_store(store)

    yield store

    await manager.close()
    set_event_store(original_store)

    try:
        os.remove(temp_path)
    except OSError:
        pass


@pytest.mark.asyncio
async def test_audit_grant_and_denial_async(temp_event_store):
    """Verify async audit trail logging inserts events into the EventStore."""
    store = temp_event_store
    initial_events = await store.query()
    initial_count = len(initial_events)

    # Log a grant asynchronously
    await audit_grant(
        agent_id="test-agent-async",
        capability="filesystem.read",
        scope="Workspace directory",
        rule="Explicit test rule",
    )

    # Log a denial asynchronously
    await audit_denial(
        agent_id="test-agent-async",
        capability="shell.execute",
        scope="Workspace directory",
        rule="Strict block rule",
        reason="Execution of shell commands is disallowed",
    )

    # Query events from EventStore
    updated_events = await store.query()
    assert len(updated_events) == initial_count + 2

    # Check the grant event details
    grant_event = updated_events[-2]
    assert grant_event.type == "allowed"
    assert grant_event.payload["task_id"] == "test-agent-async"
    assert "filesystem.read" in grant_event.payload["action"]

    # Check the denial event details
    denial_event = updated_events[-1]
    assert denial_event.type == "denied"
    assert denial_event.payload["task_id"] == "test-agent-async"
    assert "shell.execute" in denial_event.payload["action"]
    assert denial_event.payload["reason"] == "Execution of shell commands is disallowed"


@pytest.mark.asyncio
async def test_audit_grant_and_denial_sync(temp_event_store):
    """Verify sync audit trail logging inserts events into the EventStore."""
    store = temp_event_store
    initial_events = await store.query()
    initial_count = len(initial_events)

    # Log a grant synchronously
    audit_grant_sync(
        agent_id="test-agent-sync",
        capability="git.commit",
        scope="Current repository",
        rule="Tester bypass rule",
    )

    # Log a denial synchronously
    audit_denial_sync(
        agent_id="test-agent-sync",
        capability="network.access",
        scope="Allowlisted endpoints",
        rule="Outbound block",
        reason="Destination not on allowlist",
    )

    # Wait for background queue thread to process sync events (up to 2 seconds)
    for _ in range(20):
        updated_events = await store.query()
        if len(updated_events) == initial_count + 2:
            break
        await asyncio.sleep(0.1)
    else:
        updated_events = await store.query()

    assert len(updated_events) == initial_count + 2

    grant_event = updated_events[-2]
    assert grant_event.type == "allowed"
    assert grant_event.payload["task_id"] == "test-agent-sync"

    denial_event = updated_events[-1]
    assert denial_event.type == "denied"
    assert denial_event.payload["task_id"] == "test-agent-sync"
