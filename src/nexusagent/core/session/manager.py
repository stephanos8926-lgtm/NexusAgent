"""SessionManager — lifecycle manager for Session instances.

Caches active sessions and coordinates creation/idle/closed transitions.
"""

from __future__ import annotations

import asyncio
import logging

from nexusagent.core.session.session import Session

logger = logging.getLogger(__name__)


class SessionManager:
    """Lifecycle manager for Session instances.

    Caches active sessions and coordinates creation/idle/closed transitions.
    """

    def __init__(self) -> None:
        """Initialize an empty session manager."""
        self._sessions: dict[str, Session] = {}
        self._creating: set[str] = set()
        self._lock = asyncio.Lock()

    def get(self, session_id: str) -> Session | None:
        """Return a cached session by ID, or None."""
        return self._sessions.get(session_id)

    async def get_or_create(
        self,
        session_id: str,
        working_dir: str = ".",
        agent=None,
        db_repo=None,
    ) -> Session:
        """Get existing session or create new one (thread-safe)."""
        # Fast path: no lock needed for read
        existing = self._sessions.get(session_id)
        if existing is not None:
            return existing

        # Slow path: acquire lock to prevent duplicate creation
        async with self._lock:
            # Double-check after acquiring lock
            existing = self._sessions.get(session_id)
            if existing is not None:
                return existing

            if session_id in self._creating:
                pass  # Fall through to wait loop below
            else:
                self._creating.add(session_id)
                try:
                    session = Session(
                        session_id=session_id,
                        working_dir=working_dir,
                        agent=agent,
                        db_repo=db_repo,
                    )
                    # Final double-check
                    existing = self._sessions.get(session_id)
                    if existing is not None:
                        await session.close()
                        return existing
                    self._sessions[session_id] = session
                    return session
                finally:
                    self._creating.discard(session_id)

        # Wait for the other coroutine to finish creating this session
        # Timeout after 30s to prevent deadlock if the creating coroutine is cancelled
        deadline = asyncio.get_running_loop().time() + 30.0
        while session_id in self._creating:
            if asyncio.get_running_loop().time() >= deadline:
                logger.warning(
                    "Timeout waiting for session %s creation — "
                    "proceeding with new session (possible orphaned creation)",
                    session_id,
                )
                break
            await asyncio.sleep(0.05)
            existing = self._sessions.get(session_id)
            if existing is not None:
                return existing

        return await self.get_or_create(
            session_id=session_id,
            working_dir=working_dir,
            agent=agent,
            db_repo=db_repo,
        )

    async def mark_idle(self, session_id: str) -> None:
        """Transition a session to idle status."""
        session: Session | None = None
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is not None and session.status == "active":
                session.status = "idle"
        if session is not None:
            try:
                if session.db_repo is not None:
                    await session.db_repo.update_status(session_id, "idle")
            except Exception as exc:
                logger.warning("Failed to mark session idle in DB: %s", exc)

    async def close(self, session_id: str) -> None:
        """Close a session and remove it from the cache."""
        session: Session | None = None
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.close()

    @property
    def active_count(self) -> int:
        """Number of sessions currently cached."""
        return len(self._sessions)


# Module-level singleton (lazy, injectable)
_session_manager_instance: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get or create the module-level SessionManager singleton."""
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = SessionManager()
    return _session_manager_instance


def set_session_manager(instance: SessionManager) -> None:
    """Override the module-level SessionManager singleton (for testing)."""
    global _session_manager_instance
    _session_manager_instance = instance


# Backward-compatible alias — deprecated, use get_session_manager()
session_manager = get_session_manager()
