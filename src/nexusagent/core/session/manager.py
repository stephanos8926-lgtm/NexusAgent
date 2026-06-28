"""SessionManager — lifecycle manager for Session instances.

Caches active sessions and coordinates creation/idle/closed transitions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from nexusagent.core.session.session import Session

logger = logging.getLogger(__name__)


# ── Cross-session memory cache ──────────────────────────────────────────

# Simple dict cache: {working_dir: (timestamp, [memory_strings])}
# TTL = 5 minutes
_MEMORY_DISCOVERY_CACHE: dict[str, tuple[float, list[str]]] = {}
_MEMORY_DISCOVERY_TTL = 300.0  # 5 minutes


def _get_cached_memories(working_dir: str) -> list[str] | None:
    """Return cached memories for a working dir if not expired."""
    entry = _MEMORY_DISCOVERY_CACHE.get(working_dir)
    if entry is None:
        return None
    ts, memories = entry
    if time.monotonic() - ts > _MEMORY_DISCOVERY_TTL:
        del _MEMORY_DISCOVERY_CACHE[working_dir]
        return None
    return memories


def _set_cached_memories(working_dir: str, memories: list[str]) -> None:
    """Store discovered memories in the cache."""
    _MEMORY_DISCOVERY_CACHE[working_dir] = (time.monotonic(), memories)


async def _discover_cross_session_memories(
    working_dir: str,
    session_id: str,
    db_repo: Any,
) -> list[str]:
    """Search previous sessions' memory indices for relevant memories.

    Finds up to 5 previous sessions for the same workspace, searches each
    session's HybridMemoryIndex, and returns the top-3 memories by score.

    Returns an empty list if no previous sessions or no memories found.
    """
    try:
        prev_sessions = await db_repo.find_sessions_by_working_dir(
            working_dir, exclude=session_id, limit=5
        )
    except Exception as exc:
        logger.warning("Failed to find previous sessions for %s: %s", working_dir, exc)
        return []

    if not prev_sessions:
        return []

    # Search each previous session's memory index in parallel
    async def _search_session(sess_info: dict) -> list[dict]:
        """Search a single previous session's memory index."""
        mem_dir = sess_info.get("memory_dir")
        if not mem_dir:
            return []
        try:
            from nexusagent.memory.memory_index import HybridMemoryIndex

            index = HybridMemoryIndex(mem_dir)
            try:
                results = await asyncio.to_thread(
                    index.search_sync, "recent work and decisions", max_results=6
                )
                return results
            finally:
                index.close()
        except Exception as exc:
            logger.debug(
                "Failed to search memory for session %s: %s",
                sess_info.get("id", "?"),
                exc,
            )
            return []

    # Run searches in parallel across all previous sessions
    all_results_nested = await asyncio.gather(*[_search_session(s) for s in prev_sessions])

    # Flatten and deduplicate by content
    seen_contents: set[str] = set()
    all_results: list[dict] = []
    for result_list in all_results_nested:
        for r in result_list:
            content = r.get("content", "").strip()
            if content and content not in seen_contents:
                seen_contents.add(content)
                all_results.append(r)

    if not all_results:
        return []

    # Rank by score (higher is better), take top 3
    all_results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
    top_results = all_results[:3]

    # Format as context strings
    memories: list[str] = []
    for r in top_results:
        source = r.get("file", "unknown")
        content = r.get("content", "").strip()
        score = r.get("score", 0.0)
        if content:
            memories.append(f"Source: {source} (score: {score:.2f})\n{content}")

    return memories


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
        memory_dir: str | None = None,
        parent_memory_dir: str | None = None,
    ) -> Session:
        """Get existing session or create new one (thread-safe).

        Args:
            session_id: Unique identifier for this session.
            working_dir: Absolute path to the project working directory.
            agent: The agent instance used to process user messages.
            db_repo: Database repository for persisting session data.
            memory_dir: Optional override for the hybrid memory directory path.
                When None, defaults to ``~/.nexusagent/sessions/{session_id}/memory``.
                When set, uses this path directly (for workspace-scoped memory).
            parent_memory_dir: Optional path to a parent workspace whose memory
                index this session should inherit from (cross-agent memory sharing).
        """
        # Fast path: no lock needed for read
        existing = self._sessions.get(session_id)
        if existing is not None:
            return existing

        # Slow path: acquire lock to prevent duplicate creation
        # Initialize injected_memories here so it's available in the recursive call
        injected_memories: list[str] | None = None
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
                    # Discover cross-session memories from previous sessions
                    try:
                        cached = _get_cached_memories(working_dir)
                        if cached is not None:
                            injected_memories = cached
                        elif db_repo is not None:
                            injected_memories = await _discover_cross_session_memories(
                                working_dir, session_id, db_repo
                            )
                            if injected_memories:
                                _set_cached_memories(working_dir, injected_memories)
                    except Exception as exc:
                        logger.debug("Cross-session memory discovery failed: %s", exc)

                    session = Session(
                        session_id=session_id,
                        working_dir=working_dir,
                        agent=agent,
                        db_repo=db_repo,
                        memory_dir=memory_dir,
                        injected_memories=injected_memories,
                        parent_memory_dir=parent_memory_dir,
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
            memory_dir=memory_dir,
            injected_memories=injected_memories,
            parent_memory_dir=parent_memory_dir,
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
