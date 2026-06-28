"""Summary DAG for hierarchical context compression.

Provides a 3-level DAG structure for progressive conversation summarization:
  - Depth-0 (Leaf):   Raw conversation messages
  - Depth-1 (Arc):    Summarized conversation arcs (4+ leaves → 1 arc)
  - Depth-2 (Narrative): Durable narrative and milestones (4+ arcs → 1 narrative)

The DAG grows indefinitely as leaves are added. Compression promotes
lower-depth nodes into higher-depth summaries. The fresh tail (last 32
messages by default) is never compressed.

LLM summarization is optional — when no LLM callable is provided, heuristic
summaries are generated instead.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------


@dataclass
class DAGNode:
    """A single node in the summary DAG."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    depth: int = 0  # 0=leaf, 1=arc, 2=narrative
    content: str = ""
    source_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMessage:
    """A thin wrapper around a message dict with a stable ID."""

    id: str
    message: dict[str, Any]


# ---------------------------------------------------------------------------
# LLM call signature
# ---------------------------------------------------------------------------

# An async callable that takes (system_prompt, user_prompt) and returns text.
LLMCallable = Callable[[str, str], Awaitable[str]]


# ---------------------------------------------------------------------------
# SummaryDAG
# ---------------------------------------------------------------------------


class SummaryDAG:
    """Hierarchical context compression via a 3-level summary DAG.

    Usage::

        dag = SummaryDAG(fresh_tail=32)
        for msg in messages:
            dag.add_leaf(msg.get("content", ""), {"role": msg.get("role")})
        await dag.compress(llm_call=my_llm)
        context = dag.to_messages()

    Args:
        fresh_tail: Number of recent messages to preserve verbatim
            (never compressed into summaries).
        leaf_batch: Number of depth-0 leaves required to form a depth-1 arc.
        arc_batch: Number of depth-1 arcs required to form a depth-2 narrative.
    """

    def __init__(
        self,
        fresh_tail: int = 32,
        leaf_batch: int = 4,
        arc_batch: int = 4,
    ) -> None:
        self.fresh_tail = fresh_tail
        self.leaf_batch = leaf_batch
        self.arc_batch = arc_batch

        # All nodes indexed by ID.
        self._nodes: dict[str, DAGNode] = {}
        # Ordered leaf node IDs (depth-0).
        self._leaves: list[str] = []
        # Ordered arc node IDs (depth-1).
        self._arcs: list[str] = []
        # Narrative node IDs (depth-2).
        self._narratives: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_leaf(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Add a depth-0 leaf node.

        Returns the node ID.
        """
        node = DAGNode(depth=0, content=content, metadata=metadata or {})
        self._nodes[node.id] = node
        self._leaves.append(node.id)
        return node.id

    def add_message(self, message: dict[str, Any]) -> str:
        """Add a leaf node from a conversation message dict.

        Uses ``message.get("content", "")`` as the leaf content.
        The full message dict is stored in metadata.
        """
        content = message.get("content", "")
        if isinstance(content, list):
            # Flatten list content to text
            content = "\n".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in content
            )
        return self.add_leaf(content, metadata=dict(message))

    async def compress(
        self,
        llm_call: LLMCallable | None = None,
        tier2_model: str = "",
    ) -> None:
        """Compress the DAG by promoting lower-depth nodes.

        1. Group uncompressed depth-0 leaves (outside fresh tail) into
           batches of ``leaf_batch`` and create depth-1 arc summaries.
        2. Group uncompressed depth-1 arcs into batches of ``arc_batch``
           and create depth-2 narrative summaries.

        If *llm_call* is provided it is used for summarization;
        otherwise heuristic summaries are generated.
        """
        await self._compress_leaves(llm_call)
        await self._compress_arcs(llm_call)

    def expand(self, node_id: str) -> list[dict[str, Any]]:
        """Expand a summary node back to its source messages.

        For leaf nodes, returns the original message from metadata.
        For arc/narrative nodes, recursively expands children.
        """
        node = self._nodes.get(node_id)
        if node is None:
            logger.warning("expand(): unknown node %s", node_id)
            return []

        if node.depth == 0:
            msg = node.metadata.get("message")
            return [msg] if msg else []

        result: list[dict[str, Any]] = []
        for child_id in node.source_ids:
            result.extend(self.expand(child_id))
        return result

    def to_messages(self, include_non_fresh: bool = True) -> list[dict[str, Any]]:
        """Convert the DAG to a flat message list for context injection.

        Messages are ordered: narratives → arcs → unprocessed leaves → fresh tail.
        Each summary node becomes a ``system`` role message with a reference marker.

        Args:
            include_non_fresh: If True (default), include summaries for
                older messages. If False, return only the fresh tail.
        """
        messages: list[dict[str, Any]] = []

        if include_non_fresh:
            # Narrative summaries (depth-2)
            for nid in self._narratives:
                node = self._nodes[nid]
                messages.append(
                    {
                        "role": "system",
                        "content": f"[Narrative summary]\n{node.content}",
                        "_dag_node_id": node.id,
                        "_dag_depth": 2,
                    }
                )

            # Arc summaries (depth-1) not yet promoted to narrative
            promoted_arcs: set[str] = set()
            for nid in self._narratives:
                node = self._nodes[nid]
                promoted_arcs.update(node.source_ids)

            for nid in self._arcs:
                if nid in promoted_arcs:
                    continue
                node = self._nodes[nid]
                messages.append(
                    {
                        "role": "system",
                        "content": f"[Conversation arc summary]\n{node.content}",
                        "_dag_node_id": node.id,
                        "_dag_depth": 1,
                    }
                )

            # Unprocessed leaves (depth-0) not promoted to arcs
            promoted_leaves: set[str] = set()
            for nid in self._arcs:
                node = self._nodes[nid]
                promoted_leaves.update(node.source_ids)

            for nid in self._leaves:
                if nid in promoted_leaves:
                    continue
                # Skip leaves in the fresh tail — they'll be added below
                if nid in self._fresh_tail_ids():
                    continue
                node = self._nodes[nid]
                msg = node.metadata.get("message")
                if msg:
                    messages.append(msg)

        # Fresh tail — always included as original messages
        for nid in self._fresh_tail_ids():
            node = self._nodes.get(nid)
            if not node:
                continue
            msg = node.metadata.get("message")
            if msg:
                messages.append(msg)

        return messages

    @property
    def leaf_count(self) -> int:
        return len(self._leaves)

    @property
    def arc_count(self) -> int:
        return len(self._arcs)

    @property
    def narrative_count(self) -> int:
        return len(self._narratives)

    def stats(self) -> dict[str, Any]:
        """Return a compact stats dict for debugging."""
        return {
            "leaves": self.leaf_count,
            "arcs": self.arc_count,
            "narratives": self.narrative_count,
            "fresh_tail": min(self.fresh_tail, self.leaf_count),
            "total_nodes": len(self._nodes),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fresh_tail_ids(self) -> set[str]:
        """Return the set of leaf IDs that are in the fresh tail."""
        n = min(self.fresh_tail, len(self._leaves))
        return set(self._leaves[-n:]) if n else set()

    async def _compress_leaves(self, llm_call: LLMCallable | None) -> None:
        """Compress uncompressed leaves outside fresh tail into arc summaries."""
        promoted = set()
        # Check narratives for promoted arcs
        for nid in self._narratives:
            node = self._nodes[nid]
            for arc_id in node.source_ids:
                arc_node = self._nodes.get(arc_id)
                if arc_node:
                    promoted.update(arc_node.source_ids)

        # Gather compressible leaf IDs
        tail_ids = self._fresh_tail_ids()
        candidates = [nid for nid in self._leaves if nid not in tail_ids and nid not in promoted]

        # Process in batches
        for batch_start in range(0, len(candidates), self.leaf_batch):
            batch = candidates[batch_start : batch_start + self.leaf_batch]
            if len(batch) < self.leaf_batch:
                # Not enough to compress — leave as-is
                break

            # Check if any are already part of an arc (from a previous pass)
            batch = [nid for nid in batch if nid not in promoted]
            if len(batch) < self.leaf_batch:
                continue

            # Build summarization prompt from leaf contents
            leaf_texts = [self._nodes[nid].content for nid in batch if nid in self._nodes]
            summary = await self._summarize(
                llm_call,
                system_prompt=(
                    "You are a conversation summarizer. Summarize the following "
                    "conversation messages into a concise arc summary preserving "
                    "key decisions, facts, and action items."
                ),
                user_prompt=_format_messages_for_summary(leaf_texts),
            )

            arc = DAGNode(
                depth=1,
                content=summary,
                source_ids=list(batch),
                metadata={"kind": "arc"},
            )
            self._nodes[arc.id] = arc
            self._arcs.append(arc.id)

            # Mark leaves as promoted
            promoted.update(batch)

    async def _compress_arcs(self, llm_call: LLMCallable | None) -> None:
        """Compress arcs into narrative summaries."""
        # Gather compressible arc IDs (not already promoted to narratives)
        promoted_arcs: set[str] = set()
        for nid in self._narratives:
            node = self._nodes[nid]
            promoted_arcs.update(node.source_ids)

        candidates = [nid for nid in self._arcs if nid not in promoted_arcs]

        for batch_start in range(0, len(candidates), self.arc_batch):
            batch = candidates[batch_start : batch_start + self.arc_batch]
            if len(batch) < self.arc_batch:
                break

            promoted = set()
            for nid in batch:
                arc_node = self._nodes.get(nid)
                if arc_node and arc_node.depth == 2:
                    promoted.add(nid)
            batch = [nid for nid in batch if nid not in promoted]

            if len(batch) < self.arc_batch:
                continue

            arc_texts = [self._nodes[nid].content for nid in batch if nid in self._nodes]
            summary = await self._summarize(
                llm_call,
                system_prompt=(
                    "You are a narrative synthesizer. Given these conversation "
                    "arc summaries, produce a concise narrative preserving the "
                    "most durable insights, milestones, and lessons learned."
                ),
                user_prompt=_format_messages_for_summary(arc_texts),
            )

            narrative = DAGNode(
                depth=2,
                content=summary,
                source_ids=list(batch),
                metadata={"kind": "narrative"},
            )
            self._nodes[narrative.id] = narrative
            self._narratives.append(narrative.id)

    async def _summarize(
        self,
        llm_call: LLMCallable | None,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate a summary using the LLM or a heuristic fallback."""
        if llm_call is not None:
            try:
                return await llm_call(system_prompt, user_prompt)
            except Exception:
                logger.warning("LLM summarization failed; using heuristic fallback")

        # Heuristic fallback: truncate and prefix
        total_chars = len(user_prompt)
        truncated = user_prompt[:1000]
        return f"[Heuristic summary of ~{total_chars} chars]\n{truncated}" + (
            "..." if total_chars > 1000 else ""
        )


# ---------------------------------------------------------------------------
# Heuristic summarization helpers
# ---------------------------------------------------------------------------


def _format_messages_for_summary(texts: Sequence[str]) -> str:
    """Format a list of message texts into a prompt-friendly block."""
    lines: list[str] = []
    for i, text in enumerate(texts, 1):
        lines.append(f"--- Message {i} ---")
        lines.append(text)
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience: DAG + CompactionPipeline integration
# ---------------------------------------------------------------------------


def dag_from_messages(
    messages: list[dict[str, Any]],
    fresh_tail: int = 32,
) -> SummaryDAG:
    """Create a :class:`SummaryDAG` from a list of conversation messages."""
    dag = SummaryDAG(fresh_tail=fresh_tail)
    for msg in messages:
        dag.add_message(msg)
    return dag


async def compress_messages(
    messages: list[dict[str, Any]],
    llm_call: LLMCallable | None = None,
    fresh_tail: int = 32,
    leaf_batch: int = 4,
    arc_batch: int = 4,
) -> list[dict[str, Any]]:
    """One-shot convenience: build DAG, compress, return messages.

    This is the primary entry point for the CompactionPipeline integration.
    """
    dag = SummaryDAG(
        fresh_tail=fresh_tail,
        leaf_batch=leaf_batch,
        arc_batch=arc_batch,
    )
    for msg in messages:
        dag.add_message(msg)
    await dag.compress(llm_call=llm_call)
    return dag.to_messages()
