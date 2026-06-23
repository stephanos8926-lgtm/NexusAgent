"""Context compaction pipeline for managing conversation history size.

Applies graduated compaction strategies from cheapest to most expensive:
  1. Clear old tool results
  2. Microcompact (remove old tool result content)
  3. Summarize oldest messages
  4. Emergency truncation (last resort)

After graduated compaction, a SummaryDAG can be applied for hierarchical
context compression (depth-0 leaves → depth-1 arcs → depth-2 narratives).

The pipeline is stateless — it takes messages in, returns compacted messages out.
It is designed to be called BEFORE each model invocation.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# LLM call signature: (system_prompt, user_prompt) -> text
_DAGLLMCallable = Callable[[str, str], Awaitable[str]]


# ---------------------------------------------------------------------------
# CompactionPipeline
# ---------------------------------------------------------------------------


class CompactionPipeline:
    """Graduated context compaction pipeline.

    Compaction levels (cheapest → most expensive):
      1. _clear_tool_results — blank old tool result content
      2. _microcompact       — remove tool results for old turns
      3. _summarize_old_messages — compress old messages into a summary
      4. _emergency_truncate    — keep only the last N messages
    """

    def __init__(
        self,
        context_window_tokens: int = 200_000,
        compaction_threshold: float = 0.75,
    ) -> None:
        """Initialize the compaction pipeline.

        Args:
            context_window_tokens: Maximum tokens the model context window holds.
            compaction_threshold: Fraction of the context window at which
                compaction is triggered (e.g. 0.75 = compact at 75% full).
        """
        self.context_window_tokens = context_window_tokens
        self.compaction_threshold = compaction_threshold

    # -- public API ----------------------------------------------------------

    def estimate_tokens(self, messages: list[dict]) -> int:
        """Estimate token count from message content lengths.

        Uses a simple heuristic: 4 chars per token.
        """
        total_chars = 0
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                # Handle list content (e.g. tool_use / multi-modal blocks)
                for block in content:
                    if isinstance(block, dict):
                        total_chars += len(str(block))
                    elif isinstance(block, str):
                        total_chars += len(block)
        return total_chars // 4

    def should_compact(self, messages: list[dict]) -> bool:
        """Return True if the message list exceeds the compaction threshold."""
        return self.estimate_tokens(messages) > int(
            self.compaction_threshold * self.context_window_tokens
        )

    def compact(self, messages: list[dict]) -> list[dict]:
        """Apply graduated compaction until the message list is under threshold.

        Returns the (possibly modified) message list.
        """
        if not messages:
            return messages

        # Level 1: clear old tool results
        messages = self._clear_tool_results(messages)
        if not self.should_compact(messages):
            return messages

        # Level 2: microcompact
        messages = self._microcompact(messages)
        if not self.should_compact(messages):
            return messages

        # Level 3: summarize old messages
        messages = self._summarize_old_messages(messages)
        if not self.should_compact(messages):
            return messages

        # Level 4: emergency truncation (last resort)
        messages = self._emergency_truncate(messages)
        return messages

    # -- DAG-based hierarchical compaction ------------------------------------

    def compress_with_dag(
        self,
        messages: list[dict],
        llm_call: _DAGLLMCallable | None = None,
        fresh_tail: int | None = None,
    ) -> list[dict]:
        """Apply graduated compaction, then DAG-based hierarchical summarization.

        This is a convenience method that:
        1. Runs the graduated pipeline (levels 1-4) first.
        2. Builds a SummaryDAG from the result.
        3. Compresses the DAG (leaves → arcs → narratives).
        4. Returns the DAG as a message list.

        Args:
            messages: The conversation messages to compact.
            llm_call: Optional async callable for LLM-based summarization.
                If None, heuristic summaries are used.
            fresh_tail: Override the DAG fresh_tail. Defaults to the
                pipeline's context-derived heuristic (32 messages).

        Returns:
            A message list with hierarchical summaries and fresh tail.
        """
        from nexusagent.memory.dag import SummaryDAG

        # Step 1: graduated compaction
        messages = self.compact(messages)

        if len(messages) <= 1:
            return messages

        # Step 2: build and compress DAG
        tail = fresh_tail if fresh_tail is not None else 32
        dag = SummaryDAG(fresh_tail=max(tail, 1))
        for msg in messages:
            dag.add_message(msg)

        # DAG compression is async — run synchronously if no event loop
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an async context — create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run, dag.compress(llm_call=llm_call)
                )
                future.result()
        else:
            asyncio.run(dag.compress(llm_call=llm_call))

        return dag.to_messages()

    # -- strategy 1: clear old tool results ----------------------------------

    def _clear_tool_results(self, messages: list[dict]) -> list[dict]:
        """Replace old tool result content with a placeholder.

        For messages older than the last 5 *turns* that contain tool results,
        replace the tool result content while keeping the message structure.
        A "turn" is approximated as a user+assistant pair, so we look at the
        last ~10 messages (5 user + 5 assistant).
        """
        keep_last = 10  # last 5 turns
        if len(messages) <= keep_last:
            return messages

        split = len(messages) - keep_last
        result = []
        for i, msg in enumerate(messages):
            if i < split and msg.get("role") == "tool":
                new_msg = dict(msg)
                new_msg["content"] = "[Previous tool result content cleared]"
                result.append(new_msg)
            else:
                result.append(msg)
        return result

    # -- strategy 2: microcompact --------------------------------------------

    def _microcompact(self, messages: list[dict]) -> list[dict]:
        """Remove tool result content for messages older than last 3 turns.

        Keeps user messages and assistant text responses intact.
        A "turn" ≈ 2 messages, so 3 turns ≈ 6 messages.
        """
        keep_last = 6  # last 3 turns
        if len(messages) <= keep_last:
            return messages

        split = len(messages) - keep_last
        result = []
        for i, msg in enumerate(messages):
            if i < split and msg.get("role") == "tool":
                new_msg = dict(msg)
                new_msg["content"] = "[Previous tool result content cleared]"
                result.append(new_msg)
            else:
                result.append(msg)
        return result

    # -- strategy 3: summarize old messages ----------------------------------

    def _summarize_old_messages(self, messages: list[dict], keep_last: int = 10) -> list[dict]:
        """Replace old messages with a single summary system message.

        Takes messages older than *keep_last* and generates a simple
        heuristic summary (concatenates user messages, notes key actions).
        In production this would call an LLM for a proper summary.
        """
        if len(messages) <= keep_last:
            return messages

        old_messages = messages[:keep_last]
        recent_messages = messages[keep_last:]

        # Build a heuristic summary from user messages and assistant actions
        user_parts: list[str] = []
        assistant_parts: list[str] = []
        assistant_with_tools = 0

        for msg in old_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                if role == "user":
                    user_parts.append(content[:200])
                elif role == "assistant":
                    assistant_parts.append(content[:200])
                    if msg.get("tool_calls"):
                        assistant_with_tools += 1

        summary_lines = []
        summary_lines.append(
            f"[Conversation summary: {len(user_parts)} user messages, "
            f"{len(assistant_parts)} assistant responses"
        )
        if assistant_with_tools:
            summary_lines.append(f", {assistant_with_tools} tool invocations")
        summary_lines.append("]\n")

        if user_parts:
            summary_lines.append("User topics discussed:")
            for part in user_parts[:5]:
                summary_lines.append(f"  - {part}")
            if len(user_parts) > 5:
                summary_lines.append(f"  ... and {len(user_parts) - 5} more messages")

        if assistant_parts:
            summary_lines.append("Assistant actions:")
            for part in assistant_parts[:3]:
                summary_lines.append(f"  - {part}")

        summary = " ".join(summary_lines)
        summary_message = {"role": "system", "content": summary}

        return [summary_message, *recent_messages]

    # -- strategy 4: emergency truncation ------------------------------------

    def _emergency_truncate(self, messages: list[dict], keep_last: int = 5) -> list[dict]:
        """Last resort: keep only the last N messages and prepend a warning."""
        if len(messages) <= keep_last:
            return messages

        kept = messages[-keep_last:]
        warning = {
            "role": "system",
            "content": "[Context truncated due to length. Previous conversation summary unavailable.]",
        }
        return [warning, *kept]


# ---------------------------------------------------------------------------
# Pre-compaction flush
# ---------------------------------------------------------------------------


async def pre_compaction_flush(session, summary: str) -> str:
    """Flush session state to memory before compaction.

    Writes the summary to the daily log via the session's hybrid memory
    manager, then returns a context string to inject after compaction.
    """
    try:
        await session.hybrid_memory.flush(summary)
    except Exception as exc:
        logger.warning("Pre-compaction flush failed: %s", exc)

    return f"Before compaction, the following was saved to memory: {summary}"
