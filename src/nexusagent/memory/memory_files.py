"""
File-based memory layer — canonical source of truth.

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
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

MEMORY_INDEX_MAX_LINES = 200
MEMORY_INDEX_MAX_BYTES = 25_000  # 25KB


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

    def write_entry(
        self,
        content: str,
        entry_type: MemoryEntryType,
        description: str,
        confidence: float | None = None,
        entities: list[str] | None = None,
    ) -> str:
        """Write a memory entry to a topic file and update the index.

        Returns the path of the topic file.
        """
        # Generate a filename from the description
        slug = re.sub(r"[^a-z0-9]+", "-", description.lower())[:40].strip("-")
        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        filename = f"{slug}-{timestamp}.md"
        filepath = self.bank_dir / filename

        # Build YAML frontmatter
        frontmatter: dict[str, Any] = {
            "name": description[:50],
            "description": description[:100],
            "type": entry_type.value,
            "created": datetime.now(UTC).isoformat(),
        }
        if confidence is not None:
            frontmatter["confidence"] = round(confidence, 2)
        if entities:
            frontmatter["entities"] = entities

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

        return str(filepath)

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
        """Parse MEMORY.md and return list of index entries."""
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
                    entries.append(
                        {
                            "type": match.group(1),
                            "description": match.group(2).strip(),
                            "file": match.group(3).strip(),
                        }
                    )

        return entries

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
