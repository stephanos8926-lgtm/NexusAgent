# tests/core/events/test_event_store.py
"""Comprehensive tests for the EventStore, Subscribers, and APIs."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.core.events.base import SystemEvent
from nexusagent.core.events.dashboard_subscriber import DashboardSubscriber
from nexusagent.core.events.memory_subscriber import MemorySubscriber
from nexusagent.core.events.pol_subscriber import POLSubscriber
from nexusagent.infrastructure.db import DatabaseManager
from nexusagent.infrastructure.events.event_store import EventStore


@pytest.fixture
async def temp_db_manager():
    """In-memory SQLite DatabaseManager for testing."""
    manager = DatabaseManager(db_url="sqlite+aiosqlite:///:memory:")
    await manager.init_db()
    yield manager
    await manager.close()


@pytest.fixture
def mock_bus():
    """Mock NATS AgentBus."""
    bus = MagicMock()
    bus.nc = MagicMock()
    bus.nc.is_closed = False
    bus.publish = AsyncMock()
    return bus


@pytest.mark.asyncio
async def test_event_store_query_and_replay(temp_db_manager):
    """Test EventStore query and replay functions with full sqlite backing."""
    store = EventStore(db_manager=temp_db_manager)

    e1 = SystemEvent(source="component_x", type="task.created", payload={"id": "1"})
    e2 = SystemEvent(source="component_y", type="worker.failed", payload={"id": "2"})
    e3 = SystemEvent(source="component_x", type="task.completed", payload={"id": "1"})

    await store.append(e1)
    await store.append(e2)
    await store.append(e3)

    # Query all
    all_events = await store.query()
    assert len(all_events) == 3

    # Query by type
    failed_evts = await store.query(type="worker.failed")
    assert len(failed_evts) == 1
    assert failed_evts[0].source == "component_y"

    # Query by source
    comp_x_evts = await store.query(source="component_x")
    assert len(comp_x_evts) == 2

    # Replay
    replayed = await store.replay(from_id=e1.id)
    assert len(replayed) == 2
    assert replayed[0].id == e2.id
    assert replayed[1].id == e3.id


@pytest.mark.asyncio
async def test_durable_subscribers():
    """Test POL, Memory, and Dashboard Subscribers receiving events."""
    pol = POLSubscriber()
    mem = MemorySubscriber()
    dash = DashboardSubscriber()

    e_fail = SystemEvent(source="worker-a", type="worker.failed", payload={"error": "oom"})
    e_denied = SystemEvent(source="policy", type="tool.denied", payload={"tool_name": "run_shell"})
    e_comp = SystemEvent(source="worker-a", type="task.completed", payload={"task_id": "99"})

    # POLSubscriber
    await pol.handle_event(e_fail)
    await pol.handle_event(e_denied)
    await pol.handle_event(e_comp)  # POL ignores this
    assert len(pol.interventions) == 2

    # MemorySubscriber
    await mem.handle_event(e_fail)  # Ignored
    await mem.handle_event(e_comp)
    assert len(mem.processed_completions) == 1

    # DashboardSubscriber
    await dash.handle_event(e_fail)
    await dash.handle_event(e_comp)
    assert len(dash.events_received) == 2
