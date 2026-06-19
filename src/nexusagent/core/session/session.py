"""Session — a single interactive conversation between user and agent.

Manages message flow, event streaming, approval gates, cancellation,
and real-time token streaming via LangGraph's astream().
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from nexusagent.core.session.helpers import (
    _build_environment_context,
    _build_session_history_context,
)
from nexusagent.hooks import HookEvent, get_hook_manager
from nexusagent.infrastructure.config import settings
from nexusagent.infrastructure.prompt_loader import inject_file_at_reference, load_nexus_prompt
from nexusagent.llm.models import ErrorEvent, ResponseEvent, ThinkingEvent
from nexusagent.memory.compaction import CompactionPipeline, pre_compaction_flush
from nexusagent.memory.extraction import MemoryExtractor
from nexusagent.memory.memory import HybridMemoryManager

logger = logging.getLogger(__name__)

_MAX_EXTRACTION_QUEUE = 3


class Session:
    """A single interactive session between a user and the agent.

    Manages message flow, event streaming, approval gates, and cancellation.
    """

    def __init__(
        self,
        session_id: str,
        working_dir: str,
        agent: Any,
        db_repo: Any,
        memory_dir: str | Path | None = None,
        injected_memories: list[str] | None = None,
    ) -> None:
        """Initialize a new interactive session.

        Args:
            session_id: Unique identifier for this session.
            working_dir: Absolute path to the project working directory.
            agent: The agent instance used to process user messages.
            db_repo: Database repository for persisting session and message data.
            memory_dir: Optional override for the hybrid memory directory path.
                Defaults to ``~/.nexusagent/sessions/{session_id}/memory``.
            injected_memories: Optional list of memory context strings from
                previous sessions in the same workspace, to be injected as
                SystemMessages during agent calls.
        """
        self.session_id = session_id
        self.working_dir = working_dir
        self.agent = agent
        self.db_repo = db_repo

        if memory_dir is None:
            memory_dir = os.path.expanduser(f"~/.nexusagent/sessions/{session_id}/memory")
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.hybrid_memory = HybridMemoryManager(str(self.memory_dir))
        self.hybrid_memory.initialize()

        self.injected_memories: list[str] = injected_memories or []

        self.status: str = "active"
        self._cancel_flag: bool = False
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}
        self._seen_tool_results: set[str] = set()
        self._seen_tool_calls: set[str] = set()
        self._conversation_history: list[Any] = []
        self._extractor = MemoryExtractor()
        self._extraction_queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_EXTRACTION_QUEUE)

    # ── Prompt & Context ─────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        """Load the full system prompt from NEXUS.md files."""
        if hasattr(self, "_cached_prompt"):
            return self._cached_prompt

        package_root = Path(__file__).parent.parent.parent
        prompt = load_nexus_prompt(
            package_root=package_root,
            cwd=Path(self.working_dir),
            max_depth=settings.prompt.max_chain_depth,
        )
        self._cached_prompt = prompt
        logger.debug("Loaded system prompt (%d chars) for session %s", len(prompt), self.session_id)
        return prompt

    def _build_context_injection(self) -> str:
        """Build the environment + session history context block."""
        parts = [_build_environment_context(self.working_dir)]
        history_ctx = _build_session_history_context(self.working_dir)
        if history_ctx:
            parts.append(f"\n## Recent Session History\n{history_ctx}")
        return "\n".join(parts)

    # ── Send a user message ────────────────────────────────────────────

    def _process_chat_input(self, user_message: str) -> str:
        """Process chat input: handle @file injection if enabled."""
        if not settings.prompt.chat_file_injection:
            return user_message

        has_at_ref = False
        for line in user_message.split("\n"):
            stripped = line.strip()
            if stripped.startswith("@") and len(stripped) > 1 and stripped[1] != " ":
                has_at_ref = True
                break

        if not has_at_ref:
            return user_message

        try:
            injected = inject_file_at_reference(
                user_message,
                cwd=Path(self.working_dir),
                max_depth=settings.prompt.max_chain_depth,
            )
            logger.debug("Chat @file injection: %d -> %d chars", len(user_message), len(injected))
            return injected
        except Exception as e:
            logger.warning("Chat @file injection failed: %s", e)
            return user_message

    def _build_user_message(self, user_message: str, images: list[str] | None = None):
        """Build a HumanMessage, optionally with image attachments."""
        from nexusagent.llm.models import encode_image_to_content

        if not images:
            return HumanMessage(content=user_message)

        content_blocks: list[dict] = [{"type": "text", "text": user_message}]
        for img_path in images:
            try:
                image_content = encode_image_to_content(img_path)
                content_blocks.append(image_content)
            except Exception as exc:
                logger.warning("Failed to encode image '%s': %s", img_path, exc)
                content_blocks.append({
                    "type": "text",
                    "text": f"[Image could not be loaded: {img_path}]",
                })

        return HumanMessage(content=content_blocks)

    async def send(self, user_message: str, images: list[str] | None = None) -> None:
        """Process a user message: store in DB, recall memory, stream agent response.

        Uses LangGraph's astream() with stream_mode="messages" for real-time
        streaming of tool calls, tool results, and tokens.
        """
        if self.status != "active":
            self._enqueue(ErrorEvent(message="Session is not active").model_dump())
            return

        if settings.hooks.hooks_enabled:
            try:
                await get_hook_manager().run_hooks(HookEvent.SESSION_INIT, {
                    "session_id": self.session_id,
                    "working_dir": self.working_dir,
                    "config": settings,
                })
            except Exception as exc:
                logger.warning("session_init hook failed: %s", exc)

        user_message = self._process_chat_input(user_message)
        self._enqueue(ThinkingEvent(content="Processing...").model_dump())

        try:
            await self.db_repo.add_message(self.session_id, "user", user_message)
        except Exception as exc:
            logger.warning("Failed to store user message in DB: %s", exc)

        # Build messages list
        system_prompt = self._load_system_prompt()
        context_block = self._build_context_injection()
        if context_block:
            system_prompt = system_prompt + "\n\n" + context_block
        messages = [SystemMessage(content=system_prompt)]

        # Inject cross-session memories from previous sessions in same workspace
        if self.injected_memories:
            cross_session_ctx = (
                "[Previous Session Context]\n"
                + "\n---\n".join(self.injected_memories)
                + "\n[/Previous Session Context]"
            )
            messages.append(SystemMessage(content=cross_session_ctx))

        try:
            hybrid_context = await self.hybrid_memory.get_memory_context(user_message, max_results=5)
            if hybrid_context:
                messages.append(SystemMessage(content=hybrid_context))
        except Exception as exc:
            logger.warning("Hybrid memory context retrieval failed: %s", exc)

        messages.extend(self._conversation_history[-settings.agent.max_conversation_history:])
        user_msg = self._build_user_message(user_message, images)
        messages.append(user_msg)

        # Compaction
        _compaction = CompactionPipeline()
        if settings.agent.compaction_enabled and _compaction.should_compact(
            [{"role": "system" if isinstance(m, SystemMessage) else "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content} for m in messages]
        ):
            summary = f"Session {self.session_id} turn: {user_message[:100]}"
            try:
                flush_ctx = await pre_compaction_flush(self, summary)
                messages.insert(1, SystemMessage(content=flush_ctx))
            except Exception as exc:
                logger.warning("Pre-compaction flush failed: %s", exc)
            msg_dicts = [{"role": "system" if isinstance(m, SystemMessage) else "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content} for m in messages]
            compacted = _compaction.compact(msg_dicts)
            messages = []
            for md in compacted:
                if md["role"] == "system":
                    messages.append(SystemMessage(content=md["content"]))
                elif md["role"] == "user":
                    messages.append(HumanMessage(content=md["content"]))
                else:
                    messages.append(AIMessage(content=md["content"]))

        # Invoke the agent via astream for real-time token streaming
        self._cancel_flag = False
        accumulated: list[str] = []
        try:
            async for chunk in self.agent.astream(
                {"messages": messages},
                stream_mode="messages",
            ):
                if self._cancel_flag:
                    break
                if isinstance(chunk, tuple):
                    token, metadata = chunk
                    await self._handle_message_token(token, metadata, accumulated)
                else:
                    await self._handle_message_token(chunk, {}, accumulated)

            if self._cancel_flag:
                self._enqueue(ErrorEvent(message="Session interrupted").model_dump())
            else:
                final_content = "".join(accumulated)
                self._enqueue(ResponseEvent(content=final_content).model_dump())

                self._conversation_history.append(user_msg)
                self._conversation_history.append(AIMessage(content=final_content))
                max_hist = settings.agent.max_conversation_history
                if len(self._conversation_history) > max_hist:
                    self._conversation_history = self._conversation_history[-max_hist:]

                try:
                    await self.db_repo.add_message(self.session_id, "assistant", final_content)
                except Exception as exc:
                    logger.warning("Failed to store assistant message in DB: %s", exc)

                # Fire-and-forget auto extraction (non-blocking)
                self._schedule_extraction(user_msg, final_content)

        except Exception as exc:
            logger.error("Agent invocation failed: %s", exc, exc_info=True)
            if settings.hooks.hooks_enabled:
                try:
                    await get_hook_manager().run_hooks(HookEvent.ERROR, {
                        "session_id": self.session_id,
                        "error_message": str(exc),
                        "working_dir": self.working_dir,
                    })
                except Exception as hook_exc:
                    logger.warning("error hook failed: %s", hook_exc)
            self._enqueue(ErrorEvent(message=str(exc)).model_dump())

    async def _handle_message_token(self, token, metadata: dict, accumulated: list[str]) -> None:
        """Process a single message token from the stream."""
        from langchain_core.messages import AIMessageChunk, ToolMessage

        if isinstance(token, AIMessageChunk) and token.tool_call_chunks:
            for tc in token.tool_call_chunks:
                call_id = tc.get("id", "")
                if tc.get("name") and call_id and call_id not in self._seen_tool_calls:
                    self._seen_tool_calls.add(call_id)
                    self._enqueue({
                        "type": "tool_call",
                        "tool": tc["name"],
                        "args": tc.get("args", {}),
                        "call_id": call_id,
                    })

        if isinstance(token, ToolMessage):
            call_id = getattr(token, "tool_call_id", "")
            if call_id and call_id not in self._seen_tool_results:
                self._seen_tool_results.add(call_id)
                self._enqueue({
                    "type": "tool_result",
                    "call_id": call_id,
                    "output": str(token.content) if token.content else "",
                    "success": True,
                })
                if settings.hooks.hooks_enabled:
                    try:
                        await get_hook_manager().run_hooks(HookEvent.POST_TOOL_USE, {
                            "session_id": self.session_id,
                            "tool_name": getattr(token, "name", "unknown"),
                            "tool_args": {},
                            "tool_result": str(token.content)[:400] if token.content else "",
                            "call_id": call_id,
                        })
                    except Exception as exc:
                        logger.warning("post_tool_use hook failed: %s", exc)

        if isinstance(token, AIMessageChunk) and token.content and not token.tool_call_chunks:
            chunk_text = ""
            if isinstance(token.content, str):
                chunk_text = token.content
                accumulated.append(chunk_text)
            elif isinstance(token.content, list):
                for block in token.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        chunk_text += text
                        accumulated.append(text)
            if chunk_text:
                self._enqueue({
                    "type": "response_chunk",
                    "content": chunk_text,
                })

    # ── Pre-compaction flush ───────────────────────────────────────────

    async def pre_compaction_flush(self) -> str:
        """Flush session state to daily log before context compaction."""
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
        """Close the session: update status, persist to DB, and clean up memory."""
        self.status = "closed"
        try:
            await self.db_repo.update_status(self.session_id, "closed")
        except Exception as exc:
            logger.warning("Failed to update session status in DB: %s", exc)
        self.hybrid_memory.close()
        self._enqueue({"type": "session_closed"})

    # ── Event stream ───────────────────────────────────────────────────

    async def event_stream(self):
        """Yield events from the internal queue as an async generator."""
        while True:
            event = await self._event_queue.get()
            yield event
            if event.get("type") == "session_closed":
                break

    # ── Internal helpers ───────────────────────────────────────────────

    def _schedule_extraction(self, user_message: str, response: str) -> None:
        """Schedule fire-and-forget memory extraction from a turn.

        Uses a bounded queue (max 3 pending). If the queue is full,
        drops the oldest extraction to prevent unbounded growth.
        """
        # Drop oldest if at capacity
        if self._extraction_queue.full():
            try:
                self._extraction_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        combined = f"User: {user_message}\nAssistant: {response}"
        task = asyncio.create_task(self._run_extraction(combined))
        task.add_done_callback(self._on_extraction_done)
        try:
            self._extraction_queue.put_nowait(task)
        except asyncio.QueueFull:
            # Extremely unlikely (we just made room), but handle gracefully
            task.cancel()

    async def _run_extraction(self, text: str) -> None:
        """Run regex extraction and store results as observation memories."""
        results = self._extractor.extract(text)
        for result in results:
            try:
                await self.hybrid_memory.remember(
                    content=result.content,
                    type=result.type,
                    description=result.description,
                    confidence=result.confidence,
                    entities=result.entities or None,
                )
            except Exception as exc:
                logger.warning("Failed to store extracted memory: %s", exc)

    @staticmethod
    def _on_extraction_done(task: asyncio.Task) -> None:
        """Log errors from background extraction tasks (never swallow silently)."""
        exc = task.exception()
        if exc is not None:
            logger.warning("Auto-extraction task failed: %s", exc)

    def _enqueue(self, event: dict[str, Any]) -> None:
        """Put an event dict onto the internal queue (non-blocking).

        If the queue is full (consumer is slow), drop the oldest event
        to prevent memory growth and potential deadlock.
        """
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event to make room (prevents deadlock on slow consumers)
            try:
                self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event queue full — dropping event for session %s", self.session_id)
