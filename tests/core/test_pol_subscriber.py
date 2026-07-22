# tests/core/test_pol_subscriber.py
"""Tests for POLSubscriber event routing and automatic intervention triggers."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from nexusagent.core.events.base import SystemEvent
from nexusagent.core.pol_subscriber import POLSubscriber
from nexusagent.core.pol import POLControlPlane, set_pol_control_plane


@pytest.mark.asyncio
async def test_pol_subscriber_event_routing(tmp_path):
    """Test that events received by POLSubscriber automatically trigger interventions."""
    persistence_file = str(tmp_path / "pol_interventions.json")
    pol_plane = POLControlPlane(persistence_path=persistence_file)
    set_pol_control_plane(pol_plane)

    subscriber = POLSubscriber()

    # Emit worker.failed event
    e_fail = SystemEvent(
        source="worker_a",
        type="worker.failed",
        payload={"task_id": "task-xyz", "error": "OutOfMemory error occurred"}
    )
    await subscriber.handle_event(e_fail)

    # Check that intervention was created automatically in the POL Control Plane
    intvs = pol_plane.list_interventions()
    assert len(intvs) == 1
    assert intvs[0]["task_id"] == "task-xyz"
    assert intvs[0]["reason"] == "worker.failed"
    assert "OutOfMemory" in intvs[0]["guidance"]
    assert intvs[0]["status"] == "pending"

    # Emit tool.denied event
    e_denied = SystemEvent(
        source="policy",
        type="tool.denied",
        payload={"task_id": "task-xyz", "reason": "No shell commands outside workspace"}
    )
    await subscriber.handle_event(e_denied)

    intvs = pol_plane.list_interventions()
    assert len(intvs) == 2
    assert intvs[1]["reason"] == "repeated_tool_failure"
    assert "No shell commands" in intvs[1]["guidance"]
