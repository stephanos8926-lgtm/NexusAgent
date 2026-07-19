"""Managed adapter for Session with lifecycle support.

ManagedSession wraps an existing Session instance with observable lifecycle.
RuntimeSessionManager wraps SessionManager with the same pattern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from nexusagent.runtime.context import RuntimeContext
from nexusagent.runtime.lifecycle import (
    HealthStatus,
    LifecycleMixin,
    LifecycleState,
)

logger = logging.getLogger("nexusagent.runtime.session")


@dataclass
class SessionMetadata:
    """Metadata for a managed session."""

    session_id: str
    created_at: float = 0.0
    label: str = ""
    tags: list[str] = field(default_factory=list)


class ManagedSession(LifecycleMixin):
    """Wraps a Session instance with observable lifecycle.

    Manages the policy_context lifecycle:
      - Sets RuntimeContext.policy_context on initialize()
      - Clears it on shutdown()
    """

    def __init__(
        self,
        session: Any,
        context: RuntimeContext | None = None,
        metadata: SessionMetadata | None = None,
    ) -> None:
        self._session = session
        self._context = context
        self._metadata = metadata or SessionMetadata(session_id=session.session_id)
        self._state = LifecycleState.CREATED

    # --- LifecycleMixin ---

    @property
    def state(self) -> LifecycleState:
        return self._state

    @property
    def session(self) -> Any:
        """Access to the underlying Session."""
        return self._session

    @property
    def session_id(self) -> str:
        return self._session.session_id

    async def initialize(self) -> None:
        """Initialize the session. Sets policy_context if available."""
        self._state = LifecycleState.INITIALIZING

        # Session-scoped policy context
        if self._context is not None and hasattr(self._session, "policy"):
            self._context.policy_context = self._session.policy

        self._state = LifecycleState.RUNNING
        logger.debug("ManagedSession %s initialized.", self.session_id)

    async def shutdown(self) -> None:
        """Shutdown the session. Clears policy_context."""
        # Clear session-scoped policy
        if self._context is not None:
            self._context.policy_context = None

        try:
            await self._session.close()
        except Exception as e:
            logger.warning("Session %s close error: %s", self.session_id, e)

        self._state = LifecycleState.TERMINATED

    def health(self) -> HealthStatus:
        return HealthStatus(
            healthy=self._state == LifecycleState.RUNNING,
            details={
                "session_id": self.session_id,
                "state": self._state.value,
                "session_status": getattr(self._session, "status", "unknown"),
            },
        )

    # --- Delegated API ---

    async def send(self, user_message: str, images: list[str] | None = None) -> None:
        """Process a user message. Delegates to session.send().

        Additionally sets current_session_id on RuntimeContext when active.
        """
        if self._context is not None:
            self._context.current_session_id = self.session_id
        await self._session.send(user_message, images=images)

    async def close(self) -> None:
        """Close the underlying session."""
        await self._session.close()

    def event_stream(self):
        """Stream session events. Delegates to underlying stream."""
        return self._session.event_stream()


class RuntimeSessionManager(LifecycleMixin):
    """Manages multiple ManagedSessions with Runtime context.

    Wraps the existing SessionManager with lifecycle and RuntimeContext integration.
    """

    def __init__(
        self,
        context: RuntimeContext | None = None,
    ) -> None:
        self._context = context
        self._state = LifecycleState.CREATED
        self._sessions: dict[str, ManagedSession] = {}

        # Lazy import to avoid circular dependency
        self._inner = None  # SessionManager instance

    @property
    def state(self) -> LifecycleState:
        return self._state

    async def initialize(self) -> None:
        """Initialize the session manager."""
        self._state = LifecycleState.INITIALIZING

        from nexusagent.core.session.manager import get_session_manager

        self._inner = get_session_manager()
        self._state = LifecycleState.RUNNING
        logger.info("RuntimeSessionManager initialized.")

    async def shutdown(self) -> None:
        """Shutdown all managed sessions."""
        for session_id, managed in list(self._sessions.items()):
            try:
                await managed.shutdown()
            except Exception as e:
                logger.warning("Session %s shutdown error: %s", session_id, e)

        self._sessions.clear()
        self._state = LifecycleState.TERMINATED

    def health(self) -> HealthStatus:
        return HealthStatus(
            healthy=self._state == LifecycleState.RUNNING,
            details={
                "state": self._state.value,
                "active_sessions": len(self._sessions),
            },
        )

    async def get_or_create(
        self,
        session_id: str,
        working_dir: str,
        agent: Any,
        db_repo: Any,
        memory_dir: str | None = None,
        **kwargs: Any,
    ) -> ManagedSession:
        """Get an existing session or create a new one.

        Delegates to SessionManager.get_or_create() and wraps result.
        """
        if session_id in self._sessions:
            return self._sessions[session_id]

        if self._inner is None:
            from nexusagent.core.session.manager import get_session_manager

            self._inner = get_session_manager()

        # Create the underlying session via the real manager
        session = await self._inner.get_or_create(
            session_id=session_id,
            working_dir=working_dir,
            agent=agent,
            db_repo=db_repo,
            memory_dir=memory_dir,
            **kwargs,
        )

        managed = ManagedSession(
            session=session,
            context=self._context,
            metadata=SessionMetadata(session_id=session_id),
        )
        await managed.initialize()
        self._sessions[session_id] = managed
        return managed

    def get(self, session_id: str) -> ManagedSession | None:
        """Get a managed session by ID."""
        return self._sessions.get(session_id)

    @property
    def active_count(self) -> int:
        return len(self._sessions)
