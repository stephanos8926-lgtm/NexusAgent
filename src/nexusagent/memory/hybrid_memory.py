# src/nexusagent/memory/hybrid_memory.py
"""HybridMemoryManager — combines FileMemory + HybridMemoryIndex."""

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class HybridMemoryManager:
    """Combines file-based memory (canonical) with hybrid search index (derived).

    This is the top-level memory interface for the hybrid memory system.
    Files are the source of truth; the SQLite index is rebuilt from them.
    """

    def __init__(self, workspace_dir: str):
        """Initialize the hybrid memory manager.

        Args:
            workspace_dir: Path to the workspace root. Memory files live
                under this directory; the SQLite index is derived from them.
        """
        from nexusagent.memory.memory_files import FileMemory
        from nexusagent.memory.memory_index import HybridMemoryIndex

        self.workspace_dir = workspace_dir
        self.file_memory = FileMemory(workspace_dir)
        self.index = HybridMemoryIndex(workspace_dir)

    def initialize(self):
        """Initialize the file memory layer."""
        self.file_memory.initialize()

    async def remember(
        self,
        content: str,
        type: str,
        description: str,
        confidence: float | None = None,
        entities: list[str] | None = None,
        source_session_id: str | None = None,
        derived_from: list[str] | None = None,
    ) -> str:
        """Write a memory entry and index it using the full async embedding chain.

        Returns the file path of the written entry.
        """
        from nexusagent.memory.memory_files import MemoryEntryType

        entry_type = MemoryEntryType(type)
        filepath = self.file_memory.write_entry(
            content=content,
            entry_type=entry_type,
            description=description,
            confidence=confidence,
            entities=entities,
            source_session_id=source_session_id,
            derived_from=derived_from,
        )
        # Index the file that was just written — async with Gemini embeddings
        rel_path = filepath.replace(self.workspace_dir, "").lstrip("/")
        await self.index.async_index_file(rel_path)
        return filepath

    async def recall(self, query: str, max_results: int = 6) -> list[dict]:
        """Search memory using hybrid keyword + vector search.

        Returns results with citations (file, content, score).
        """
        return await self.index.search(query, max_results=max_results)

    async def get_memory_context(self, query: str, max_results: int = 5) -> str:
        """Format recall results as a context string for prompt injection.

        Includes source citations in the format 'Source: bank/filename.md'.
        Uses async search to avoid blocking the event loop.
        """
        results = await self.index.search(query, max_results=max_results)
        if not results:
            return ""

        lines = ["## Relevant Memories\n"]
        for r in results:
            source = r.get("file", "unknown")
            content = r.get("content", "").strip()
            score = r.get("score", 0)
            lines.append(f"Source: {source} (score: {score:.2f})")
            lines.append(f"{content}\n")

        return "\n".join(lines)

    async def flush(self, session_summary: str):
        """Persist a session summary to the daily log and re-index.

        Uses async embedding (Gemini → local → hash fallback) for the re-index
        step so that stored vectors match query vectors.
        """
        self.file_memory.append_daily_log(session_summary)
        # Re-index the daily log file — async with full embedding chain
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        rel_path = f"memory/{today}.md"
        await self.index.async_index_file(rel_path)

    def close(self):
        """Close the memory manager and clean up resources.

        Releases the embedding provider and index references so that
        the SQLite connections (opened/closed per-method) and the
        embedder's thread pool can be garbage-collected.
        """
        if self.index is not None:
            self.index.embedder = None  # type: ignore[assignment]
