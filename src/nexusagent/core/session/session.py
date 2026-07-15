"""Session — a single interactive conversation between user and agent.

Extends SessionBase (shared memory logic) with:
- Event streaming (WebSocket/TUI)
- Approval gates
- Conversation history
- Hooks integration
- Real-time token streaming via LangGraph's astream()
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from nexusagent.core.agent import _current_session
from nexusagent.core.session.helpers import (
    _build_environment_context,
    _build_session_history_context,
)
from nexusagent.core.session.session_base import SessionBase
from nexusagent.hooks import HookEvent, get_hook_manager
from nexusagent.infrastructure.config import settings
from nexusagent.infrastructure.prompt_loader import inject_file_at_reference, load_nexus_prompt
from nexusagent.llm.models import ErrorEvent, ResponseEvent, ThinkingEvent
from nexusagent.memory.dream import DreamCycle

logger = logging.getLogger(__name__)

_MAX_EXTRACTION_QUEUE = 3


class Session(SessionBase):
    """Interactive session with event streaming, approval gates, and conversation history.

    Extends SessionBase with TUI-specific features:
    - Event queue for WebSocket/TUI streaming
    - Approval gates for tool calls
    - Conversation history management
    - Hooks integration
    - Real-time token streaming

    Args:
        session_id: Unique identifier for this session.
        working_dir: Absolute path to the project working directory.
        agent: The agent instance used to process user messages.
        db_repo: Database repository for persisting session and message data.
        memory_dir: Optional override for the hybrid memory directory.
        injected_memories: Optional list of memory context strings from previous sessions.
        parent_memory_dir: Optional path to a parent workspace whose memory to inherit.
        llm_call: Optional async callable for LLM invocations (extraction).
    """

    def __init__(
        self,
        session_id: str,
        working_dir: str,
        agent: Any,
        db_repo: Any,
        memory_dir: str | Path | None = None,
        injected_memories: list[str] | None = None,
        parent_memory_dir: str | Path | None = None,
        llm_call: Any = None,
    ):
        # Initialize base class (memory, extraction, dream cycle, compaction)
        super().__init__(
            session_id=session_id,
            working_dir=working_dir,
            memory_dir=memory_dir,
            parent_memory_dir=parent_memory_dir,
            llm_call=llm_call,
        )

        # Session-specific attributes
        self.agent = agent
        self.db_repo = db_repo
        self.injected_memories: list[str] = injected_memories or []

        # TUI/Event streaming
        self.status: str = "active"
        self._cancel_flag: bool = False
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}
        self._pending_answers: dict[str, asyncio.Event] = {}
        self._ask_user_answers: dict[str, str] = {}
        self._seen_tool_results: set[str] = set()
        self._seen_tool_calls: set[str] = set()
        self._conversation_history: list[Any] = []
        self._pending_tool_calls: list[dict[str, Any]] = []
        self._pending_tool_messages: list[ToolMessage] = []
        self._extraction_queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_EXTRACTION_QUEUE)
        self._heartbeat_task: asyncio.Task | None = None

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

    # ── Send a user message ─────────────────────────────────────────────

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
                content_blocks.append(
                    {
                        "type": "text",
                        "text": f"[Image could not be loaded: {img_path}]",
                    }
                )

        return HumanMessage(content=content_blocks)

    # ── send() helper methods ────────────────────────────────────────────

    async def _build_messages_list(
        self,
        system_prompt: str,
        user_message: str,
        images: list[str] | None = None,
    ) -> list[Any]:
        """Build the complete message list for agent invocation.

        Assembles system prompt, context injections, cross-session memories,
        hybrid memory context, and conversation history.

        Args:
            system_prompt: Base system prompt from NEXUS.md.
            user_message: User's input message.
            images: Optional list of image paths to attach.

        Returns:
            List of LangChain message objects ready for agent invocation.
        """
        messages = [SystemMessage(content=system_prompt)]

        # Inject cross-session memories
        if self.injected_memories:
            cross_session_ctx = (
                "[Previous Session Context]\n"
                + "\n---\n".join(self.injected_memories)
                + "\n[/Previous Session Context]"
            )
            messages.append(SystemMessage(content=cross_session_ctx))

        # Inject hybrid memory context
        try:
            hybrid_context = await self.hybrid_memory.get_memory_context(user_message, max_results=5)
            if hybrid_context:
                messages.append(SystemMessage(content=hybrid_context))
        except Exception as exc:
            logger.warning("Hybrid memory context retrieval failed: %s", exc)

        # Add conversation history
        max_hist = settings.agent.max_conversation_history
        messages.extend(self._conversation_history[-max_hist:])

        # Add user message
        user_msg = self._build_user_message(user_message, images)
        messages.append(user_msg)

        return messages

    async def _apply_compaction(self, messages: list[Any]) -> list[Any]:
        """Apply compaction to the message list if enabled.

        Flushes memory context before compaction, then compacts
        the message list using graduated strategies.

        Args:
            messages: List of messages to potentially compact.

        Returns:
            Compacted message list (or original if compaction skipped).
        """
        _compaction = self._compaction.__class__()
        if not settings.agent.compaction_enabled:
            return messages

        # Check if compaction should be applied
        msg_dicts = [
            {
                "role": "system"
                if isinstance(m, SystemMessage)
                else "user"
                if isinstance(m, HumanMessage)
                else "assistant",
                "content": m.content,
            }
            for m in messages
        ]

        if not _compaction.should_compact(msg_dicts):
            return messages

        logger.debug("Session %s turn: compaction triggered", self.session_id)

        # Try to flush memory context before compaction
        try:
            flush_ctx = await self.pre_compaction_flush()
            messages.insert(1, SystemMessage(content=flush_ctx))
        except Exception as exc:
            logger.warning("Pre-compaction flush failed: %s", exc)

        # Re-convert to dicts after flush insertion
        msg_dicts = [
            {
                "role": "system"
                if isinstance(m, SystemMessage)
                else "user"
                if isinstance(m, HumanMessage)
                else "assistant",
                "content": m.content,
            }
            for m in messages
        ]

        # Apply compaction
        compacted = _compaction.compact(msg_dicts)

        # Convert back to message objects
        result = []
        for md in compacted:
            if md["role"] == "system":
                result.append(SystemMessage(content=md["content"]))
            elif md["role"] == "user":
                result.append(HumanMessage(content=md["content"]))
            else:
                result.append(AIMessage(content=md["content"]))

        return result

    async def _stream_agent_response(
        self,
        messages: list[Any],
        user_msg: Any,
        accumulated: list[str],
    ) -> bool:
        """Stream agent response via astream() with heartbeat monitoring.

        Emits periodic "still thinking" events during long LLM calls,
        handles token streaming, tool calls, and tool results.

        Args:
            messages: Message list for agent invocation.
            user_msg: The user message object (for history tracking).
            accumulated: List to accumulate response tokens.

        Returns:
            True if response completed successfully, False if cancelled.
        """
        self._cancel_flag = False
        self._pending_tool_calls = []
        self._pending_tool_messages = []

        # Start heartbeat task for long-running LLM calls
        heartbeat_interval = 15.0  # seconds
        last_heartbeat = asyncio.get_event_loop().time()

        async def _heartbeat():
            """Emit periodic thinking events during long LLM calls."""
            while True:
                await asyncio.sleep(heartbeat_interval)
                elapsed = int(asyncio.get_event_loop().time() - last_heartbeat)
                # Only send "still thinking" if we've been waiting > 30s
                if elapsed >= 30:
                    self._enqueue(
                        ThinkingEvent(content=f"Still thinking... ({elapsed}s)").model_dump()
                    )

        self._heartbeat_task = asyncio.create_task(_heartbeat())

        try:
            async for chunk in self.agent.astream(
                {"messages": messages},
                stream_mode="messages",
            ):
                if self._cancel_flag:
                    break
                # Reset heartbeat timer on each chunk
                last_heartbeat = asyncio.get_event_loop().time()
                if isinstance(chunk, tuple):
                    token, metadata = chunk
                    await self._handle_message_token(token, metadata, accumulated)
                else:
                    await self._handle_message_token(chunk, {}, accumulated)

            if self._cancel_flag:
                self._enqueue(ErrorEvent(message="Session interrupted").model_dump())
                return False

            # Response completed successfully
            # Cancel heartbeat before anything else, otherwise it keeps firing
            # "Still thinking..." forever after we're done.
            if self._heartbeat_task is not None and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()

            final_content = "".join(accumulated)
            self._enqueue(ResponseEvent(content=final_content).model_dump())

            # Update conversation history
            self._conversation_history.append(user_msg)
            if self._pending_tool_calls:
                # AIMessage carries the tool_calls so the model can see, on the
                # next turn, that it actually invoked these tools — followed by
                # the matching ToolMessage results (provider APIs require the
                # ToolMessage(s) to immediately follow the AIMessage that made
                # the call, with matching tool_call_id).
                self._conversation_history.append(
                    AIMessage(content=final_content, tool_calls=self._pending_tool_calls)
                )
                self._conversation_history.extend(self._pending_tool_messages)
            else:
                self._conversation_history.append(AIMessage(content=final_content))
            max_hist = settings.agent.max_conversation_history
            if len(self._conversation_history) > max_hist:
                self._conversation_history = self._conversation_history[-max_hist:]

            # Store in DB
            try:
                await self.db_repo.add_message(self.session_id, "assistant", final_content)
            except Exception as exc:
                logger.warning("Failed to store assistant message in DB: %s", exc)

            # Schedule auto-extraction (fire-and-forget)
            self._schedule_extraction(user_msg, final_content)

            # Increment turn count and trigger dream cycle
            self._turn_count += 1
            self._maybe_trigger_dream_cycle()

            return True

        except Exception as exc:
            logger.error("Agent invocation failed: %s", exc, exc_info=True)
            # Cancel heartbeat task on error (prevents zombie tasks)
            if self._heartbeat_task is not None and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            # Preserve a record of this turn in history even on failure —
            # otherwise the user's message AND the fact that something
            # failed disappear entirely, and the agent has no memory of
            # the exchange at all on the next turn.
            self._conversation_history.append(user_msg)
            self._conversation_history.append(
                AIMessage(content=f"[Turn failed with an internal error: {exc}]")
            )
            raise

    async def _handle_send_error(self, exc: Exception) -> None:
        """Handle errors during send() execution.

        Runs error hooks if enabled and enqueues an ErrorEvent.

        Args:
            exc: The exception that occurred.
        """
        if settings.hooks.hooks_enabled:
            try:
                await get_hook_manager().run_hooks(
                    HookEvent.ERROR,
                    {
                        "session_id": self.session_id,
                        "error_message": str(exc),
                        "working_dir": self.working_dir,
                    },
                )
            except Exception as hook_exc:
                logger.warning("error hook failed: %s", hook_exc)
        self._enqueue(ErrorEvent(message=str(exc)).model_dump())

    async def send(self, user_message: str, images: list[str] | None = None) -> None:
        _current_session.set(self)
        """Process a user message: store in DB, recall memory, stream agent response."""
        if self.status != "active":
            # Cancel any zombie heartbeat task from previous run
            if self._heartbeat_task is not None and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            self._enqueue(ErrorEvent(message="Session is not active").model_dump())
            return

        if settings.hooks.hooks_enabled:
            try:
                await get_hook_manager().run_hooks(
                    HookEvent.SESSION_INIT,
                    {
                        "session_id": self.session_id,
                        "working_dir": self.working_dir,
                        "config": settings,
                    },
                )
            except Exception as exc:
                logger.warning("session_init hook failed: %s", exc)

        user_message = self._process_chat_input(user_message)
        self._enqueue(ThinkingEvent(content="Processing...").model_dump())

        try:
            await self.db_repo.add_message(self.session_id, "user", user_message)
        except Exception as exc:
            logger.warning("Failed to store user message in DB: %s", exc)

        # Build system prompt with context
        system_prompt = self._load_system_prompt()
        context_block = self._build_context_injection()
        if context_block:
            system_prompt = system_prompt + "\n\n" + context_block

        # Build messages list (system prompt, memories, history, user message)
        messages = await self._build_messages_list(system_prompt, user_message, images)

        # Apply compaction if enabled
        messages = await self._apply_compaction(messages)

        # Prepare for streaming
        accumulated: list[str] = []
        user_msg = self._build_user_message(user_message, images)

        try:
            # Stream agent response with heartbeat monitoring
            success = await self._stream_agent_response(messages, user_msg, accumulated)

            if success:
                logger.debug("Session %s completed successfully", self.session_id)

        except Exception as exc:
            logger.error("Agent invocation failed: %s", exc, exc_info=True)
            # Cancel heartbeat task on error (prevents zombie tasks)
            if self._heartbeat_task is not None and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            await self._handle_send_error(exc)

    async def _handle_message_token(self, token, metadata: dict, accumulated: list[str]) -> None:
        """Process a single message token from the stream."""
        from langchain_core.messages import AIMessageChunk, ToolMessage

        if isinstance(token, AIMessageChunk) and token.tool_call_chunks:
            for tc in token.tool_call_chunks:
                call_id = tc.get("id", "")
                if tc.get("name") and call_id and call_id not in self._seen_tool_calls:
                    self._seen_tool_calls.add(call_id)
                    args = tc.get("args", {})
                    # Preserve the real tool call so it can be replayed into
                    # conversation history — without this, the model loses
                    # all memory of tool calls it made earlier in the session.
                    self._pending_tool_calls.append(
                        {
                            "id": call_id,
                            "name": tc["name"],
                            "args": args if isinstance(args, dict) else {},
                        }
                    )
                    self._enqueue(
                        {
                            "type": "tool_call",
                            "tool": tc["name"],
                            "args": args,
                            "call_id": call_id,
                        }
                    )

        if isinstance(token, ToolMessage):
            call_id = getattr(token, "tool_call_id", "")
            if call_id and call_id not in self._seen_tool_results:
                self._seen_tool_results.add(call_id)
                self._pending_tool_messages.append(token)
                output_text = str(token.content) if token.content else ""
                is_error = output_text.startswith("Error:") or getattr(token, "status", None) == "error"
                self._enqueue(
                    {
                        "type": "tool_result",
                        "call_id": call_id,
                        "output": output_text,
                        "success": not is_error,
                    }
                )
                if settings.hooks.hooks_enabled:
                    try:
                        await get_hook_manager().run_hooks(
                            HookEvent.POST_TOOL_USE,
                            {
                                "session_id": self.session_id,
                                "tool_name": getattr(token, "name", "unknown"),
                                "tool_args": {},
                                "tool_result": str(token.content)[:400] if token.content else "",
                                "call_id": call_id,
                            },
                        )
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
                self._enqueue(
                    {
                        "type": "response_chunk",
                        "content": chunk_text,
                    }
                )

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

    async def answer(self, call_id: str, answer_text: str) -> None:
        """Record an answer for an ask_user tool call."""
        self._ask_user_answers[call_id] = answer_text
        gate = self._pending_answers.get(call_id)
        if gate is not None:
            gate.set()

    def _wait_for_answer(self, call_id: str) -> asyncio.Event:
        """Create (or return existing) answer gate for an ask_user call."""
        if call_id not in self._pending_answers:
            self._pending_answers[call_id] = asyncio.Event()
        return self._pending_answers[call_id]

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
        # Cancel heartbeat task if running
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
        await super().close()
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

    def _enqueue(self, event: dict) -> None:
        """Put an event dict onto the internal queue (non-blocking)."""
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event to make room (prevents deadlock on slow consumers)
            with contextlib.suppress(asyncio.QueueEmpty):
                self._event_queue.get_nowait()
            try:
                self._event_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event queue full — dropping event for session %s", self.session_id)

    # ── Background extraction ──────────────────────────────────────────────

    def _schedule_extraction(self, user_message: str, response: str) -> None:
        """Schedule fire-and-forget memory extraction from a conversation turn.

        Uses a bounded queue (max 3 pending). If the queue is full,
        drops the oldest extraction to prevent unbounded growth.
        """
        # Drop oldest if at capacity
        if self._extraction_queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._extraction_queue.get_nowait()

        combined = f"User: {user_message}\nAssistant: {response}"
        task = asyncio.create_task(self._run_extraction(combined))
        task.add_done_callback(self._on_extraction_done)
        try:
            self._extraction_queue.put_nowait(task)
        except asyncio.QueueFull:
            # Extremely unlikely (we just made room), but handle gracefully
            task.cancel()

    async def _run_extraction(self, text: str) -> None:
        """Run memory extraction and store results."""
        # Use base class method
        await self.extract_and_store("", text)  # Empty user_msg, full text as response

    @staticmethod
    def _on_extraction_done(task: asyncio.Task) -> None:
        """Log errors from background extraction tasks (never swallow silently)."""
        exc = task.exception()
        if exc is not None:
            logger.warning("Auto-extraction task failed: %s", exc)

    def _maybe_trigger_dream_cycle(self) -> None:
        """Auto-trigger dream cycle every N turns (fire-and-forget)."""
        interval = settings.agent.dream_cycle_interval
        if interval <= 0:
            return
        if self._turn_count % interval != 0:
            return
        if self._turn_count == 0:
            return

        # Fire-and-forget: create task without awaiting
        self._dream_task = asyncio.create_task(self._run_dream_cycle())

    async def _run_dream_cycle(self) -> None:
        """Run dream cycle in background."""
        try:
            cycle = DreamCycle(str(self.memory_dir))
            report = await cycle.run(dry_run=False)
            logger.info(
                "Dream cycle completed for session %s: %s",
                self.session_id,
                report,
            )
        except Exception as exc:
            logger.warning("Dream cycle failed: %s", exc)
