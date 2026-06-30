"""HybridMemoryManager — combines FileMemory (canonical) with HybridMemoryIndex (derived).

This is the top-level memory interface for the hybrid memory system.
Files are the source of truth; the SQLite index is rebuilt from them.
"""

import asyncio
import fcntl
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

    def __init__(
        self,
        workspace_dir: str | Path,
        parent_memory_dir: str | Path | None = None,
    ):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.file_memory = FileMemory(str(self.workspace_dir))
        self.index = HybridMemoryIndex(str(self.workspace_dir))

        # Parent memory support
        self.parent_memory_dir: Path | None = None
        self._parent_index: HybridMemoryIndex | None = None
        if parent_memory_dir is not None:
            self.parent_memory_dir = Path(parent_memory_dir)

        # NATS distributed memory bus (optional)
        self._nats_memory_bus: Any = None

        # Extraction queue — bounded to prevent unbounded growth
        self._extraction_queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_EXTRACTION_QUEUE)
        self._extractor = MemoryExtractor()
        self._turn_count: int = 0

    def set_nats_memory_bus(self, nats_memory_bus: Any) -> None:
        """Set the NATS memory bus for publishing memory events.

        Args:
            nats_memory_bus: A NatsMemoryBus instance configured with
                             the worker's NATS client and session ID.
        """
        self._nats_memory_bus = nats_memory_bus

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

        # Publish to NATS if enabled (fire-and-forget)
        if self._nats_memory_bus is not None:
            try:
                await self._nats_memory_bus.publish_remember(
                    content=content,
                    memory_type=type,
                    description=description,
                    confidence=confidence,
                    entities=entities,
                    source_path=rel_path,
                )
            except Exception as exc:
                logger.warning("Failed to publish memory to NATS: %s", exc)

        return filepath

    async def recall(
        self,
        query: str,
        max_results: int = 6,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> list[dict]:
        """Search memory using hybrid keyword + vector search.

        Searches both the own index and the parent index (if configured),
        merging results with parent results marked with origin="parent".

        Returns results with citations (file, content, score).

        Args:
            query: Search query string.
            max_results: Maximum results to return.
            valid_from: Optional ISO datetime — filter memories with valid_from >= this date.
            valid_until: Optional ISO datetime — filter memories with valid_until <= this date.
        """
        fetch_count = max_results * 3  # Fetch extra for filtering
        results = await self.index.search(query, max_results=fetch_count)

        # Search parent index if configured
        parent_results: list[dict] = []
        if self._parent_index is not None:
            try:
                parent_results = await self._parent_index.search(query, max_results=fetch_count)
                for r in parent_results:
                    r["origin"] = "parent"
            except Exception as exc:
                logger.warning("Parent index search failed: %s", exc)

        # Merge: own results first, then parent results, dedup by file
        seen_files: set[str] = {r.get("file", "") for r in results}
        for r in parent_results:
            f = r.get("file", "")
            if f not in seen_files:
                seen_files.add(f)
                results.append(r)

        # Apply bi-temporal filtering
        if valid_from or valid_until:
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

        # Sort by score descending and trim
        results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
        return results[:max_results]

    async def get_memory_context(self, query: str, max_results: int = 5) -> str:
        """Format recall results as a context string for prompt injection.

        Includes source citations in the format 'Source: bank/filename.md'.
        Parent memories are prefixed with '[Parent Memory]'.
        Uses async search to avoid blocking the event loop.
        """
        results = await self.recall(query, max_results=max_results)
        if not results:
            return ""

        lines = ["## Relevant Memories\n"]
        for r in results:
            source = r.get("file", "unknown")
            content = r.get("content", "").strip()
            score = r.get("score", 0)
            origin = r.get("origin", "")
            prefix = "[Parent Memory] " if origin == "parent" else ""
            lines.append(f"{prefix}Source: {source} (score: {score:.2f})")
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

    async def close(self):
        """Close the memory manager and clean up resources.

        Closes the database connections in the underlying index
        and the parent index if one is configured.
        """
        await self.index.close()
        if self._parent_index is not None:
            await self._parent_index.close()
            self._parent_index = None

    def inherit_from(self, parent_dir: str | Path) -> None:
        """Configure this manager to inherit memories from a parent workspace.

        Validates the parent directory, checks it contains a valid memory index,
        and ensures it is not the same as the own workspace directory.

        Args:
            parent_dir: Path to the parent workspace directory containing
                ``.memory/index.sqlite``.

        Raises:
            FileNotFoundError: If parent_dir does not exist or lacks a memory index.
            ValueError: If parent_dir resolves to the same path as workspace_dir.
        """
        resolved_path = Path(parent_dir).resolve()

        # Validate path exists
        if not resolved_path.exists():
            raise FileNotFoundError(f"Parent memory directory does not exist: {resolved_path}")

        # Validate it contains a memory index
        index_path = resolved_path / ".memory" / "index.sqlite"
        if not index_path.exists():
            raise FileNotFoundError(f"Parent memory directory missing index: {index_path}")

        # Prevent self-inheritance
        if resolved_path == self.workspace_dir.resolve():
            raise ValueError(
                f"Cannot inherit from own workspace: {resolved_path} == {self.workspace_dir}"
            )

        # Close previous parent index if replacing
        if self._parent_index is not None:
            await self._parent_index.close()

        self.parent_memory_dir = resolved_path
        self._parent_index = HybridMemoryIndex(str(resolved_path))
        logger.info("Configured parent memory inheritance from %s", resolved_path)

    def promote_to_parent(self, filter_fn=None) -> int:
        """Copy selected markdown memories from own bank/ to parent's bank/.

        Uses file-based locking for concurrency safety. After copying,
        re-indexes the parent index for the new files.

        Args:
            filter_fn: Optional callable that takes a Path and returns True
                for files that should be promoted. If None, all ``*.md`` files
                in ``bank/`` are promoted.

        Returns:
            Number of memory files promoted.
        """
        if self.parent_memory_dir is None:
            logger.warning("No parent memory directory configured — nothing to promote")
            return 0

        own_bank = self.workspace_dir / "bank"
        if not own_bank.exists():
            return 0

        parent_bank = self.parent_memory_dir / "bank"
        parent_bank.mkdir(parents=True, exist_ok=True)

        lock_path = self.workspace_dir / ".memory" / "promote.lock"

        return self._promote_with_lock(own_bank, parent_bank, lock_path, filter_fn)

    def _promote_with_lock(
        self,
        own_bank: Path,
        parent_bank: Path,
        lock_path: Path,
        filter_fn,
    ) -> int:
        """Acquire file lock and perform the actual promotion."""
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0

        with open(lock_path, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                for md_file in sorted(own_bank.glob("*.md")):
                    if filter_fn is not None and not filter_fn(md_file):
                        continue
                    dest = parent_bank / md_file.name
                    shutil.copy2(md_file, dest)
                    count += 1

                # Re-index parent for new files
                if (
                    count > 0
                    and self._parent_index is not None
                    and self.parent_memory_dir is not None
                ):
                    for md_file in parent_bank.glob("*.md"):
                        rel = md_file.relative_to(self.parent_memory_dir)
                        self._parent_index.index_file(str(rel))
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)

        if count:
            logger.info("Promoted %d memories to parent %s", count, self.parent_memory_dir)
        return count

    async def _get_entry_temporal_fields(self, file_path: str) -> tuple:
        """Extract valid_from and valid_until from a memory file's frontmatter.

        Args:
            file_path: Relative path to the memory file (e.g., "bank/obs-123.md")

        Returns:
            Tuple of (valid_from, valid_until) as datetime objects or None if not present.
        """
        from datetime import datetime

        import yaml

        full_path = self.workspace_dir / file_path
        if not full_path.exists():
            return None, None

        try:
            content = full_path.read_text()
            # Extract YAML frontmatter
            if content.startswith("---"):
                import yaml

                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml

                    frontmatter = yaml.safe_load(parts[1]) or {}
                    vf = frontmatter.get("valid_from")
                    vu = frontmatter.get("valid_until")
                    vf_dt = datetime.fromisoformat(vf) if vf else None
                    vu_dt = datetime.fromisoformat(vu) if vu else None
                    return vf_dt, vu_dt
        except Exception:
            pass
        return None, None
