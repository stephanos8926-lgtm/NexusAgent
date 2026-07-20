"""Tests for the event system - SystemEvent base and typed subclasses."""

from __future__ import annotations

import pytest

from nexusagent.core.events import (
    EventEmitter,
    EventType,
    SystemEvent,
    TaskEvent,
    WorkerEvent,
    get_emitter,
)


class TestSystemEvent:
    """Tests for the base SystemEvent class."""

    def test_system_event_creation(self):
        """Verify SystemEvent can be created with required fields."""
        event = SystemEvent(
            source="test_source",
            type="test_type",
            payload={"key": "value"},
        )
        assert event.source == "test_source"
        assert event.type == "test_type"
        assert event.payload == {"key": "value"}
        assert event.id is not None
        assert event.timestamp is not None

    def test_system_event_nats_subject(self):
        """Verify NATS subject is generated correctly."""
        event = SystemEvent(
            source="test",
            type="test_type",
            payload={},
        )
        event.category = EventType.TASK
        assert event.nats_subject == "nexus.task.test_type"

    def test_system_event_serialization(self):
        """Verify event can be serialized to JSON."""
        event = SystemEvent(
            source="test",
            type="test_type",
            payload={"key": "value"},
        )
        json_str = event.to_json()
        assert "test" in json_str
        assert "test_type" in json_str
        assert "key" in json_str
        assert "value" in json_str

    def test_system_event_from_json(self):
        """Verify event can be deserialized from JSON."""
        event = SystemEvent(
            source="test",
            type="test_type",
            payload={"key": "value"},
        )
        json_str = event.to_json()
        restored = SystemEvent.from_json(json_str)
        assert restored.source == event.source
        assert restored.type == event.type
        assert restored.payload == event.payload


class TestTaskEvent:
    """Tests for TaskEvent and its factory methods."""

    def test_task_event_created_factory(self):
        """Test task.created factory method."""
        event = TaskEvent.created(
            source="test_source",
            task_id="task-123",
            objective="Test objective",
            owner="worker-1",
        )
        assert event.type == "created"
        assert event.payload["task_id"] == "task-123"
        assert event.payload["objective"] == "Test objective"
        assert event.payload["owner"] == "worker-1"

    def test_task_event_started_factory(self):
        """Test task.started factory method."""
        event = TaskEvent.started(
            source="test_source",
            task_id="task-123",
            owner="worker-1",
        )
        assert event.type == "started"
        assert event.payload["task_id"] == "task-123"
        assert event.payload["owner"] == "worker-1"

    def test_task_event_completed_factory(self):
        """Test task.completed factory method."""
        event = TaskEvent.completed(
            source="test_source",
            task_id="task-123",
            owner="worker-1",
            result="success",
        )
        assert event.type == "completed"
        assert event.payload["task_id"] == "task-123"
        assert event.payload["result"] == "success"

    def test_task_event_failed_factory(self):
        """Test task.failed factory method."""
        event = TaskEvent.failed(
            source="test_source",
            task_id="task-123",
            owner="worker-1",
            error="Something went wrong",
        )
        assert event.type == "failed"
        assert event.payload["task_id"] == "task-123"
        assert event.payload["error"] == "Something went wrong"

    def test_task_event_properties(self):
        """Test task_id, error, and result properties."""
        event = TaskEvent.failed(
            source="test",
            task_id="task-123",
            error="Test error",
        )
        assert event.task_id == "task-123"
        assert event.error == "Test error"
        assert event.result is None

        event = TaskEvent.completed(
            source="test",
            task_id="task-456",
            result="done",
        )
        assert event.task_id == "task-456"
        assert event.result == "done"


class TestWorkerEvent:
    """Tests for WorkerEvent."""

    def test_worker_event_started_factory(self):
        """Test worker.started factory."""
        event = WorkerEvent.started(
            source="test",
            worker_id="worker-1",
            task_id="task-123",
            description="Test task",
        )
        assert event.type == "started"
        assert event.payload["worker_id"] == "worker-1"
        assert event.payload["task_id"] == "task-123"

    def test_worker_event_failed_factory(self):
        """Test worker.failed factory."""
        event = WorkerEvent.failed(
            source="test",
            worker_id="worker-1",
            task_id="task-123",
            error="Failed",
        )
        assert event.type == "failed"
        assert event.payload["error"] == "Failed"

    def test_worker_event_recovered_factory(self):
        """Test worker.recovered factory."""
        event = WorkerEvent.recovered(
            source="test",
            worker_id="worker-1",
            task_id="task-123",
            checkpoint="checkpoint-data",
        )
        assert event.type == "recovered"
        assert event.payload["checkpoint"] == "checkpoint-data"


class TestEventEmitter:
    """Tests for EventEmitter."""

    @pytest.mark.asyncio
    async def test_emit_event(self):
        """Test async event emission."""
        emitter = EventEmitter()
        from nexusagent.core.events import EventType, TaskEvent
        event = TaskEvent(
            source="test",
            type="created",
            payload={"task_id": "test-1", "objective": "Test", "owner": "tester"},
        )
        event.category = EventType.TASK
        # Just verify it doesn't crash (no NATS connection in tests)
        try:
            await emitter.emit(event)
        except Exception as e:
            # NATS not connected is expected in tests
            assert "nats" in str(e).lower() or "bus" in str(e).lower() or "connect" in str(e).lower()

    def test_emit_event_sync(self):
        """Test synchronous event emission."""
        emitter = EventEmitter()
        from nexusagent.core.events import EventType, TaskEvent
        event = TaskEvent(
            source="test",
            type="created",
            payload={"task_id": "test-1", "objective": "Test", "owner": "tester"},
        )
        event.category = EventType.TASK
        # Should not crash even without NATS
        emitter.emit_sync(event)


class TestEventIntegration:
    """Integration tests for event system with Task/WorkerPool."""

    def test_task_transition_emits_event(self):
        """Verify Task.transition_to emits events."""
        from nexusagent.core.task.task_state import Task, TaskState

        # Replace emitter with a mock to capture events
        captured = []
        original_emit = get_emitter().emit_sync

        def capture_emit(event):
            captured.append(event)

        import nexusagent.core.events as events_module
        events_module.get_emitter().emit_sync = capture_emit

        try:
            task = Task(id="test-1", objective="Test", owner="test")
            task.transition_to(TaskState.PLANNING)
            task.transition_to(TaskState.EXECUTING)

            assert len(captured) == 2
            assert captured[0].type == "created"
            assert captured[1].type == "started"
        finally:
            events_module.get_emitter().emit_sync = original_emit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
