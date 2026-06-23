"""Tests for NATS SPOF elimination — Kanban t_3a205302.

Verifies health tracking, reconnect caps, and graceful degradation.
"""

import asyncio

import pytest


def test_reconnect_cap_effective():
    """_effective_max_reconnects caps -1 to a hard limit."""
    from nexusagent.infrastructure.bus import _effective_max_reconnects

    # -1 means "infinite" in NATS client — should be capped
    assert _effective_max_reconnects(-1) == 30
    # Positive values below cap pass through
    assert _effective_max_reconnects(5) == 5
    # Positive values above cap are clamped
    assert _effective_max_reconnects(100) == 30
    # Zero means no reconnects
    assert _effective_max_reconnects(0) == 0


def test_bus_health_properties():
    """AgentBus has is_connected, is_degraded, reconnect_count properties."""
    from nexusagent.infrastructure.bus import AgentBus

    bus = AgentBus(url="nats://localhost:4222")

    # Initially not connected
    assert bus.is_connected is False
    assert bus.is_degraded is False
    assert bus.reconnect_count == 0


def test_wait_for_connection_timeout():
    """wait_for_connection returns False on timeout when not connected."""
    from nexusagent.infrastructure.bus import AgentBus

    bus = AgentBus(url="nats://localhost:4222")

    # Should return False immediately (not connected, short timeout)
    result = asyncio.run(bus.wait_for_connection(timeout=0.01))
    assert result is False


def test_check_health_returns_dict():
    """check_health returns a health snapshot dict."""
    from nexusagent.infrastructure.bus import AgentBus

    bus = AgentBus(url="nats://localhost:4222")
    health = asyncio.run(bus.check_health())

    assert isinstance(health, dict)
    assert "healthy" in health
    assert "connected" in health
    assert "degraded" in health
    assert "reconnect_count" in health
    assert "max_reconnects" in health
    assert health["connected"] is False
    assert health["healthy"] is False


def test_subscribe_durable_signature():
    """subscribe_durable has the expected signature."""
    import inspect

    from nexusagent.infrastructure.bus import AgentBus

    sig = inspect.signature(AgentBus.subscribe_durable)
    params = list(sig.parameters.keys())
    assert "self" in params
    assert "subject" in params
    assert "callback" in params
    assert "stream" in params
    assert "durable" in params
    assert "batch_size" in params
    assert "batch_timeout" in params

    # Defaults
    assert sig.parameters["stream"].default == "nexus_tasks"
    assert sig.parameters["durable"].default == "nexus_worker"
    assert sig.parameters["batch_size"].default == 10
    assert sig.parameters["batch_timeout"].default == 5.0


def test_subscribe_durable_not_connected():
    """subscribe_durable raises when not connected."""
    from nexusagent.infrastructure.bus import AgentBus

    bus = AgentBus(url="nats://localhost:4222")
    with pytest.raises(RuntimeError, match="not connected"):
        asyncio.run(bus.subscribe_durable("test.subject", lambda msg: None))
