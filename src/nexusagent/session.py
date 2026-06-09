"""Session manager for interactive WebSocket sessions.

Provides Session (a single conversation) and SessionManager (lifecycle/cache).
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage

from nexusagent.models import ErrorEvent, ResponseEvent

logger = logging.getLogger(__name__)


class Session:
    """A single interactive session between a user and the agent.

    Manages message flow, event streaming, approval gates, and cancellation.
    """

    def __init__(
        self,
        session_id: str,
        working_dir: str,
        agent: Any,
        memory: Any,
        db_repo: Any,
        memory_dir: str | Path | None = None,
    ) -> None:
        self.session_id = session_id
        self.working_dir = working_dir
        self.agent = agent
        self.memory = memory
        self.db_repo = db_repo

        # Hybrid memory directory — defaults to ~/.nexusagent/sessions/{session_id}/memory
        if memory_dir is None:
            memory_dir = os.path.expanduser(f"~/.nexusagent/sessions/{session_id}/memory")
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Hybrid memory manager (file + index)
        from nexusagent.memory import HybridMemoryManager

        self.hybrid_memory = HybridMemoryManager(str(self.memory_dir))
        self.hybrid_memory.initialize()

        self.status: str = "active"
        self._cancel_flag: bool = False
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}

    # ── Send a user message ────────────────────────────────────────────

    def _base_system_prompt(self) -> str:
        """Return the default system prompt for this session."""
        return "You are a helpful AI assistant."

    async def send(self, user_message: str) -> None:
        """Process a user message: store in DB, recall memory, invoke agent, emit events."""
        if self.status != "active":
            self._enqueue(ErrorEvent(message="Session is not active").model_dump())
            return

        # Store user message in DB
        try:
            await self.db_repo.add_message(self.session_id, "user", user_message)
        except Exception as exc:
            logger.warning("Failed to store user message in DB: %s", exc)

        # Build messages list with memory context injected as SystemMessage
        from langchain_core.messages import HumanMessage

        system_prompt = self._base_system_prompt()
        messages = [SystemMessage(content=system_prompt)]

        try:
            hybrid_context = self.hybrid_memory.get_memory_context(user_message, max_results=5)
            if hybrid_context:
                messages.append(SystemMessage(content=hybrid_context))
        except Exception as exc:
            logger.warning("Hybrid memory context retrieval failed: %s", exc)

        messages.append(HumanMessage(content=user_message))

        # Compaction: if messages exceed context window, compact before model call
        from nexusagent.compaction import CompactionPipeline, pre_compaction_flush

        _compaction = CompactionPipeline()
        if _compaction.should_compact([{"role": "system", "content": m.content} for m in messages]):
            # Pre-compaction flush to memory
            summary = f"Session {self.session_id} turn: {user_message[:100]}"
            try:
                flush_ctx = await pre_compaction_flush(self, summary)
                messages.insert(1, SystemMessage(content=flush_ctx))
            except Exception as exc:
                logger.warning("Pre-compaction flush failed: %s", exc)
            # Compact messages
            msg_dicts = [{"role": "system" if isinstance(m, SystemMessage) else "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content} for m in messages]
            compacted = _compaction.compact(msg_dicts)
            # Rebuild messages list from compacted dicts
            messages = []
            for md in compacted:
                if md["role"] == "system":
                    messages.append(SystemMessage(content=md["content"]))
                elif md["role"] == "user":
                    messages.append(HumanMessage(content=md["content"]))
                else:
                    messages.append(HumanMessage(content=md["content"]))  # fallback

        # Invoke agent with proper messages format
        self._cancel_flag = False
        try:
            result = self.agent({"messages": messages})
            # If the agent returns an async generator, stream events
            if hasattr(result, "__aiter__"):
                async for event in result:
                    if self._cancel_flag:
                        self._enqueue(ErrorEvent(message="Session interrupted").model_dump())
                        break
                    self._enqueue(event if isinstance(event, dict) else event.model_dump())
            else:
                # Synchronous result — emit as ResponseEvent
                content = result if isinstance(result, str) else str(result)
                self._enqueue(ResponseEvent(content=content).model_dump())

                # Store assistant response in DB
                try:
                    await self.db_repo.add_message(self.session_id, "assistant", content)
                except Exception as exc:
                    logger.warning("Failed to store assistant message in DB: %s", exc)

                # Remember in memory
                try:
                    if self.memory is not None:
                        await self.memory.remember(
                            user_message,
                            metadata={"response": content},
                        )
                except Exception as exc:
                    logger.warning("Failed to remember in memory: %s", exc)

        except Exception as exc:
            logger.error("Agent invocation failed: %s", exc)
            self._enqueue(ErrorEvent(message=str(exc)).model_dump())

    # ── Pre-compaction flush ───────────────────────────────────────────

    async def pre_compaction_flush(self) -> str:
        """Flush session state to daily log before context compaction.

        Returns a summary string to be used as context after compaction.
        """
        summary = f"Session {self.session_id} compaction flush at {asyncio.get_event_loop().time()}"
        try:
            await self.hybrid_memory.flush(summary)
        except Exception as exc:
            logger.warning("Pre-compaction flush failed: %s", exc)
        return summary

    # ── Approval gate ──────────────────────────────────────────────────

    async def approve(self, call_id: str, approved: bool) -> None:
        """Record an approval decision for a pending tool call."""
        self._approval_results[call_id] = approved
        gate = self._pending_approvals.get(call_id)
        if gate is not None:
            gate.set()

    def _wait_for_approval(self, call_id: str) -> asyncio.Event:
        """Create (or return existing) approval gate for a tool call."""
        if call_id not in self._pending_approvals:
            self._pending_approvals[call_id] = asyncio.Event()
        return self._pending_approvals[call_id]

    # ── Interrupt / Cancel ─────────────────────────────────────────────

    def interrupt(self) -> None:
        """Request cancellation of the current agent invocation."""
        self._cancel_flag = True

    # ── Close ──────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the session: update status and persist to DB."""
        self.status = "closed"
        try:
            await self.db_repo.update_status(self.session_id, "closed")
        except Exception as exc:
            logger.warning("Failed to update session status in DB: %s", exc)
        # Signal end of stream
        self._enqueue({"type": "session_closed"})

    # ── Event stream ───────────────────────────────────────────────────

    async def event_stream(self) -> AsyncGenerator[dict[str, Any]]:
        """Yield events from the internal queue as an async generator."""
        while True:
            event = await self._event_queue.get()
            yield event
            if event.get("type") == "session_closed":
                break

    # ── Internal helpers ───────────────────────────────────────────────

    def _enqueue(self, event: dict[str, Any]) -> None:
        """Put an event dict onto the internal queue (non-blocking)."""
        self._event_queue.put_nowait(event)


class SessionManager:
    """Lifecycle manager for Session instances.

    Caches active sessions and coordinates creation/idle/closed transitions.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    def get(
        self,
        session_id: str,
    ) -> Session | None:
        """Return a cached session by ID, or None."""
        return self._sessions.get(session_id)

    async def get_or_create(
        self,
        session_id: str,
        working_dir: str = ".",
        agent: Any = None,
        memory: Any = None,
        db_repo: Any = None,
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

            # Build the memory directory path for this session
            memory_dir = os.path.expanduser(f"~/.nexusagent/sessions/{session_id}/memory")
            os.makedirs(memory_dir, exist_ok=True)

            session = Session(
                session_id=session_id,
                working_dir=working_dir,
                agent=agent,
                memory=memory,
                db_repo=db_repo,
                memory_dir=memory_dir,
            )
            self._sessions[session_id] = session
            return session

    async def mark_idle(self, session_id: str) -> None:
        """Transition a session to idle status."""
        session = self._sessions.get(session_id)
        if session is not None and session.status == "active":
            session.status = "idle"
            try:
                if session.db_repo is not None:
                    await session.db_repo.update_status(session_id, "idle")
            except Exception as exc:
                logger.warning("Failed to mark session idle in DB: %s", exc)

    async def close(self, session_id: str) -> None:
        """Close a session and remove it from the cache."""
        session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.close()

    @property
    def active_count(self) -> int:
        """Number of sessions currently cached."""
        return len(self._sessions)


# Module-level singleton
session_manager = SessionManager()
