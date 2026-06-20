"""HybridMemoryManager — combines FileMemory (canonical) with HybridMemoryIndex (derived).

This is the top-level memory interface for the hybrid memory system.
Files are the source of truth; the SQLite index is rebuilt from them.
"""

import asyncio
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from nexusagent.memory.compaction import CompactionPipeline, pre_compaction_flush
from nexusagent.memory.extraction import MemoryExtractor
from nexusagent.memory.memory_files import FileMemory
from nexusagent.memory.memory_index import HybridMemoryIndex

logger = logging.getLogger(__name__)

# Maximum extraction queue size
_MAX_EXTRACTION_QUEUE = 3

# Stale threshold for dream cycle (30 days)
STALE_THRESHOLD_DAYS = 30
LOW_QUALITY_THRESHOLD = 0.3


class HybridMemoryManager:
    """Combines file-based memory (canonical) with hybrid search index (derived).

    This is the top-level memory interface for the hybrid memory system.
    Files are the source of truth; the SQLite index is rebuilt from them.
    """

    def __init__(self, workspace_dir: str | Path):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.file_memory = FileMemory(str(self.workspace_dir))
        self.index = HybridMemoryIndex(str(self.workspace_dir))

        # Extraction queue — bounded to prevent unbounded growth
        self._extraction_queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_EXTRACTION_QUEUE)
        self._extractor = MemoryExtractor()
        self._turn_count: int = 0

    def initialize(self) -> None:
        """Initialize the file memory layer."""
        self.file_memory.initialize()

    async def remember(
        self,
        content: str,
        type: str = "observation",
        description: str = "",
        confidence: float | None = None,
        entities: list[str] | None = None,
        ttl_hours: int | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        source_session_id: str | None = None,
        derived_from: list[str] | None = None,
        related: list[str] | None = None,
    ) -> str:
        """Write a memory entry and index it using the full async embedding chain.

        Returns the file path of the written entry.
        """
        from nexusagent.memory.memory_files import MemoryEntryType
        entry_type = MemoryEntryType(type) if isinstance(type, str) else type

        # Auto-link to related memories if not explicitly provided
        if related is None:
            related = self.file_memory.find_related(
                content=content,
                entities=entities,
                max_results=3,
            )

        filepath = self.file_memory.write_entry(
            content=content,
            entry_type=entry_type,
            description=description,
            confidence=confidence,
            entities=entities or None,
            ttl_hours=ttl_hours,
            valid_from=valid_from,
            valid_until=valid_until,
            source_session_id=source_session_id,
            derived_from=derived_from,
            related=related,
        )
        # Index the file that was just written — async with Gemini embeddings
        rel_path = str(filepath).replace(str(self.workspace_dir), "").lstrip("/")
        await self.index.async_index_file(rel_path)
        return filepath

    async def recall(
        self,
        query: str,
        max_results: int = 6,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> list[dict]:
        """Search memory using hybrid keyword + vector search.

        Returns results with citations (file, content, score).

        Args:
            query: Search query string.
            max_results: Maximum results to return.
            valid_from: Optional ISO datetime — filter memories with valid_from >= this date.
            valid_until: Optional ISO datetime — filter memories with valid_until <= this date.
        """
        results = await self.index.search(query, max_results=max_results * 3)  # Fetch more to filter

        # Apply bi-temporal filtering
        if valid_from or valid_until:
            from datetime import datetime, UTC
            valid_from_dt = datetime.fromisoformat(valid_from) if valid_from else None
            valid_until_dt = datetime.fromisoformat(valid_until) if valid_until else None

            filtered = []
            for r in results:
                file_path = r.get("file", "")
                # Read frontmatter to check temporal fields
                vf, vu = await self._get_entry_temporal_fields(file_path)
                if valid_from_dt and (vf is None or vf < valid_from_dt):
                    continue
                if valid_until_dt and (vu is None or vu is None or vu > valid_until_dt):
                    continue
                filtered.append(r)
            results = filtered

        return results[:max_results]

    async def _get_entry_temporal_fields(self, file_path: str) -> tuple:
        """Extract valid_from and valid_until from a memory file's frontmatter.

        Args:
            file_path: Relative path to the memory file (e.g., "bank/obs-123.md")

        Returns:
            Tuple of (valid_from, valid_until) as datetime objects or None if not present.
        """
        import yaml
        from datetime import datetime, UTC

        full_path = self.workspace_dir / file_path
        if not full_path.exists():
            return None, None

        try:
            content = full_path.read_text()
            # Extract YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    vf = frontmatter.get("valid_from")
                    vu = frontmatter.get("valid_until")
                    vf_dt = datetime.fromisoformat(vf) if vf else None
                    vu_dt = datetime.fromisoformat(vu) if vu else None
                    return vf_dt, vu_dt
        except Exception:
            pass
        return None, None

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

        Closes the database connections in the underlying index.
        """
        self.index.close()

    async def _get_entry_temporal_fields(self, file_path: str) -> tuple:
        """Extract valid_from and valid_until from a memory file's frontmatter.

        Args:
            file_path: Relative path to the memory file (e.g., "bank/obs-123.md")

        Returns:
            Tuple of (valid_from, valid_until) as datetime objects or None if not present.
        """
        import yaml
        from datetime import datetime, UTC

        full_path = self.workspace_dir / file_path
        if not full_path.exists():
            return None, None

        try:
            content = full_path.read_text()
            # Extract YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    vf = frontmatter.get("valid_from")
                    vu = frontmatter.get("valid_until")
                    vf_dt = datetime.fromisoformat(vf) if vf else None
                    vu_dt = datetime.fromisoformat(vu) if vu else None
                    return vf_dt, vu_dt
        except Exception:
            pass
        return None, None