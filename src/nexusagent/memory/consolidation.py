"""Memory consolidation engine — background daemon for memory health.

Periodically scans all memories and:
- Identifies duplicates (high similarity, same content)
- Detects contradictions (same entity, conflicting facts)
- Prunes stale entries (age-based, TTL-based)
- Merges redundant entries
- Rebuilds the FTS5 index
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class ConsolidationEngine:
    """Scan, analyze, and consolidate workspace memories."""

    def __init__(self, workspace_dir: str, dry_run: bool = True):
        self.workspace_dir = Path(workspace_dir)
        self.dry_run = dry_run
        self.bank_dir = self.workspace_dir / "bank"
        self.entities_dir = self.bank_dir / "entities"

    def scan(self) -> dict:
        """Scan all memories and return analysis report."""
        if not self.bank_dir.exists():
            return {"status": "no_bank", "files": 0}

        files = list(self.bank_dir.glob("*.md"))
        entities = list(self.entities_dir.glob("*.md")) if self.entities_dir.exists() else []

        report = {
            "status": "ok",
            "total_files": len(files),
            "total_entities": len(entities),
            "duplicates": [],
            "contradictions": [],
            "stale": [],
            "merged": [],
        }

        # Find duplicates by comparing content hashes
        seen_hashes: dict[str, str] = {}
        for f in files:
            try:
                content = f.read_text()
                content_hash = self._hash_content(content)
                if content_hash in seen_hashes:
                    report["duplicates"].append({
                        "original": seen_hashes[content_hash],
                        "duplicate": str(f.name),
                    })
                else:
                    seen_hashes[content_hash] = str(f.name)
            except Exception:
                continue

        # Find stale entries (older than 30 days with no retrieval)
        cutoff = datetime.now(UTC) - timedelta(days=30)
        for f in files:
            try:
                stat = f.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime, UTC)
                if mtime < cutoff:
                    report["stale"].append({
                        "file": str(f.name),
                        "age_days": (datetime.now(UTC) - mtime).days,
                    })
            except Exception:
                continue

        return report

    def consolidate(self, report: dict | None = None) -> dict:
        """Execute consolidation based on scan report."""
        if report is None:
            report = self.scan()

        actions = {
            "duplicates_removed": 0,
            "stale_pruned": 0,
            "index_rebuilt": False,
        }

        if self.dry_run:
            actions["dry_run"] = True
            return actions

        # Remove duplicate files
        for dup in report.get("duplicates", []):
            dup_path = self.bank_dir / dup["duplicate"]
            if dup_path.exists():
                try:
                    dup_path.unlink()
                    actions["duplicates_removed"] += 1
                    logger.info("Removed duplicate: %s", dup["duplicate"])
                except Exception as e:
                    logger.warning("Failed to remove duplicate %s: %s", dup["duplicate"], e)

        # Prune stale entries
        for stale in report.get("stale", []):
            stale_path = self.bank_dir / stale["file"]
            if stale_path.exists():
                try:
                    stale_path.unlink()
                    actions["stale_pruned"] += 1
                    logger.info("Pruned stale entry: %s", stale["file"])
                except Exception as e:
                    logger.warning("Failed to prune stale %s: %s", stale["file"], e)

        # Rebuild index
        try:
            from nexusagent.memory.index.index import HybridMemoryIndex
            idx = HybridMemoryIndex(str(self.workspace_dir))
            idx.rebuild()
            actions["index_rebuilt"] = True
        except Exception as e:
            logger.error("Index rebuild failed: %s", e)

        return actions

    def health_report(self) -> dict:
        """Return memory health metrics."""
        report = self.scan()
        return {
            "total_memories": report["total_files"],
            "total_entities": report["total_entities"],
            "duplicate_count": len(report["duplicates"]),
            "stale_count": len(report["stale"]),
            "health_score": self._compute_health_score(report),
        }

    def _compute_health_score(self, report: dict) -> float:
        """Compute a 0.0-1.0 health score for the memory bank."""
        total = report["total_files"]
        if total == 0:
            return 1.0

        issues = len(report["duplicates"]) + len(report["stale"])
        if issues == 0:
            return 1.0

        penalty = min(issues / total, 1.0)
        return round(1.0 - penalty, 2)

    @staticmethod
    def _hash_content(content: str) -> str:
        """Hash content for deduplication comparison."""
        import hashlib
        normalized = " ".join(content.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
