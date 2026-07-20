"""Event emitter for publishing system events to NATS.

Provides a centralized way to emit events to NATS subjects with automatic
serialization and error handling.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from typing import Any, Protocol

from nexusagent.core.events.base import SystemEvent
from nexusagent.infrastructure.bus import AgentBus, get_bus

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    """Protocol for event publishing capability."""
    
    async def publish(self, subject: str, message: Any) -> None:
        """Publish a message to a NATS subject."""
        ...


class EventEmitter:
    """Emits system events to NATS subjects.
    
    Provides a simple interface for publishing events with automatic
    JSON serialization and error handling. Supports both sync and async
    emission patterns.
    
    Usage:
        # Async emission (preferred)
        emitter = EventEmitter()
        await emitter.emit(event)
        
        # Sync emission (fire-and-forget)
        emitter.emit_sync(event)
        
        # With custom bus
        emitter = EventEmitter(bus=my_bus)
    """
    
    def __init__(self, bus: EventPublisher | None = None):
        """Initialize the event emitter.
        
        Args:
            bus: Optional EventPublisher (AgentBus) to use. If None,
                 uses the default bus from get_bus().
        """
        self._bus: EventPublisher | None = bus
        self._queue: asyncio.Queue[SystemEvent] | None = None
        self._queue_thread: threading.Thread | None = None
        self._running = False
    
    @property
    def bus(self) -> EventPublisher | None:
        """Get or create the bus instance."""
        if self._bus is None:
            # Use module-level default bus
            from nexusagent.infrastructure.bus import _default_bus
            return _default_bus
        return self._bus
    
    @bus.setter
    def bus(self, value: EventPublisher | None):
        """Set the bus instance."""
        self._bus = value
    
    def _ensure_bus(self) -> EventPublisher:
        """Ensure we have a connected bus, raising if not available."""
        bus = self.bus
        if bus is None:
            raise RuntimeError(
                "No NATS bus available. Call EventEmitter.set_bus() or "
                "ensure AgentBus.connect() has been called."
            )
        return bus
    
    async def emit(self, event: SystemEvent) -> None:
        """Emit an event to NATS asynchronously.
        
        Serializes the event to JSON and publishes to the appropriate
        NATS subject based on the event's category and type.
        
        Args:
            event: The SystemEvent (or subclass) to emit.
            
        Raises:
            RuntimeError: If the bus is not connected.
            Exception: If NATS publish fails.
        """
        bus = self._ensure_bus()
        subject = event.nats_subject
        
        try:
            # Serialize event to dict (handles datetime conversion)
            payload = event.to_dict()
            await bus.publish(subject, payload)
            logger.debug(f"Emitted event {event.id} to {subject}")
        except Exception as e:
            logger.error(f"Failed to emit event {event.id} to {subject}: {e}")
            raise
    
    def emit_sync(self, event: SystemEvent) -> None:
        """Emit an event synchronously (fire-and-forget).
        
        Queues the event for async processing in the background.
        Does not wait for completion or raise on failure.
        
        Args:
            event: The SystemEvent (or subclass) to emit.
        """
        try:
            # Create queue if needed
            if self._queue is None:
                self._queue = asyncio.Queue()
                self._running = True
                self._queue_thread = threading.Thread(
                    target=self._process_queue,
                    daemon=True,
                )
                self._queue_thread.start()
            
            # Put event in queue
            self._queue.put_nowait(event)
        except Exception as e:
            logger.warning(f"Failed to queue event for async emission: {e}")
    
    def _process_queue(self) -> None:
        """Background thread to process queued events."""
        import asyncio
        
        async def _process():
            while self._running:
                try:
                    # Get event with timeout
                    try:
                        event = self._queue.get_nowait()
                    except asyncio.QueueEmpty:
                        await asyncio.sleep(0.1)
                        continue
                    
                    try:
                        await self.emit(event)
                    except Exception as e:
                        logger.warning(f"Async event emission failed: {e}")
                    finally:
                        self._queue.task_done()
                except Exception as e:
                    logger.warning(f"Event queue processing error: {e}")
                    await asyncio.sleep(1.0)
        
        # Run the async processor
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_process())
        except Exception as e:
            logger.error(f"Event queue processor crashed: {e}")
        finally:
            loop.close()
    
    async def close(self) -> None:
        """Close the emitter and cleanup resources."""
        self._running = False
        if self._queue is not None:
            # Drain the queue
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except Exception:
                    pass
        if self._queue_thread is not None:
            self._queue_thread.join(timeout=5.0)
    
    @classmethod
    def get_emitter(cls) -> "EventEmitter":
        """Get the module-level default emitter."""
        global _default_emitter
        if _default_emitter is None:
            _default_emitter = cls()
        return _default_emitter
    
    @classmethod
    def set_emitter(cls, emitter: "EventEmitter") -> None:
        """Set the module-level default emitter."""
        global _default_emitter
        _default_emitter = emitter


# Module-level default emitter
_default_emitter: EventEmitter | None = None


def get_emitter() -> EventEmitter:
    """Get or create the default EventEmitter."""
    return EventEmitter.get_emitter()


def set_emitter(emitter: EventEmitter) -> None:
    """Override the default EventEmitter."""
    EventEmitter.set_emitter(emitter)


async def emit_event(event: SystemEvent) -> None:
    """Convenience function to emit an event using the default emitter."""
    emitter = get_emitter()
    await emitter.emit(event)


def emit_event_sync(event: SystemEvent) -> None:
    """Convenience function to emit an event synchronously."""
    emitter = get_emitter()
    emitter.emit_sync(event)
