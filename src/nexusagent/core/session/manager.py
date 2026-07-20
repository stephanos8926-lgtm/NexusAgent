"""SessionManager — lifecycle manager for Session instances.

Caches active sessions and coordinates creation/idle/closed transitions.
Integrates with Phase 2 Task model for durable task persistence and recovery.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from nexusagent.core.session.session import Session
from nexusagent.core.task import Task, TaskState, TaskStore

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
                await index.close()
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
    Integrates with Phase 2 Task model for durable task persistence and recovery.
    """

    def __init__(self, task_store: TaskStore | None = None) -> None:
        """Initialize an empty session manager.

        Args:
            task_store: Optional TaskStore for durable task persistence.
                       If None, creates a new in-memory TaskStore.
        """
        self._sessions: dict[str, Session] = {}
        self._creating: set[str] = set()
        self._lock = asyncio.Lock()
        self._task_store = task_store or TaskStore()
        self._session_tasks: dict[str, Task] = {}  # session_id -> Task

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

        When creating a new session, also creates or recovers a Task
        via TaskStore for durable persistence and recovery.

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
                    # Create or recover Task for this session
                    task = await self._get_or_create_task(session_id, working_dir, agent)
                    self._session_tasks[session_id] = task

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

                    # Persist task state as ACTIVE
                    await self._persist_task_state(session_id, TaskState.EXECUTING)

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

        # Also persist task state as idle (but keep it EXECUTING for recovery)
        # Task state stays EXECUTING so it can be recovered if needed
        await self._persist_task_state(session_id, TaskState.EXECUTING)

    async def close(self, session_id: str) -> None:
        """Close a session and remove it from the cache."""
        session: Session | None = None
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.close()
            # Mark task as COMPLETED when session closes
            await self._persist_task_state(session_id, TaskState.COMPLETED)

    @property
    def active_count(self) -> int:
        """Number of sessions currently cached."""
        return len(self._sessions)

    async def _get_or_create_task(self, session_id: str, working_dir: str, agent: Any) -> Task:
        """Create a new Task or recover an existing one for this session.

        Uses the session_id as the task_id for direct mapping between sessions and tasks.
        """
        # Try to load existing task
        task = await self._task_store.load_task(session_id)
        if task is not None:
            logger.info("Recovered existing task %s for session %s (state: %s)",
                       task.id, session_id, task.state.value)
            # Try to recover from checkpoint if task was in progress
            if task.state in (TaskState.EXECUTING, TaskState.PLANNING, TaskState.RECOVERING):
                checkpoint = await self._task_store.load_latest_checkpoint(session_id)
                if checkpoint:
                    logger.info("Found checkpoint for task %s at node %s",
                               session_id, checkpoint.current_node)
            return task

        # Create new task for this session
        task = Task(
            id=session_id,
            objective=f"Session {session_id} in {working_dir}",
            owner=agent.__class__.__name__ if agent else "unknown",
            state=TaskState.CREATED,
        )
        await self._task_store.save_task(task)
        logger.info("Created new task %s for session %s", task.id, session_id)
        return task

    async def _persist_task_state(self, session_id: str, state: TaskState) -> None:
        """Persist the task state for a session."""
        task = self._session_tasks.get(session_id)
        if task is None:
            task = await self._task_store.load_task(session_id)
            if task is None:
                logger.warning("No task found for session %s", session_id)
                return
            self._session_tasks[session_id] = task

        try:
            task.transition_to(state)
            await self._task_store.save_task(task)
            logger.debug("Persisted task %s state: %s", session_id, state.value)
        except Exception as exc:
            logger.warning("Failed to persist task state for %s: %s", session_id, exc)

    async def _persist_checkpoint(self, session_id: str, checkpoint) -> None:
        """Persist a checkpoint for the session's task."""
        try:
            await self._task_store.save_checkpoint(session_id, checkpoint)
            logger.debug("Persisted checkpoint for task %s", session_id)
        except Exception as exc:
            logger.warning("Failed to persist checkpoint for %s: %s", session_id, exc)

    async def recover_session(self, session_id: str, working_dir: str, agent: Any,
                              db_repo=None, memory_dir: str | None = None,
                              parent_memory_dir: str | None = None) -> Session | None:
        """Recover a session from its persisted task and checkpoint.

        This method can be called on startup to restore a previous session
        from its last checkpoint.

        Returns:
            Recovered Session instance, or None if no task exists.
        """
        task = await self._task_store.load_task(session_id)
        if task is None:
            logger.info("No task found for session %s, cannot recover", session_id)
            return None

        if task.state == TaskState.COMPLETED:
            logger.info("Task %s already completed, not recovering", session_id)
            return None

        checkpoint = task.latest_checkpoint
        if checkpoint:
            logger.info("Recovering session %s from checkpoint at node %s",
                       session_id, checkpoint.current_node)
        else:
            logger.info("Recovering session %s from start (no checkpoint)", session_id)

        # Recover the task state to RECOVERING
        try:
            task.transition_to(TaskState.RECOVERING)
            await self._task_store.save_task(task)
        except Exception as exc:
            logger.warning("Failed to transition task %s to RECOVERING: %s", session_id, exc)

        # Create the session with the recovered task
        injected_memories: list[str] | None = None
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
            logger.debug("Cross-session memory discovery failed during recovery: %s", exc)

        session = Session(
            session_id=session_id,
            working_dir=working_dir,
            agent=agent,
            db_repo=db_repo,
            memory_dir=memory_dir,
            injected_memories=injected_memories,
            parent_memory_dir=parent_memory_dir,
        )

        # Attach the recovered task
        self._session_tasks[session_id] = task
        self._sessions[session_id] = session

        # Update task state to EXECUTING
        await self._persist_task_state(session_id, TaskState.EXECUTING)

        return session

    async def get_task(self, session_id: str) -> Task | None:
        """Get the task associated with a session."""
        if session_id in self._session_tasks:
            return self._session_tasks[session_id]
        return await self._task_store.load_task(session_id)

    async def save_checkpoint(self, session_id: str, checkpoint) -> None:
        """Save a checkpoint for the session's task."""
        await self._persist_checkpoint(session_id, checkpoint)


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