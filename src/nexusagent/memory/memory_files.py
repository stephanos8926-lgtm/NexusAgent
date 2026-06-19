"""File-based memory layer — canonical source of truth.

Memory layout:
  MEMORY.md              ← index (pointers only, ≤200 lines / 25KB)
  memory/YYYY-MM-DD.md   ← daily log (narrative + ## Retain)
  bank/                  ← curated typed memory pages
    world.md, experience.md, opinions.md, entities/*.md

Each topic file has YAML frontmatter:
  ---
  name: short-name
  description: one-line description (used by search/LLM selection)
  type: world|experience|opinion|observation
  confidence: 0.0-1.0 (opinions only)
  entities: [name1, name2]
  created: ISO-date
  ---

Design principles:
- Files are canonical. The SQLite index is derived and rebuildable.
- MEMORY.md is an index, NOT a store. Never put memory bodies in it.
- Daily logs use ## Retain sections with typed, self-contained bullets.
- Scoped writes: each session can only write to its own workspace.
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from nexusagent.infrastructure.config import settings
from nexusagent.memory.git_ops import MemoryGitOps

logger = logging.getLogger(__name__)

MEMORY_INDEX_MAX_LINES = 200
MEMORY_INDEX_MAX_BYTES = 25_000  # 25KB


# ── TTL helpers ──────────────────────────────────────────────────────────


def _parse_expiry(frontmatter: dict) -> datetime | None:
    """Parse expires_at from frontmatter, returning None if absent or unparseable."""
    expires_at = frontmatter.get("expires_at")
    if not expires_at:
        return None
    try:
        return datetime.fromisoformat(expires_at)
    except (ValueError, TypeError):
        return None


def _is_expired(frontmatter: dict) -> bool:
    """Return True if the entry has an expires_at that is in the past."""
    expiry = _parse_expiry(frontmatter)
    if expiry is None:
        return False
    return datetime.now(UTC) > expiry


class MemoryEntryType(StrEnum):
    """Types of memory entries stored in topic files.

    Each type corresponds to a category of knowledge:
        - WORLD: Objective facts about the environment.
        - EXPERIENCE: Actions the agent has taken.
        - OPINION: Preferences with confidence scores.
        - OBSERVATION: Summaries or generated insights.
    """

    WORLD = "world"  # Objective facts
    EXPERIENCE = "experience"  # What the agent did
    OPINION = "opinion"  # Preferences + confidence
    OBSERVATION = "observation"  # Summary/generated


class FileMemory:
    """File-based memory — canonical source of truth."""

    def __init__(self, workspace_dir: str):
        """Initialize file-backed memory for the given workspace.

        Args:
            workspace_dir: Path to the workspace root. Subdirectories
                ``memory/`` and ``bank/`` are created as needed.
        """
        self.workspace = Path(workspace_dir)
        self.memory_dir = self.workspace / "memory"
        self.bank_dir = self.workspace / "bank"
        self.entities_dir = self.bank_dir / "entities"
        self.index_file = self.workspace / "MEMORY.md"

        # Git ops — non-fatal, enabled via config
        git_enabled = getattr(settings.agent, "memory_git_enabled", True)
        self._git = MemoryGitOps(self.workspace) if git_enabled else None

    def initialize(self):
        """Create the memory directory structure if it doesn't exist."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.bank_dir.mkdir(parents=True, exist_ok=True)
        self.entities_dir.mkdir(parents=True, exist_ok=True)

        if not self.index_file.exists():
            self.index_file.write_text(
                "# Memory Index\n\n"
                "This file is an index of memory entries. Do not edit manually — "
                "use memory_write() to add entries.\n\n"
                "## Entries\n"
            )

        # Create .gitignore in .nexusagent/ if .git/ exists in workspace root
        nexus_dir = self.workspace / ".nexusagent"
        git_dir = self.workspace / ".git"
        if git_dir.is_dir():
            nexus_dir.mkdir(parents=True, exist_ok=True)
            gitignore = nexus_dir / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text("*\n!.gitignore\n")

        # Write .gitignore in memory dir to exclude binary/cache files
        mem_gitignore = self.memory_dir / ".gitignore"
        if not mem_gitignore.exists():
            mem_gitignore.write_text(
                "*.sqlite\n*.db\n__pycache__/\n"
            )

        # Initialize git repo if enabled
        if self._git is not None:
            self._git.init_repo()

    def write_entry(
        self,
        content: str,
        entry_type: MemoryEntryType,
        description: str,
        confidence: float | None = None,
        entities: list[str] | None = None,
        ttl_hours: int | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
    ) -> str:
        """Write a memory entry to a topic file and update the index.

        Args:
            content: The memory content.
            entry_type: Type of memory entry.
            description: Short description/title.
            confidence: Confidence score (for opinion entries).
            entities: Related entity names.
            ttl_hours: Optional TTL in hours. Entry expires after this time.
            valid_from: Optional ISO date when this knowledge becomes valid.
            valid_until: Optional ISO date when this knowledge expires.
        """
        # Generate a filename from the description
        slug = re.sub(r"[^a-z0-9]+", "-", description.lower())[:40].strip("-")
        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        filename = f"{slug}-{timestamp}.md"
        filepath = self.bank_dir / filename

        # Build YAML frontmatter with bi-temporal and quality fields
        now = datetime.now(UTC)
        frontmatter: dict[str, Any] = {
            "name": description[:50],
            "description": description[:100],
            "type": entry_type.value,
            "created": now.isoformat(),
            "quality_score": self._compute_quality_score(content, confidence),
            "retrieval_count": 0,
        }
        if confidence is not None:
            frontmatter["confidence"] = round(confidence, 2)
        if entities:
            frontmatter["entities"] = entities
        if ttl_hours is not None:
            frontmatter["ttl_hours"] = ttl_hours
            frontmatter["expires_at"] = (now + timedelta(hours=ttl_hours)).isoformat()
        if valid_from:
            frontmatter["valid_from"] = valid_from
        if valid_until:
            frontmatter["valid_until"] = valid_until

        # Write topic file
        file_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{content}\n"

        # If file exists, append; otherwise create
        if filepath.exists():
            with open(filepath, "a") as f:
                f.write(f"\n---\n\n{content}\n")
        else:
            filepath.write_text(file_content)

        # Update index with a one-line pointer
        self._add_index_entry(description, filename, entry_type)

        # Update entity pages if entities specified
        if entities:
            for entity in entities:
                self._update_entity(entity, content, entry_type)

        # Auto-commit if enabled
        if self._git is not None and getattr(settings.agent, "memory_git_auto_commit", True):
            self._git.commit(
                f"memory: add {description[:60]}",
                files=[str(filepath.relative_to(self.workspace))],
            )

        return str(filepath)

    @staticmethod
    def _compute_quality_score(content: str, confidence: float | None = None) -> float:
        """Compute initial quality score for a memory entry.

        Based on content length (longer = more detailed) and confidence.
        Score range: 0.0 - 1.0
        """
        # Base score from content length (logarithmic, caps at 1.0 for ~1000 chars)
        import math
        length_score = min(math.log(max(len(content), 1)) / math.log(1000), 1.0)

        # Confidence bonus
        if confidence is not None:
            confidence_score = confidence
        else:
            confidence_score = 0.5  # Default for non-opinion entries

        # Weighted average: 60% length, 40% confidence
        score = 0.6 * length_score + 0.4 * confidence_score
        return round(score, 2)

    def _add_index_entry(self, description: str, filename: str, entry_type: MemoryEntryType):
        """Add a one-line pointer to MEMORY.md."""
        line = f"- [{entry_type.value[0].upper()}] {description} → bank/{filename}\n"

        content = self.index_file.read_text() if self.index_file.exists() else ""
        lines = content.split("\n")

        # Find the "## Entries" section
        entries_start = 0
        for i, ln in enumerate(lines):
            if ln.strip() == "## Entries":
                entries_start = i + 1
                break

        # Insert after the Entries header
        lines.insert(entries_start, line.rstrip())

        # Enforce truncation
        if len(lines) > MEMORY_INDEX_MAX_LINES:
            lines = lines[:MEMORY_INDEX_MAX_LINES]
            lines.append(
                f"\n⚠ Index truncated at {MEMORY_INDEX_MAX_LINES} lines. "
                f"Consolidate entries or move detail to topic files."
            )

        # Enforce byte limit
        content = "\n".join(lines)
        if len(content.encode()) > MEMORY_INDEX_MAX_BYTES:
            # Truncate at last newline before limit
            truncated = content.encode()[:MEMORY_INDEX_MAX_BYTES]
            last_nl = truncated.rfind(b"\n")
            content = truncated[:last_nl].decode("utf-8", errors="ignore")
            content += f"\n⚠ Index truncated to {MEMORY_INDEX_MAX_BYTES} bytes."

        self.index_file.write_text(content)

    def _update_entity(self, entity: str, content: str, entry_type: MemoryEntryType):
        """Update an entity page with a new mention."""
        entity_slug = re.sub(r"[^a-z0-9]+", "-", entity.lower())[:30].strip("-")
        entity_file = self.entities_dir / f"{entity_slug}.md"

        entry = f"- [{entry_type.value[0].upper()}] {content[:100]}\n"

        if entity_file.exists():
            existing = entity_file.read_text()
            # Append after frontmatter
            parts = existing.split("\n---\n", 2)
            if len(parts) >= 2:
                entity_file.write_text(parts[0] + "\n---\n" + parts[1] + entry)
            else:
                entity_file.write_text(existing + entry)
        else:
            frontmatter = {
                "name": entity,
                "type": "entity",
                "created": datetime.now(UTC).isoformat(),
            }
            entity_file.write_text(
                f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n"
                f"# {entity}\n\n{entry}"
            )

    def append_daily_log(self, content: str):
        """Append to today's daily log."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        log_file = self.memory_dir / f"{today}.md"

        timestamp = datetime.now(UTC).strftime("%H:%M")
        entry = f"\n### {timestamp}\n{content}\n"

        if log_file.exists():
            with open(log_file, "a") as f:
                f.write(entry)
        else:
            log_file.write_text(f"# {today}\n\n### Session Start\n{content}\n")

    def get_index_entries(self) -> list[dict]:
        """Parse MEMORY.md and return list of index entries.

        Expired entries (those with ``expires_at`` in the past) are
        silently excluded from the results but are NOT deleted — use
        :meth:`sweep_expired` to physically remove them.
        """
        if not self.index_file.exists():
            return []

        content = self.index_file.read_text()
        entries = []

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- ["):
                # Parse: - [W] description → bank/filename.md
                match = re.match(r"- \[(\w)\] (.+) → (.+)", line)
                if match:
                    entry_file = match.group(3).strip()
                    # Check TTL: skip expired entries
                    if self._entry_is_expired(entry_file):
                        continue
                    entries.append(
                        {
                            "type": match.group(1),
                            "description": match.group(2).strip(),
                            "file": entry_file,
                        }
                    )

        return entries

    def _entry_is_expired(self, relative_path: str) -> bool:
        """Check whether a bank/ entry has expired based on its frontmatter."""
        filepath = self.workspace / relative_path
        if not filepath.exists():
            return False
        try:
            content = filepath.read_text()
            frontmatter = self._parse_frontmatter(content)
            return _is_expired(frontmatter)
        except Exception:
            return False

    @staticmethod
    def _parse_frontmatter(content: str) -> dict:
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

    def read_topic_file(self, filename: str) -> str | None:
        """Read a topic file from the bank/ directory."""
        filepath = self.bank_dir / filename
        if filepath.exists():
            return filepath.read_text()
        return None

    def get_daily_logs(self, days: int = 2) -> list[dict]:
        """Get daily logs for the last N days (today + yesterday by default)."""
        from datetime import timedelta

        logs = []
        for i in range(days):
            date = (datetime.now(UTC) - timedelta(days=i)).strftime("%Y-%m-%d")
            log_file = self.memory_dir / f"{date}.md"
            if log_file.exists():
                content = log_file.read_text()
                # Extract ## Retain section if present
                retain = ""
                if "## Retain" in content:
                    parts = content.split("## Retain")
                    if len(parts) > 1:
                        retain = parts[1].strip()

                logs.append(
                    {
                        "date": date,
                        "content": content,
                        "retain": retain,
                    }
                )

        return logs

    def list_all_files(self) -> list[str]:
        """List all memory files (bank/ + memory/)."""
        files = []
        if self.bank_dir.exists():
            files.extend(str(f.relative_to(self.workspace)) for f in self.bank_dir.rglob("*.md"))
        if self.memory_dir.exists():
            files.extend(str(f.relative_to(self.workspace)) for f in self.memory_dir.glob("*.md"))
        return files

    def delete_by_file(self, relative_path: str) -> bool:
        """Delete a memory file and auto-commit.

        Args:
            relative_path: Relative path of the file (e.g. ``bank/foo.md``).

        Returns:
            True if the file was deleted, False if it didn't exist or deletion failed.
        """
        filepath = self.workspace / relative_path
        if not filepath.exists():
            return False
        try:
            filepath.unlink()
            # Remove from index
            self._remove_index_entry(relative_path)

            # Auto-commit if enabled
            if self._git is not None and getattr(settings.agent, "memory_git_auto_commit", True):
                self._git.commit(
                    f"memory: delete {relative_path}",
                    files=[relative_path],
                )
            return True
        except Exception as e:
            logger.warning("Failed to delete %s: %s", relative_path, e)
            return False

    def sweep_expired(self) -> dict[str, Any]:
        """Physically remove expired memory files and their index entries.

        Scans all ``bank/*.md`` files, checks their ``expires_at`` frontmatter,
        and deletes any that have expired. Corresponding index entries in
        MEMORY.md are also removed.

        Returns a report dict with:
            - expired_found: number of expired entries found
            - files_removed: number of files actually deleted
            - index_entries_removed: number of index lines removed
            - files: list of removed file paths (relative)
        """
        report: dict[str, Any] = {
            "expired_found": 0,
            "files_removed": 0,
            "index_entries_removed": 0,
            "files": [],
        }

        if not self.bank_dir.exists():
            return report

        expired_files: list[str] = []
        for f in self.bank_dir.glob("*.md"):
            try:
                content = f.read_text()
                frontmatter = self._parse_frontmatter(content)
                if _is_expired(frontmatter):
                    rel = str(f.relative_to(self.workspace))
                    expired_files.append(rel)
            except Exception:
                continue

        report["expired_found"] = len(expired_files)

        # Delete expired files and remove their index entries
        for rel_path in expired_files:
            filepath = self.workspace / rel_path
            try:
                filepath.unlink()
                report["files_removed"] += 1
                report["files"].append(rel_path)
                logger.info("Swept expired memory: %s", rel_path)
            except Exception as e:
                logger.warning("Failed to delete expired %s: %s", rel_path, e)
                continue

            # Remove from index
            try:
                self._remove_index_entry(rel_path)
                report["index_entries_removed"] += 1
            except Exception as e:
                logger.warning(
                    "Failed to remove index entry for %s: %s", rel_path, e
                )

        # Auto-commit if enabled
        if (
            report["files_removed"] > 0
            and self._git is not None
            and getattr(settings.agent, "memory_git_auto_commit", True)
        ):
            self._git.commit(
                f"feat(memory): sweep {report['files_removed']} expired entries",
                files=None,  # stage all changes
            )

        return report

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
