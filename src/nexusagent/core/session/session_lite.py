"""SessionLite — lightweight session for worker agents.

Provides memory recall, auto-extraction, and dream cycle for workers
without the overhead of event streaming, approval gates, or real-time
token streaming.

Used by WorkerPool when spawning sub-agent workers that need memory
inheritance from the parent session.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from nexusagent.infrastructure.config import settings
from nexusagent.infrastructure.prompt_loader import load_nexus_prompt
from nexusagent.memory.compaction import CompactionPipeline, pre_compaction_flush
from nexusagent.memory.dream import DreamCycle
from nexusagent.memory.extraction import MemoryExtractor
from nexusagent.memory.memory import HybridMemoryManager

logger = logging.getLogger(__name__)


class SessionLite:
    """Lightweight session for worker agents.

    Provides:
    - Memory recall (HybridMemoryManager with optional parent inheritance)
    - Auto-extraction after each turn
    - Dream cycle (periodic consolidation)
    - Compaction (pre-flush before context limits)

    Does NOT provide:
    - Event streaming (no WebSocket/TUI)
    - Approval gates
    - Real-time token streaming
    - Conversation history management

    Args:
        session_id: Unique identifier for this session.
        working_dir: Absolute path to the project working directory.
        memory_dir: Optional override for the hybrid memory directory.
        parent_memory_dir: Optional path to a parent workspace whose memory
            index this session should inherit from.
        llm_call: Optional async callable for LLM invocations.
                  Used for LLM-powered extraction when enabled.
    """

    def __init__(
        self,
        session_id: str,
        working_dir: str,
        memory_dir: str | Path | None = None,
        parent_memory_dir: str | Path | None = None,
        llm_call: Any = None,
    ):
        self.session_id = session_id
        self.working_dir = working_dir

        if memory_dir is None:
            memory_dir = Path(working_dir) / ".nexusagent" / "memory"
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # HybridMemoryManager with optional parent inheritance
        self.hybrid_memory = HybridMemoryManager(
            str(self.memory_dir),
            parent_memory_dir=parent_memory_dir,
        )
        self.hybrid_memory.initialize()

        # LLM extraction (optional)
        self._llm_call = llm_call
        self._llm_extractor = None
        if llm_call is not None:
            from nexusagent.memory.llm_extraction import LLMExtractor
            self._llm_extractor = LLMExtractor(llm_call=llm_call)

        # Compaction
        self._compaction = CompactionPipeline()

        # Turn counting for dream cycle
        self._turn_count = 0

    async def get_memory_context(self, query: str, max_results: int = 5) -> str:
        """Get relevant memory context for injection into agent prompts.

        Args:
            query: The user message or task description.
            max_results: Maximum number of memories to retrieve.

        Returns:
            Formatted memory context string, or empty string if none found.
        """
        try:
            return await self.hybrid_memory.get_memory_context(
                query, max_results=max_results
            )
        except Exception as exc:
            logger.warning("Memory context retrieval failed: %s", exc)
            return ""

    async def remember(
        self,
        content: str,
        type: str = "observation",
        description: str = "",
        confidence: float | None = None,
        entities: list[str] | None = None,
        source_session_id: str | None = None,
    ) -> str:
        """Store a memory entry.

        Args:
            content: The memory content.
            type: Type of memory (observation, world, opinion, preference, error).
            description: Short description/title.
            confidence: Confidence score (0.0-1.0).
            entities: Related entity names.
            source_session_id: The session that created this memory.

        Returns:
            File path of the written entry.
        """
        return await self.hybrid_memory.remember(
            content=content,
            type=type,
            description=description,
            confidence=confidence,
            entities=entities,
            source_session_id=source_session_id or self.session_id,
        )

    async def extract_and_store(self, user_message: str, response: str) -> int:
        """Run auto-extraction on a conversation turn and store results.

        Args:
            user_message: The user's message.
            response: The assistant's response.

        Returns:
            Number of memories extracted and stored.
        """
        combined = f"User: {user_message}\nAssistant: {response}"

        if self._llm_extractor is not None:
            results = await self._llm_extractor.extract(combined)
        else:
            extractor = MemoryExtractor()
            results = extractor.extract(combined)

        stored = 0
        for result in results:
            try:
                await self.remember(
                    content=result.content,
                    type=result.type,
                    description=result.description,
                    confidence=result.confidence,
                    entities=result.entities,
                )
                stored += 1
            except Exception as exc:
                logger.warning("Failed to store extracted memory: %s", exc)

        self._turn_count += 1
        return stored

    async def maybe_dream(self) -> None:
        """Run dream cycle if interval has been reached."""
        interval = settings.agent.dream_cycle_interval
        if interval <= 0:
            return
        if self._turn_count % interval != 0:
            return
        if self._turn_count == 0:
            return

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

    async def pre_compaction_flush(self) -> str:
        """Flush session state before context compaction.

        Returns:
            Summary string to be inserted into the conversation.
        """
        return await pre_compaction_flush(self, f"Session {self.session_id} turn")

    def get_load_context(self) -> str:
        """Get the NEXUS.md + environment context for this session.

        Returns:
            Formatted context string for prompt injection.
        """
        try:
            nexus_prompt = load_nexus_prompt(
                package_root=Path(__file__).parent.parent.parent,
                cwd=Path(self.working_dir),
                max_depth=8,
            )
            return nexus_prompt
        except Exception:
            return ""

    async def close(self) -> None:
        """Close the session and clean up resources."""
        try:
            self.hybrid_memory.close()
        except Exception as exc:
            logger.debug("Error closing hybrid memory: %s", exc)
