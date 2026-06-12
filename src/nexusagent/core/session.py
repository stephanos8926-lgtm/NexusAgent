"""Session manager for interactive WebSocket sessions.

Provides Session (a single conversation) and SessionManager (lifecycle/cache).
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import subprocess
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from nexusagent.infrastructure.config import settings
from nexusagent.hooks import HookEvent, get_hook_manager
from nexusagent.llm.models import ErrorEvent, ResponseEvent, ThinkingEvent
from nexusagent.infrastructure.prompt_loader import inject_file_at_reference, load_nexus_prompt

logger = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────────────


def _extract_agent_response(result) -> str:
    """Extract the last assistant message content from an agent result."""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        text_parts = []
        for block in result:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "thinking":
                    pass
                else:
                    text_parts.append(str(block))
            else:
                text_parts.append(str(block))
        return "\n".join(text_parts) if text_parts else str(result)
    if isinstance(result, dict):
        if "messages" in result:
            from langchain_core.messages import BaseMessage
            messages = result["messages"]
            for msg in reversed(messages):
                if isinstance(msg, BaseMessage) and not isinstance(msg, SystemMessage):
                    content = msg.content
                    if isinstance(content, list):
                        return _extract_agent_response(content)
                    return content or str(msg)
            if messages:
                last = messages[-1]
                content = last.content if isinstance(last, BaseMessage) else str(last)
                if isinstance(content, list):
                    return _extract_agent_response(content)
                return str(content)
            return "No messages in response"
        if "response" in result:
            return str(result["response"])
        if "result" in result:
            return str(result["result"])
        if "content" in result:
            return str(result["content"])
        return str(result)
    return str(result)


def _get_git_info(working_dir: str) -> str:
    """Get git status summary for the working directory."""
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
            cwd=working_dir,
        ).stdout.strip()
        if not branch:
            return ""
        status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=5,
            cwd=working_dir,
        ).stdout.strip()
        info = f"Branch: {branch}"
        if status:
            changed = len(status.splitlines())
            info += f" | {changed} changed file{'s' if changed != 1 else ''}"
        else:
            info += " | clean"
        return info
    except Exception:
        return ""


def _build_environment_context(working_dir: str) -> str:
    """Build the environment context block injected into every session."""
    now = datetime.now(UTC)
    user = os.getenv("USER", os.getenv("USERNAME", "unknown"))
    hostname = platform.node()
    os_info = ""
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    os_info = line.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        os_info = platform.system()

    cwd = str(Path(working_dir).resolve())
    git_info = _get_git_info(working_dir)

    lines = [
        "## Environment",
        f"- **Working Directory**: `{cwd}`",
        f"- **User**: {user}@{hostname}",
        f"- **OS**: {os_info}",
        f"- **Time**: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]
    if git_info:
        lines.append(f"- **Git**: {git_info}")

    # List available tools
    try:
        from nexusagent.tools.registry import list_all_tools
        tools = list_all_tools()
        if tools:
            by_cat: dict[str, list[str]] = {}
            for t in tools:
                by_cat.setdefault(t.category, []).append(t.name)
            lines.append("\n## Available Tools")
            for cat in sorted(by_cat):
                names = ", ".join(sorted(by_cat[cat]))
                lines.append(f"- **{cat}**: {names}")
    except Exception:
        pass

    return "\n".join(lines)


def _build_session_history_context(working_dir: str) -> str:
    """Build context from recent sessions for continuity.

    Uses the hybrid memory system to find and summarize recent
    conversation sessions, giving the agent awareness of what
    the user has been working on.
    """
    try:
        # This is a simplified version — in production you'd query
        # the session DB for recent sessions in this working dir
        # and extract summaries. For now, return empty.
        return ""
    except Exception:
        return ""


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
        from nexusagent.memory.memory import HybridMemoryManager

        self.hybrid_memory = HybridMemoryManager(str(self.memory_dir))
        self.hybrid_memory.initialize()

        self.status: str = "active"
        self._cancel_flag: bool = False
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}
        self._seen_tool_results: set[str] = set()  # deduplicate tool_result events
        self._seen_tool_calls: set[str] = set()  # deduplicate tool_call events
        self._conversation_history: list[Any] = []  # accumulated LangChain messages

    # ── Prompt & Context ─────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        """Load the full system prompt from NEXUS.md files.

        Loads base prompt from config/NEXUS.md, then appends any
        project-specific NEXUS.md from the working directory.
        @file chains are resolved recursively.
        """
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

        # Session history from memory
        history_ctx = _build_session_history_context(self.working_dir)
        if history_ctx:
            parts.append(f"\n## Recent Session History\n{history_ctx}")

        return "\n".join(parts)

    # ── Send a user message ────────────────────────────────────────────

    def _process_chat_input(self, user_message: str) -> str:
        """Process chat input: handle @file injection if enabled."""
        if not settings.prompt.chat_file_injection:
            return user_message

        # Check if the message contains @file references
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
        """Build a HumanMessage, optionally with image attachments.

        When images are provided, the message content is a list of content blocks
        (text + image_url blocks) for multimodal LLM input.

        Args:
            user_message: The text content.
            images: Optional list of image file paths or URLs.

        Returns:
            A HumanMessage with either string content (text-only) or list content
            (multimodal with images).
        """
        from langchain_core.messages import HumanMessage
        from nexusagent.llm.models import encode_image_to_content

        if not images:
            return HumanMessage(content=user_message)

        # Build multimodal content: text + images
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
        """Process a user message: store in DB, recall memory, invoke agent, emit events.

        Uses deepagents' astream() for real-time streaming of tool calls,
        tool results, and tokens — so the TUI can show progress instead of
        going silent for the entire duration.

        Args:
            user_message: The user's text message.
            images: Optional list of image file paths or URLs to attach.
        """
        if self.status != "active":
            self._enqueue(ErrorEvent(message="Session is not active").model_dump())
            return

        # Fire session_init hooks
        if settings.hooks.hooks_enabled:
            try:
                await get_hook_manager().run_hooks(HookEvent.SESSION_INIT, {
                    "session_id": self.session_id,
                    "working_dir": self.working_dir,
                    "config": settings,
                })
            except Exception as exc:
                logger.warning("session_init hook failed: %s", exc)

        # Process @file injection in chat input
        user_message = self._process_chat_input(user_message)

        # Emit thinking indicator so the TUI can show busy state
        self._enqueue(ThinkingEvent(content="Processing...").model_dump())

        # Store user message in DB
        try:
            await self.db_repo.add_message(self.session_id, "user", user_message)
        except Exception as exc:
            logger.warning("Failed to store user message in DB: %s", exc)

        # Build messages list: system prompt + context + memory + history + user message
        from langchain_core.messages import HumanMessage

        # 1. System prompt from NEXUS.md + environment context merged together
        system_prompt = self._load_system_prompt()
        context_block = self._build_context_injection()
        if context_block:
            system_prompt = system_prompt + "\n\n" + context_block
        messages = [SystemMessage(content=system_prompt)]

        # 2. Memory context from hybrid memory
        try:
            hybrid_context = self.hybrid_memory.get_memory_context(user_message, max_results=5)
            if hybrid_context:
                messages.append(SystemMessage(content=hybrid_context))
        except Exception as exc:
            logger.warning("Hybrid memory context retrieval failed: %s", exc)

        # 4. Conversation history
        messages.extend(self._conversation_history[-settings.agent.max_conversation_history:])

        # 5. New user message (with optional image attachments)
        user_msg = self._build_user_message(user_message, images)
        messages.append(user_msg)

        # Compaction: if messages exceed context window, compact before model call
        from nexusagent.memory.compaction import CompactionPipeline, pre_compaction_flush

        _compaction = CompactionPipeline()
        if settings.agent.compaction_enabled and _compaction.should_compact(
            [{"role": "system" if isinstance(m, SystemMessage) else "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content} for m in messages]
        ):
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
                    # assistant and any other roles → AIMessage
                    messages.append(AIMessage(content=md["content"]))

        # Invoke the agent
        self._cancel_flag = False
        try:
            result = self.agent({"messages": messages})
            if asyncio.iscoroutine(result):
                result = await result

            if self._cancel_flag:
                self._enqueue(ErrorEvent(message="Session interrupted").model_dump())
            else:
                final_content = _extract_agent_response(result)
                self._enqueue(ResponseEvent(content=final_content).model_dump())

                # Update conversation history for continuity
                self._conversation_history.append(user_msg)
                self._conversation_history.append(AIMessage(content=final_content))
                # Trim history to configured max
                max_hist = settings.agent.max_conversation_history
                if len(self._conversation_history) > max_hist:
                    self._conversation_history = self._conversation_history[-max_hist:]

                # Store assistant response in DB
                try:
                    await self.db_repo.add_message(self.session_id, "assistant", final_content)
                except Exception as exc:
                    logger.warning("Failed to store assistant message in DB: %s", exc)

                # Remember in memory
                try:
                    if self.memory is not None:
                        await self.memory.remember(
                            user_message,
                            metadata={"response": final_content},
                        )
                except Exception as exc:
                    logger.warning("Failed to remember in memory: %s", exc)

        except Exception as exc:
            logger.error("Agent invocation failed: %s", exc, exc_info=True)
            # Fire error hooks
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
        """Process a single message token from the stream.

        Handles:
        - AIMessageChunk with tool_call_chunks → emit tool_call event
        - ToolMessage → emit tool_result event
        - AIMessageChunk with text content → accumulate for final response
        """
        from langchain_core.messages import AIMessageChunk, ToolMessage

        # Tool call chunks (streaming tool invocations) — deduplicate by call_id
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

        # Tool results — deduplicate by call_id
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
                # Fire post_tool_use hook
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

        # Regular AI text content — accumulate for final response AND stream chunks
        if isinstance(token, AIMessageChunk) and token.content and not token.tool_call_chunks:
            chunk_text = ""
            if isinstance(token.content, str):
                chunk_text = token.content
                accumulated.append(chunk_text)
            elif isinstance(token.content, list):
                # Gemma returns content as list of {type: thinking|text, ...} blocks
                for block in token.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        chunk_text += text
                        accumulated.append(text)
            # Emit real-time chunk event so TUI can stream token-by-token
            if chunk_text:
                self._enqueue({
                    "type": "response_chunk",
                    "content": chunk_text,
                })

    async def _handle_update(self, data: dict) -> None:
        """Process an update chunk from the stream.

        Tracks node-level progress for status bar updates.
        """
        if not isinstance(data, dict):
            return

        for node_name, node_data in data.items():
            # Detect tool execution from the "tools" node — deduplicate
            if node_name == "tools" and isinstance(node_data, dict):
                msgs = node_data.get("messages", [])
                for msg in msgs:
                    if hasattr(msg, "type") and msg.type == "tool":
                        call_id = getattr(msg, "tool_call_id", "")
                        if call_id and call_id not in self._seen_tool_results:
                            self._seen_tool_results.add(call_id)
                            self._enqueue({
                                "type": "tool_result",
                                "call_id": call_id,
                                "output": str(msg.content) if msg.content else "",
                                "success": True,
                            })

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
