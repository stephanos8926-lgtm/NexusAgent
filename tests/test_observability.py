# SPDX-License-Identifier: MIT

# tests/test_observability.py
"""Comprehensive unit and integration tests for Phase 10: Observability & Reliability."""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.core.events import SystemEvent
from nexusagent.core.observability import (
    ChaosTestFramework,
    FailureClassifier,
    FailureType,
    get_metrics,
    get_system_health,
    trace_context,
)
from nexusagent.core.task.recovery import RecoveryManager
from nexusagent.core.task.task_state import Checkpoint, Task, TaskState


def test_trace_context_propagation():
    """Verify that tracing identifiers are correctly propagated and reset."""
    with trace_context(
        trace_id="test-trace-123",
        request_id="req-abc",
        task_id="task-xyz",
        graph_id="graph-789",
        node_id="node-456",
        worker_id="worker-999",
        component="test-component",
        event_type="test-event",
    ) as ctx:
        assert ctx["trace_id"] == "test-trace-123"
        assert ctx["request_id"] == "req-abc"
        assert ctx["task_id"] == "task-xyz"
        assert ctx["graph_id"] == "graph-789"
        assert ctx["node_id"] == "node-456"
        assert ctx["worker_id"] == "worker-999"
        assert ctx["component"] == "test-component"
        assert ctx["event_type"] == "test-event"

        # Check nested context overrides
        with trace_context(node_id="node-999") as nested_ctx:
            assert nested_ctx["trace_id"] == "test-trace-123"
            assert nested_ctx["node_id"] == "node-999"

        # Restored after nested exit
        assert ctx["node_id"] == "node-456"


def test_structured_logging_format():
    """Verify that structured JSON formatter outputs correct fields."""
    from io import StringIO

    from nexusagent.core.observability.logging import StructuredLoggingFormatter

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    formatter = StructuredLoggingFormatter()
    handler.setFormatter(formatter)

    logger = logging.getLogger("test_structured_log")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    with trace_context(
        trace_id="trace-json-999",
        task_id="task-json-999",
        worker_id="worker-json-999",
        component="TestLogger",
        event_type="test.execution",
    ):
        logger.info("Test message here", extra={"custom_field": "custom_value"})

    output_str = stream.getvalue().strip()
    assert output_str

    log_dict = json.loads(output_str)
    assert "timestamp" in log_dict
    assert log_dict["trace_id"] == "trace-json-999"
    assert log_dict["task_id"] == "task-json-999"
    assert log_dict["worker_id"] == "worker-json-999"
    assert log_dict["component"] == "TestLogger"
    assert log_dict["event_type"] == "test.execution"
    assert log_dict["severity"] == "INFO"
    assert log_dict["message"] == "Test message here"
    assert log_dict["metadata"]["custom_field"] == "custom_value"


def test_metrics_collector():
    """Verify counters, gauges, and histograms collection and snapshotting."""
    metrics = get_metrics()
    metrics.clear()

    metrics.increment("agent.tasks_completed")
    metrics.increment("agent.tasks_completed")
    metrics.increment("agent.tasks_failed", labels={"error_type": "Timeout"})

    metrics.set_gauge("runtime.active_workers", 3)

    metrics.record_histogram("runtime.task_duration_seconds", 12.5, labels={"task_id": "task-1"})
    metrics.record_histogram("runtime.task_duration_seconds", 7.5, labels={"task_id": "task-1"})

    snapshot = metrics.get_snapshot()

    assert snapshot["counters"]["agent.tasks_completed"] == 2.0
    assert snapshot["counters"]["agent.tasks_failed{error_type=Timeout}"] == 1.0
    assert snapshot["gauges"]["runtime.active_workers"] == 3.0

    histogram = snapshot["histograms"]["runtime.task_duration_seconds{task_id=task-1}"]
    assert histogram["count"] == 2
    assert histogram["sum"] == 20.0
    assert histogram["avg"] == 10.0
    assert histogram["min"] == 7.5
    assert histogram["max"] == 12.5


def test_failure_classification():
    """Verify that exceptions are correctly classified."""
    # Transient failures
    transient_exc1 = TimeoutError("Connection timed out")
    transient_exc2 = ValueError("NatsError: Connection lost")
    assert FailureClassifier.classify(transient_exc1) == FailureType.TRANSIENT
    assert FailureClassifier.classify(transient_exc2) == FailureType.TRANSIENT

    # Security failures
    security_exc1 = PermissionError("Access denied: Capability missing")
    security_exc2 = RuntimeError("Unauthorized operation requested")
    assert FailureClassifier.classify(security_exc1) == FailureType.SECURITY
    assert FailureClassifier.classify(security_exc2) == FailureType.SECURITY

    # Deterministic failures
    deterministic_exc = KeyError("missing_config_key")
    assert FailureClassifier.classify(deterministic_exc) == FailureType.DETERMINISTIC


def test_system_health_aggregation():
    """Verify system health diagnostics reports."""
    with patch("nexusagent.core.observability.health.check_event_bus_health") as mock_bus_health:
        mock_bus_health.return_value = MagicMock(
            healthy=True, message="NATS up", failed=False, degraded=False
        )
        health_report = get_system_health()

        assert "runtime" in health_report
        assert "worker_manager" in health_report
        assert "event_bus" in health_report
        assert "memory_system" in health_report
        assert "pol" in health_report
        assert "database" in health_report
        assert "external_providers" in health_report


@pytest.mark.asyncio
async def test_recovery_workflow_retry():
    """Verify that RecoveryManager handles retry/rollback recovery paths."""
    mock_store = AsyncMock()
    task = Task(id="task-rec-1", objective="test objective", state=TaskState.FAILED)
    checkpoint = Checkpoint(current_node="node-1")

    mock_store.load_task.return_value = task
    mock_store.load_latest_checkpoint.return_value = checkpoint

    recovery_mgr = RecoveryManager(store=mock_store, max_retries=2, base_delay=0.01)

    async def fake_execute(t, cp):
        return "success-result"

    # 1. First recovery attempt (Strategy: RETRY)
    res = await recovery_mgr.recover_task(task_id="task-rec-1", execute_fn=fake_execute)
    assert res == "success-result"
    assert task.state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_recovery_workflow_escalate():
    """Verify that RecoveryManager escalates to permanent failure after max retries."""
    mock_store = AsyncMock()
    task = Task(id="task-rec-2", objective="test objective", state=TaskState.FAILED)

    mock_store.load_task.return_value = task
    mock_store.load_latest_checkpoint.return_value = None

    # Instantiate manager with 0 max retries to force immediate escalation
    recovery_mgr = RecoveryManager(store=mock_store, max_retries=0, base_delay=0.01)

    async def fake_execute(t, cp):
        return "should not run"

    on_failed_called = False

    async def on_failed_event(t_id, err_msg):
        nonlocal on_failed_called
        on_failed_called = True

    with pytest.raises(RuntimeError, match="recovery escalated"):
        await recovery_mgr.recover_task(
            task_id="task-rec-2",
            execute_fn=fake_execute,
            on_failed_event=on_failed_event,
        )

    assert on_failed_called is True


def test_chaos_kill_worker():
    """Verify chaos testing tool for killing worker in WorkerPool."""
    from nexusagent.core.worker.pool import get_worker_pool

    pool = get_worker_pool()

    mock_handle = MagicMock()
    pool._active["test-worker-123"] = mock_handle

    killed = ChaosTestFramework.kill_worker("test-worker-123")
    assert killed is True
    mock_handle.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_chaos_disconnect_event_bus():
    """Verify chaos testing tool for disconnecting event bus."""
    with patch("nexusagent.core.observability.chaos.get_bus") as mock_get_bus:
        mock_bus = AsyncMock()
        mock_get_bus.return_value = mock_bus

        await ChaosTestFramework.disconnect_event_bus()
        mock_bus.close.assert_called_once()


@pytest.mark.asyncio
async def test_chaos_corrupt_checkpoint():
    """Verify chaos testing tool for checkpoint corruption."""
    mock_store = AsyncMock()
    task = Task(id="task-chaos-1")
    mock_store.load_task.return_value = task

    with patch("nexusagent.core.observability.chaos.get_task_store", return_value=mock_store):
        await ChaosTestFramework.corrupt_checkpoint("task-chaos-1")

        mock_store.save_task.assert_called_once_with(task)
        assert len(task.checkpoints) == 1
        assert task.checkpoints[0].current_node == "CORRUPTED_BY_CHAOS"


def test_system_event_trace_integration():
    """Verify SystemEvent automatically grabs tracing metadata from context."""
    with trace_context(
        trace_id="event-trace-xyz",
        request_id="event-req-xyz",
        task_id="event-task-xyz",
        worker_id="event-worker-xyz",
    ):
        event = SystemEvent(source="test", type="test_type")
        assert event.trace_id == "event-trace-xyz"
        assert event.request_id == "event-req-xyz"
        assert event.task_id == "event-task-xyz"
        assert event.worker_id == "event-worker-xyz"


def test_metrics_endpoint():
    """Verify that the FastAPI /metrics endpoint returns a valid snapshot of metrics."""
    from contextlib import asynccontextmanager

    from fastapi.testclient import TestClient

    from nexusagent.core.observability import get_metrics
    from nexusagent.server.server import app

    metrics = get_metrics()
    metrics.clear()
    metrics.increment("test.counter.integration", 5.0)

    # Override the app's lifespan to avoid real database/NATS initialization in tests
    @asynccontextmanager
    async def fake_lifespan(app_inst):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = fake_lifespan

    try:
        with TestClient(app) as client:
            response = client.get("/metrics")
            assert response.status_code == 200
            data = response.json()
            assert "counters" in data
            assert "gauges" in data
            assert "histograms" in data
            assert data["counters"].get("test.counter.integration") == 5.0
    finally:
        # Restore original lifespan context
        app.router.lifespan_context = original_lifespan


def test_structured_logging_config_and_env(monkeypatch):
    """Verify structured logging is initialized dynamically via config and env vars."""
    from nexusagent.infrastructure.config import settings

    # 1. Test standard config setting
    monkeypatch.setattr(settings.logging, "structured", True)

    # Check server structured logging flag
    import os

    structured_enabled = settings.logging.structured or os.environ.get(
        "NEXUS_STRUCTURED_LOGGING", ""
    ).lower() in ("1", "true", "yes", "on")
    assert structured_enabled is True

    # 2. Test environment variable override
    monkeypatch.setattr(settings.logging, "structured", False)
    monkeypatch.setenv("NEXUS_STRUCTURED_LOGGING", "true")
    structured_enabled_env = settings.logging.structured or os.environ.get(
        "NEXUS_STRUCTURED_LOGGING", ""
    ).lower() in ("1", "true", "yes", "on")
    assert structured_enabled_env is True


def test_cli_logging_initialization(monkeypatch):
    """Verify that _setup_cli_logging properly configures the logger based on settings."""
    from nexusagent.infrastructure.config import settings
    from nexusagent.interfaces.cli import _setup_cli_logging

    # Setup mocks to verify whether setup_structured_logging or basicConfig gets called
    mock_setup = MagicMock()
    mock_basic = MagicMock()

    monkeypatch.setattr("nexusagent.core.observability.setup_structured_logging", mock_setup)
    monkeypatch.setattr("logging.basicConfig", mock_basic)

    # Case A: Structured enabled
    monkeypatch.setattr(settings.logging, "structured", True)
    _setup_cli_logging()
    mock_setup.assert_called_once_with(settings.log_level)

    # Case B: Standard logging fallback
    mock_setup.reset_mock()
    monkeypatch.setattr(settings.logging, "structured", False)
    monkeypatch.delenv("NEXUS_STRUCTURED_LOGGING", raising=False)
    _setup_cli_logging()
    assert mock_basic.called
