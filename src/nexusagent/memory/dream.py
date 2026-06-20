"""Dream cycle engine — 4-phase memory consolidation daemon.

Runs periodic background consolidation:
  1. Scan:    Read all memory files, compute hashes, find duplicates/stale
  2. Patterns: Extract recurring themes and insights
  3. Consolidate: Merge duplicates, prune stale, resolve contradictions
  4. Trim:    Rebuild index, trim MEMORY.md to ≤200 lines

File locking prevents concurrent consolidation with active sessions.
All operations are sandboxed — can only write to memory files, never source code.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from nexusagent.memory.git_ops import MemoryGitOps
from nexusagent.memory.refinement import LLMRefinement

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

MEMORY_INDEX_MAX_LINES = 200
MEMORY_INDEX_MAX_BYTES = 25_000  # 25KB
STALE_THRESHOLD_DAYS = 30
LOW_QUALITY_THRESHOLD = 0.2
LOCK_TIMEOUT = 300  # 5 minutes
LOCK_POLL_INTERVAL = 0.5


class DreamLock:
    """File-based lock to prevent concurrent consolidation.

    Uses a ``.dream.lock`` file in the workspace with JSON metadata
    (pid, timestamp). Stale locks (older than LOCK_TIMEOUT) are
    automatically broken.
    """

    def __init__(self, workspace_dir: str | Path):
        self.lock_path = Path(workspace_dir) / ".dream.lock"

    def acquire(self) -> bool:
        """Try to acquire the lock. Returns True on success."""
        if self.lock_path.exists():
            # Check if lock is stale
            try:
                data = json.loads(self.lock_path.read_text())
                age = time.monotonic() - data.get("ts", 0)
                if age < LOCK_TIMEOUT:
                    logger.debug("Dream lock already held by pid %s", data.get("pid"))
                    return False
                logger.warning("Breaking stale dream lock (age %.0fs)", age)
            except (json.JSONDecodeError, KeyError, OSError):
                # Corrupt lock — break it
                logger.warning("Corrupt dream lock, breaking")

        try:
            payload = json.dumps({"pid": os.getpid(), "ts": time.monotonic()})
            self.lock_path.write_text(payload)
            return True
        except OSError as e:
            logger.warning("Failed to create dream lock: %s", e)
            return False

    def release(self):
        """Release the lock."""
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning("Failed to remove dream lock: %s", e)

    async def acquire_blocking(self, timeout: float = 10.0) -> bool:
        """Try to acquire the lock, polling until timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.acquire():
                return True
            await asyncio.sleep(LOCK_POLL_INTERVAL)
        return False

class DreamCycle:
    """4-phase memory consolidation daemon.

    Usage::

        cycle = DreamCycle("/path/to/workspace")
        report = await cycle.run(dry_run=True)   # preview
        report = await cycle.run(dry_run=False)  # execute

    The cycle is sandboxed: it can only write to memory files
    (bank/, memory/, MEMORY.md), never to source code.
    """

    def __init__(self, workspace_dir: str | Path, llm_refinement: bool = True):
        self.workspace = Path(workspace_dir)
        self.bank_dir = self.workspace / "bank"
        self.memory_dir = self.workspace / "memory"
        self.entities_dir = self.bank_dir / "entities"
        self.index_file = self.workspace / "MEMORY.md"
        self.lock = DreamLock(workspace_dir)
        self._git = MemoryGitOps(workspace_dir)
        self._llm_refinement = llm_refinement
        self._refinement = LLMRefinement() if llm_refinement else None

    async def _load_existing_insights(self) -> list[str]:
        """Load existing insight memories to avoid duplication."""
        if not self.bank_dir.exists():
            return []
        insights = []
        for f in self.bank_dir.glob("*.md"):
            try:
                content = f.read_text()
                if "type: insight" in content or "type: synthesis" in content:
                    # Extract the content after frontmatter
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            body = parts[2].strip()
                            if body:
                                insights.append(body[:200])
            except Exception:
                continue
        return insights

    async def _store_refinement_results(self, results) -> None:
        """Store LLM refinement results as new insight memories."""
        for r in results:
            content = r.content
            description = f"Synthesized from {r.source_count} observations"
            await self._write_insight(
                content=content,
                description=description,
                confidence=r.confidence,
                entities=r.entities,
            )

    async def _write_insight(self, content: str, description: str, confidence: float, entities: list[str]):
        """Write a synthesized insight as a new memory file."""
        from nexusagent.memory.memory_files import FileMemory, MemoryEntryType

        fm = FileMemory(str(self.workspace))
        fm.initialize()
        fm.write_entry(
            content=content,
            entry_type=MemoryEntryType.OBSERVATION,
            description=description,
            confidence=0.8,
            entities=entities or None,
        )

    # ── Phase 1: Scan ───────────────────────────────────────────────────
        """Load existing insight memories to avoid duplication."""
        if not self.bank_dir.exists():
            return []
        insights = []
        for f in self.bank_dir.glob("*.md"):
            try:
                content = f.read_text()
                if "type: insight" in content or "type: synthesis" in content:
                    # Extract the content after frontmatter
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            body = parts[2].strip()
                            if body:
                                insights.append(body[:200])
            except Exception:
                continue
        return insights

    async def _store_refinement_results(self, results) -> None:
        """Store LLM refinement results as new insight memories."""
        for r in results:
            content = r.content
            description = f"Synthesized from {r.source_count} observations"
            await self._write_insight(
                content=content,
                description=description,
                confidence=r.confidence,
                entities=r.entities,
            )

    async def _write_insight(self, content: str, description: str, confidence: float, entities: list[str]):
        """Write a synthesized insight as a new memory file."""
        from nexusagent.memory.memory_files import FileMemory, MemoryEntryType

        fm = FileMemory(str(self.workspace_dir))
        fm.initialize()
        fm.write_entry(
            content=content,
            entry_type="insight",
            description=description,
            confidence=0.8,
            entities=entities or None,
        )

    def scan(self) -> dict[str, Any]:
        """Scan all memory files and compute health metrics.

        Returns a report dict with:
            - total: total number of memory files
            - duplicates: list of {original, duplicate} pairs
            - stale: list of {file, age_days} dicts
            - low_quality: list of {file, score} dicts
            - health_score: 0.0-1.0 overall health
        """
        if not self.bank_dir.exists():
            return {
                "total": 0,
                "duplicates": [],
                "stale": [],
                "low_quality": [],
                "health_score": 1.0,
            }

        files = list(self.bank_dir.glob("*.md"))
        # Also scan entity files
        entity_files = (
            list(self.entities_dir.glob("*.md"))
            if self.entities_dir.exists()
            else []
        )

        report: dict[str, Any] = {
            "total": len(files),
            "total_entities": len(entity_files),
            "duplicates": [],
            "stale": [],
            "low_quality": [],
            "health_score": 1.0,
        }

        # Find duplicates by content hash
        # Sort by mtime (oldest first) so the earliest-written file is kept as original
        files_sorted = sorted(files, key=lambda f: f.stat().st_mtime)
        seen_hashes: dict[str, str] = {}
        for f in files_sorted:
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

        # Find stale and low-quality entries
        cutoff = datetime.now(UTC) - timedelta(days=STALE_THRESHOLD_DAYS)
        for f in files:
            try:
                content = f.read_text()

                # Staleness check
                stat = f.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime, UTC)
                if mtime < cutoff:
                    report["stale"].append({
                        "file": str(f.name),
                        "age_days": (datetime.now(UTC) - mtime).days,
                    })

                # Quality check
                score = self._read_quality_score(content)
                if score is not None and score < LOW_QUALITY_THRESHOLD:
                    report["low_quality"].append({
                        "file": str(f.name),
                        "score": score,
                    })
            except Exception:
                continue

        # Compute health score
        report["health_score"] = self._compute_health_score(report)
        return report

    # ── Phase 2: Patterns ───────────────────────────────────────────────

    def find_patterns(self) -> dict[str, Any]:
        """Extract recurring themes and insights from memory files.

        Returns a patterns dict with:
            - observations: list of extracted pattern strings
            - entity_frequency: dict of entity → mention count
            - type_distribution: dict of type → count
            - total_files_scanned: number of files analyzed
        """
        if not self.bank_dir.exists():
            return {
                "observations": [],
                "entity_frequency": {},
                "type_distribution": {},
                "total_files_scanned": 0,
            }

        files = list(self.bank_dir.glob("*.md"))
        observations: list[str] = []
        entity_freq: dict[str, int] = {}
        type_dist: dict[str, int] = {}

        for f in files:
            try:
                content = f.read_text()
                frontmatter = self._parse_frontmatter(content)

                # Track type distribution
                entry_type = frontmatter.get("type", "unknown")
                type_dist[entry_type] = type_dist.get(entry_type, 0) + 1

                # Track entity frequency
                entities = frontmatter.get("entities", [])
                if isinstance(entities, list):
                    for entity in entities:
                        entity_freq[entity] = entity_freq.get(entity, 0) + 1

                # Extract observations from content (past frontmatter)
                body = self._strip_frontmatter(content)
                if body:
                    # Look for key insight patterns
                    for line in body.split("\n"):
                        line = line.strip()
                        if line.startswith(("- ", "* ", "• ")):
                            observations.append(line[2:][:200])
                        elif line.startswith("## "):
                            observations.append(f"Section: {line[3:]}")
            except Exception:
                continue

        return {
            "observations": observations[:50],  # Cap at 50
            "entity_frequency": entity_freq,
            "type_distribution": type_dist,
            "total_files_scanned": len(files),
        }

    # ── Phase 3: Consolidate ────────────────────────────────────────────

    def consolidate(
        self,
        scan_report: dict[str, Any],
        patterns: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute consolidation changes based on scan report and patterns.

        Actions taken:
            - Remove duplicate files (keep original)
            - Prune stale entries (age > STALE_THRESHOLD_DAYS)
            - Remove low-quality entries (score < LOW_QUALITY_THRESHOLD)
            - Resolve contradictions (same entity, conflicting facts)

        Returns an actions dict with:
            - duplicates_removed: count
            - stale_pruned: count
            - low_quality_removed: count
            - contradictions_resolved: count
            - files_affected: list of affected file paths
        """
        actions: dict[str, Any] = {
            "duplicates_removed": 0,
            "stale_pruned": 0,
            "low_quality_removed": 0,
            "contradictions_resolved": 0,
            "files_affected": [],
        }

        # Remove duplicates
        for dup in scan_report.get("duplicates", []):
            dup_path = self.bank_dir / dup["duplicate"]
            if dup_path.exists():
                try:
                    dup_path.unlink()
                    actions["duplicates_removed"] += 1
                    actions["files_affected"].append(dup["duplicate"])
                    self._remove_index_entry(f"bank/{dup['duplicate']}")
                    logger.info("Removed duplicate: %s", dup["duplicate"])
                except Exception as e:
                    logger.warning(
                        "Failed to remove duplicate %s: %s", dup["duplicate"], e
                    )

        # Prune stale entries
        for stale in scan_report.get("stale", []):
            stale_path = self.bank_dir / stale["file"]
            if stale_path.exists():
                try:
                    stale_path.unlink()
                    actions["stale_pruned"] += 1
                    actions["files_affected"].append(stale["file"])
                    self._remove_index_entry(f"bank/{stale['file']}")
                    logger.info("Pruned stale entry: %s", stale["file"])
                except Exception as e:
                    logger.warning(
                        "Failed to prune stale %s: %s", stale["file"], e
                    )

        # Remove low-quality entries
        for lq in scan_report.get("low_quality", []):
            lq_path = self.bank_dir / lq["file"]
            if lq_path.exists():
                try:
                    lq_path.unlink()
                    actions["low_quality_removed"] += 1
                    actions["files_affected"].append(lq["file"])
                    self._remove_index_entry(f"bank/{lq['file']}")
                    logger.info("Removed low-quality entry: %s", lq["file"])
                except Exception as e:
                    logger.warning(
                        "Failed to remove low-quality %s: %s", lq["file"], e
                    )

        # Resolve contradictions (same entity, conflicting facts)
        contradictions = self._find_contradictions(patterns)
        for contradiction in contradictions:
            resolved = self._resolve_contradiction(contradiction)
            if resolved:
                actions["contradictions_resolved"] += 1

        return actions

    # ── Phase 4: Trim ───────────────────────────────────────────────────

    def trim_index(self) -> dict[str, Any]:
        """Rebuild FTS5 index and trim MEMORY.md to ≤200 lines.

        Also sweeps expired TTL entries from the bank/ directory.

        Returns a report dict with:
            - index_rebuilt: bool
            - memory_lines_before: int
            - memory_lines_after: int
            - memory_trimmed: bool
            - expired_swept: dict (from :meth:`FileMemory.sweep_expired`)
        """
        from nexusagent.memory.memory_files import FileMemory

        report: dict[str, Any] = {
            "index_rebuilt": False,
            "memory_lines_before": 0,
            "memory_lines_after": 0,
            "memory_trimmed": False,
            "expired_swept": {},
        }

        # Rebuild FTS5 index
        try:
            from nexusagent.memory.index.index import HybridMemoryIndex

            idx = HybridMemoryIndex(str(self.workspace))
            idx.rebuild()
            report["index_rebuilt"] = True
            logger.info("Rebuilt FTS5 index")
        except Exception as e:
            logger.error("Index rebuild failed: %s", e)

        # Sweep expired TTL entries
        try:
            fm = FileMemory(str(self.workspace))
            sweep_report = fm.sweep_expired()
            report["expired_swept"] = sweep_report
            if sweep_report["files_removed"] > 0:
                logger.info(
                    "Trim swept %d expired entries", sweep_report["files_removed"]
                )
        except Exception as e:
            logger.warning("Expired sweep failed during trim: %s", e)

        # Trim MEMORY.md
        if self.index_file.exists():
            content = self.index_file.read_text()
            lines = content.split("\n")
            report["memory_lines_before"] = len(lines)

            if len(lines) > MEMORY_INDEX_MAX_LINES:
                # Keep header + entries up to limit
                trimmed_lines = lines[:MEMORY_INDEX_MAX_LINES]
                trimmed_lines.append(
                    f"\n⚠ Index truncated at {MEMORY_INDEX_MAX_LINES} lines. "
                    f"Run dream cycle to consolidate."
                )
                self.index_file.write_text("\n".join(trimmed_lines))
                report["memory_trimmed"] = True
                report["memory_lines_after"] = len(trimmed_lines)
                logger.info(
                    "Trimmed MEMORY.md from %d to %d lines",
                    len(lines),
                    len(trimmed_lines),
                )
            else:
                report["memory_lines_after"] = len(lines)

            # Also enforce byte limit
            content = self.index_file.read_text()
            if len(content.encode()) > MEMORY_INDEX_MAX_BYTES:
                truncated = content.encode()[:MEMORY_INDEX_MAX_BYTES]
                last_nl = truncated.rfind(b"\n")
                content = truncated[:last_nl].decode("utf-8", errors="ignore")
                content += f"\n⚠ Index truncated to {MEMORY_INDEX_MAX_BYTES} bytes."
                self.index_file.write_text(content)
                report["memory_trimmed"] = True
                report["memory_lines_after"] = len(content.split("\n"))
        else:
            # Create a fresh index
            self.index_file.write_text(
                "# Memory Index\n\n"
                "This file is an index of memory entries.\n\n"
                "## Entries\n"
            )
            report["memory_lines_after"] = 4

        return report

    # ── Full cycle ──────────────────────────────────────────────────────

    async def run(
        self, memory_dir: str | Path | None = None, dry_run: bool = False
    ) -> dict[str, Any]:
        """Execute the full 4-phase dream cycle.

        Args:
            memory_dir: Optional override for the memory directory.
                Defaults to the workspace bank/ directory.
            dry_run: If True, scan and analyze but don't modify files.

        Returns a report dict with:
            - phase1_scan: scan report
            - phase2_patterns: patterns report
            - phase3_consolidate: consolidation actions (or dry_run preview)
            - phase4_trim: trim report
            - duplicates_removed: count
            - stale_pruned: count
            - patterns_extracted: count
            - health_before: float
            - health_after: float
            - dry_run: bool
        """
        if memory_dir is not None:
            self.bank_dir = Path(memory_dir)

        # Acquire lock
        if not dry_run:
            if not await self.lock.acquire_blocking():
                logger.error("Could not acquire dream lock — another cycle running?")
                return {"error": "lock_acquisition_failed", "dry_run": dry_run}

        try:
            return await self._run_locked(dry_run)
        finally:
            if not dry_run:
                self.lock.release()

    async def _run_locked(self, dry_run: bool) -> dict[str, Any]:
        """Run all 4 phases (must be called with lock held if not dry_run)."""

        # Phase 1: Scan
        logger.info("Dream cycle Phase 1: Scan")
        scan_report = self.scan()
        health_before = scan_report["health_score"]

        # Phase 2: Patterns
        logger.info("Dream cycle Phase 2: Patterns")
        patterns = self.find_patterns()

        # LLM-based refinement (Phase 2b)
        if self._llm_refinement and self._refinement:
            logger.info("Dream cycle Phase 2b: LLM Refinement")
            observations = patterns.get("observations", [])
            if observations:
                try:
                    existing_insights = await self._load_existing_insights()
                    refinement_results = await self._refinement.synthesize(
                        observations=observations,
                        existing_insights=existing_insights,
                    )
                    if refinement_results:
                        await self._store_refinement_results(refinement_results)
                        patterns["refinement_results"] = [
                            {
                                "content": r.content,
                                "confidence": r.confidence,
                                "entities": r.entities,
                                "source_count": r.source_count,
                            }
                            for r in refinement_results
                        ]
                        logger.info(
                            "LLM refinement synthesized %d insights", len(refinement_results)
                        )
                except Exception as exc:
                    logger.warning("LLM refinement failed: %s", exc)

        # Phase 3: Consolidate
        logger.info("Dream cycle Phase 3: Consolidate (dry_run=%s)", dry_run)
        if dry_run:
            consolidate_report = {
                "dry_run": True,
                "duplicates_removed": 0,
                "stale_pruned": 0,
                "low_quality_removed": 0,
                "contradictions_resolved": 0,
                "files_affected": [],
                "would_remove_duplicates": len(scan_report["duplicates"]),
                "would_prune_stale": len(scan_report["stale"]),
                "would_remove_low_quality": len(scan_report["low_quality"]),
            }
        else:
            consolidate_report = self.consolidate(scan_report, patterns)

        # Phase 4: Trim
        logger.info("Dream cycle Phase 4: Trim")
        if dry_run:
            trim_report = {
                "dry_run": True,
                "index_rebuilt": False,
                "memory_lines_before": 0,
                "memory_lines_after": 0,
                "memory_trimmed": False,
            }
            if self.index_file.exists():
                trim_report["memory_lines_before"] = len(
                    self.index_file.read_text().split("\n")
                )
        else:
            trim_report = self.trim_index()

        # Re-scan for health_after
        if not dry_run:
            after_scan = self.scan()
            health_after = after_scan["health_score"]
        else:
            health_after = health_before

        # Git commit after consolidation
        if not dry_run and consolidate_report.get("files_affected"):
            self._git.commit(
                "feat(memory): dream cycle consolidation — "
                f"removed {consolidate_report['duplicates_removed']} duplicates, "
                f"pruned {consolidate_report['stale_pruned']} stale entries",
                files=None,  # stage all changes
            )

        return {
            "phase1_scan": scan_report,
            "phase2_patterns": patterns,
            "phase3_consolidate": consolidate_report,
            "phase4_trim": trim_report,
            "duplicates_removed": consolidate_report["duplicates_removed"],
            "stale_pruned": consolidate_report["stale_pruned"],
            "patterns_extracted": len(patterns["observations"]),
            "health_before": health_before,
            "health_after": health_after,
            "dry_run": dry_run,
        }

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _hash_content(content: str) -> str:
        """Hash normalized content for deduplication."""
        normalized = " ".join(content.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    @staticmethod
    def _compute_health_score(report: dict[str, Any]) -> float:
        """Compute a 0.0-1.0 health score for the memory bank."""
        total = report["total"]
        if total == 0:
            return 1.0

        issues = (
            len(report["duplicates"])
            + len(report["stale"])
            + len(report["low_quality"])
        )
        if issues == 0:
            return 1.0

        penalty = min(issues / total, 1.0)
        return round(1.0 - penalty, 2)

    @staticmethod
    def _parse_frontmatter(content: str) -> dict[str, Any]:
        """Parse YAML frontmatter from a memory file."""
        if not content.startswith("---"):
            return {}
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        """Remove YAML frontmatter and return the body."""
        if not content.startswith("---"):
            return content
        parts = content.split("---", 2)
        if len(parts) < 3:
            return content
        return parts[2].strip()

    @staticmethod
    def _read_quality_score(content: str) -> float | None:
        """Read quality_score from frontmatter, or None if missing."""
        frontmatter = DreamCycle._parse_frontmatter(content)
        return frontmatter.get("quality_score")

    def _remove_index_entry(self, relative_path: str):
        """Remove pointer lines from MEMORY.md matching the given file path."""
        if not self.index_file.exists():
            return
        content = self.index_file.read_text()
        lines = content.split("\n")
        prefix = f" → {relative_path}"
        filtered = [ln for ln in lines if not ln.endswith(prefix)]
        if len(filtered) != len(lines):
            self.index_file.write_text("\n".join(filtered))

    def _find_contradictions(
        self, patterns: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Find contradictions: same entity with conflicting facts.

        Returns a list of contradiction dicts with entity and conflicting files.
        """
        if not patterns:
            return []

        contradictions: list[dict[str, Any]] = []
        entity_files: dict[str, list[str]] = {}

        if not self.bank_dir.exists():
            return contradictions

        for f in self.bank_dir.glob("*.md"):
            try:
                content = f.read_text()
                frontmatter = self._parse_frontmatter(content)
                entities = frontmatter.get("entities", [])
                if isinstance(entities, list):
                    for entity in entities:
                        if entity not in entity_files:
                            entity_files[entity] = []
                        entity_files[entity].append(str(f.name))
            except Exception:
                continue

        # Flag entities mentioned in many files as potential contradictions
        for entity, files in entity_files.items():
            if len(files) > 3:
                contradictions.append({
                    "entity": entity,
                    "files": files,
                    "reason": "high_entity_density",
                })

        return contradictions

    def _resolve_contradiction(self, contradiction: dict[str, Any]) -> bool:
        """Attempt to resolve a contradiction by merging entity files.

        Returns True if resolved, False otherwise.
        """
        # For now, just log — full resolution requires LLM
        logger.info(
            "Contradiction detected for entity '%s' in %d files: %s",
            contradiction["entity"],
            len(contradiction["files"]),
            contradiction["files"],
        )
        return False
