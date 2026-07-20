# src/nexusagent/infrastructure/events/event_store.py
"""Append-only Event Store with query and replay capabilities."""

import asyncio
import logging

from sqlalchemy import and_, select

from nexusagent.core.events.base import SystemEvent
from nexusagent.infrastructure.db import get_db_manager
from nexusagent.infrastructure.db.models import EventModel

logger = logging.getLogger(__name__)


class EventStore:
    """Append-only store for system events.

    Persists events to the SQLite database.
    """

    def __init__(self, db_manager=None) -> None:
        """Initialize with an optional DatabaseManager override."""
        self._db_manager = db_manager
        self._initialized = False
        self._init_lock = asyncio.Lock()

    @property
    def db_manager(self):
        """Lazy loader for database manager singleton."""
        if self._db_manager is None:
            self._db_manager = get_db_manager()
        return self._db_manager

    async def append(self, event: SystemEvent) -> None:
        """Append a system event to the SQLite database log."""
        # Ensure DB is initialized before first write to avoid "no such table" errors in tests
        if not self._initialized:
            async with self._init_lock:
                if not self._initialized:
                    try:
                        await self.db_manager.init_db()
                    except Exception as e:
                        logger.warning(f"Lazy db init failed in EventStore: {e}")
                    self._initialized = True

        try:
            async with self.db_manager.get_session() as session:
                db_event = EventModel(
                    id=event.id,
                    timestamp=event.timestamp,
                    source=event.source,
                    type=event.type,
                    payload_json=event.payload,
                )
                session.add(db_event)
        except Exception as e:
            logger.error(f"Failed to persist event {event.id} to SQLite: {e}", exc_info=True)
            raise

    async def query(
        self,
        since: str | None = None,
        until: str | None = None,
        source: str | None = None,
        type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SystemEvent]:
        """Query events from the store by criteria."""
        async with self.db_manager.get_session() as session:
            stmt = select(EventModel)
            filters = []
            if since:
                filters.append(EventModel.timestamp >= since)
            if until:
                filters.append(EventModel.timestamp <= until)
            if source:
                filters.append(EventModel.source == source)
            if type:
                filters.append(EventModel.type == type)

            if filters:
                stmt = stmt.where(and_(*filters))

            stmt = stmt.order_by(EventModel.timestamp.asc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            events = []
            for row in rows:
                evt = SystemEvent(
                    source=row.source,
                    type=row.type,
                    payload=row.payload_json or {},
                )
                evt.id = row.id
                evt.timestamp = row.timestamp
                events.append(evt)
            return events

    async def replay(self, from_id: str | None = None) -> list[SystemEvent]:
        """Replay events starting after from_id."""
        async with self.db_manager.get_session() as session:
            if from_id:
                result = await session.execute(select(EventModel).where(EventModel.id == from_id))
                row = result.scalar_one_or_none()
                if row:
                    stmt = (
                        select(EventModel)
                        .where(EventModel.timestamp > row.timestamp)
                        .order_by(EventModel.timestamp.asc())
                    )
                else:
                    stmt = select(EventModel).order_by(EventModel.timestamp.asc())
            else:
                stmt = select(EventModel).order_by(EventModel.timestamp.asc())

            result = await session.execute(stmt)
            rows = result.scalars().all()

            events = []
            for row in rows:
                evt = SystemEvent(
                    source=row.source,
                    type=row.type,
                    payload=row.payload_json or {},
                )
                evt.id = row.id
                evt.timestamp = row.timestamp
                events.append(evt)
            return events


_event_store: EventStore | None = None


def get_event_store() -> EventStore:
    """Get the global EventStore singleton."""
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
    return _event_store


def set_event_store(store: EventStore) -> None:
    """Override the global EventStore singleton (e.g. for testing)."""
    global _event_store
    _event_store = store
