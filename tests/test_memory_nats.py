# tests/test_memory_nats.py
"""Tests for NATS-based distributed memory sharing."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.memory.nats_bus import (
    MemoryEvent,
    MemoryOperation,
    NatsMemoryBus,
    NatsMemoryListener,
)


class TestMemoryEvent:
    """Tests for the MemoryEvent dataclass."""

    def test_create_remember_event(self):
        event = MemoryEvent(
            operation=MemoryOperation.REMEMBER,
            session_id="test-session",
            payload={"content": "Test memory", "type": "observation"},
        )
        assert event.operation == MemoryOperation.REMEMBER
        assert event.session_id == "test-session"
        assert event.event_id is not None

    def test_serialization_roundtrip(self):
        event = MemoryEvent(
            operation=MemoryOperation.REMEMBER,
            session_id="test-session",
            payload={"content": "Test", "confidence": 0.8},
        )
        json_str = event.to_json()
        restored = MemoryEvent.from_json(json_str)
        assert restored.operation == event.operation
        assert restored.session_id == event.session_id
        assert restored.payload == event.payload

    def test_all_operations(self):
        for op in MemoryOperation:
            event = MemoryEvent(operation=op, session_id="s1")
            json_str = event.to_json()
            restored = MemoryEvent.from_json(json_str)
            assert restored.operation == op


class TestNatsMemoryBus:
    """Tests for the NatsMemoryBus publisher."""

    @pytest.fixture
    def mock_nats_client(self):
        client = AsyncMock()
        client.publish = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_publish_remember(self, mock_nats_client):
        bus = NatsMemoryBus(
            nats_client=mock_nats_client,
            subject_prefix="test.memory",
            session_id="worker-1",
        )
        event_id = await bus.publish_remember(
            content="User prefers pytest",
            memory_type="observation",
            description="Testing preference",
            confidence=0.9,
            entities=["testing"],
        )
        assert event_id is not None
        mock_nats_client.publish.assert_called_once()
        subject, data = mock_nats_client.publish.call_args[0]
        assert subject == "test.memory.remember"
        payload = json.loads(data)
        assert payload["operation"] == "remember"
        assert payload["session_id"] == "worker-1"
        assert payload["payload"]["content"] == "User prefers pytest"

    @pytest.mark.asyncio
    async def test_publish_delete(self, mock_nats_client):
        bus = NatsMemoryBus(
            nats_client=mock_nats_client,
            subject_prefix="test.memory",
            session_id="worker-1",
        )
        await bus.publish_delete("bank/obs-001.md")
        subject, data = mock_nats_client.publish.call_args[0]
        assert subject == "test.memory.delete"

    @pytest.mark.asyncio
    async def test_publish_promote(self, mock_nats_client):
        bus = NatsMemoryBus(
            nats_client=mock_nats_client,
            subject_prefix="test.memory",
            session_id="parent-session",
        )
        await bus.publish_promote(
            source_session_id="child-session",
            memory_path="bank/obs-001.md",
        )
        subject, data = mock_nats_client.publish.call_args[0]
        assert subject == "test.memory.promote"
        payload = json.loads(data)
        assert payload["payload"]["source_session_id"] == "child-session"

    @pytest.mark.asyncio
    async def test_publish_failure_is_non_fatal(self, mock_nats_client):
        """NATS publish failure should not raise — memory is still written locally."""
        mock_nats_client.publish.side_effect = Exception("NATS unavailable")
        bus = NatsMemoryBus(
            nats_client=mock_nats_client,
            subject_prefix="test.memory",
            session_id="worker-1",
        )
        # Should not raise
        event_id = await bus.publish_remember(content="Test")
        assert event_id is not None


class TestNatsMemoryListener:
    """Tests for the NatsMemoryListener subscriber."""

    @pytest.fixture
    def mock_memory_manager(self):
        mgr = AsyncMock()
        mgr.remember = AsyncMock()
        return mgr

    @pytest.mark.asyncio
    async def test_handle_remember_event(self, mock_memory_manager):
        listener = NatsMemoryListener(
            nats_client=AsyncMock(),
            memory_manager=mock_memory_manager,
            subject_prefix="test.memory",
            session_id="local-session",
        )
        event = MemoryEvent(
            operation=MemoryOperation.REMEMBER,
            session_id="remote-session",
            payload={
                "content": "Remote memory content",
                "type": "observation",
                "description": "Remote desc",
                "confidence": 0.8,
                "entities": ["entity1"],
            },
        )
        msg = MagicMock()
        msg.data = event.to_json().encode()
        await listener._handle_message(msg)
        mock_memory_manager.remember.assert_called_once()
        call_kwargs = mock_memory_manager.remember.call_args
        assert "Remote memory content" in call_kwargs.kwargs.get("content", call_kwargs[1].get("content", ""))

    @pytest.mark.asyncio
    async def test_skip_own_events(self, mock_memory_manager):
        listener = NatsMemoryListener(
            nats_client=AsyncMock(),
            memory_manager=mock_memory_manager,
            subject_prefix="test.memory",
            session_id="my-session",
        )
        event = MemoryEvent(
            operation=MemoryOperation.REMEMBER,
            session_id="my-session",  # Same as listener's session
            payload={"content": "My own memory"},
        )
        msg = MagicMock()
        msg.data = event.to_json().encode()
        await listener._handle_message(msg)
        mock_memory_manager.remember.assert_not_called()

    @pytest.mark.asyncio
    async def test_deduplication(self, mock_memory_manager):
        listener = NatsMemoryListener(
            nats_client=AsyncMock(),
            memory_manager=mock_memory_manager,
            subject_prefix="test.memory",
            session_id="local-session",
        )
        event = MemoryEvent(
            event_id="same-id",
            operation=MemoryOperation.REMEMBER,
            session_id="remote-session",
            payload={"content": "Test"},
        )
        msg = MagicMock()
        msg.data = event.to_json().encode()
        # Send same event twice
        await listener._handle_message(msg)
        await listener._handle_message(msg)
        # Should only be processed once
        assert mock_memory_manager.remember.call_count == 1

    @pytest.mark.asyncio
    async def test_handle_delete_is_noop(self, mock_memory_manager):
        listener = NatsMemoryListener(
            nats_client=AsyncMock(),
            memory_manager=mock_memory_manager,
            subject_prefix="test.memory",
            session_id="local-session",
        )
        event = MemoryEvent(
            operation=MemoryOperation.DELETE,
            session_id="remote-session",
            payload={"memory_path": "bank/obs-001.md"},
        )
        msg = MagicMock()
        msg.data = event.to_json().encode()
        await listener._handle_message(msg)
        mock_memory_manager.remember.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_stop(self, mock_memory_manager):
        mock_client = AsyncMock()
        mock_client.subscribe = AsyncMock(return_value=MagicMock())
        listener = NatsMemoryListener(
            nats_client=mock_client,
            memory_manager=mock_memory_manager,
            subject_prefix="test.memory",
            session_id="local-session",
        )
        await listener.start()
        mock_client.subscribe.assert_called_once()
        await listener.stop()


class TestHybridMemoryManagerNatsIntegration:
    """Tests for NATS integration in HybridMemoryManager."""

    @pytest.mark.asyncio
    async def test_remember_publishes_to_nats(self):
        """When NATS bus is set, remember() should publish to NATS."""
        from nexusagent.memory.hybrid_memory import HybridMemoryManager

        tmp = tempfile.mkdtemp()
        mgr = HybridMemoryManager(tmp)
        mgr.initialize()  # Creates bank/ directory

        mock_bus = AsyncMock()
        mock_bus.publish_remember = AsyncMock(return_value="event-123")
        mgr.set_nats_memory_bus(mock_bus)

        await mgr.remember(
            content="Test memory",
            type="observation",
            description="Test",
        )
        mock_bus.publish_remember.assert_called_once()
        call_kwargs = mock_bus.publish_remember.call_args
        assert call_kwargs.kwargs.get("content", call_kwargs[1].get("content")) == "Test memory"

    @pytest.mark.asyncio
    async def test_remember_without_nats_works(self):
        """When no NATS bus is set, remember() should work normally."""
        from nexusagent.memory.hybrid_memory import HybridMemoryManager

        tmp = tempfile.mkdtemp()
        mgr = HybridMemoryManager(tmp)
        mgr.initialize()
        # No NATS bus set
        filepath = await mgr.remember(
            content="Test memory",
            type="observation",
            description="Test",
        )
        assert Path(filepath).exists()

    @pytest.mark.asyncio
    async def test_nats_publish_failure_doesnt_break_remember(self):
        """NATS publish failure should not prevent local memory write."""
        from nexusagent.memory.hybrid_memory import HybridMemoryManager

        tmp = tempfile.mkdtemp()
        mgr = HybridMemoryManager(tmp)
        mgr.initialize()

        mock_bus = AsyncMock()
        mock_bus.publish_remember = AsyncMock(side_effect=Exception("NATS down"))
        mgr.set_nats_memory_bus(mock_bus)

        filepath = await mgr.remember(
            content="Test memory",
            type="observation",
            description="Test",
        )
        assert Path(filepath).exists()
