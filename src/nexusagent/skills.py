"""
Skills system for NexusAgent.

Loads skills from ~/.nexusagent/skills/ directory. Each skill is a directory
containing a SKILL.md file with YAML frontmatter and markdown content.

Skills are injected into the system prompt so the agent can reference them.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Pattern to extract YAML frontmatter from SKILL.md
_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SkillLoadError(Exception):
    """Raised when a skill cannot be loaded."""

    pass


class Skill:
    """A single loaded skill."""

    def __init__(self, name: str, description: str, content: str, path: Path):
        self.name = name
        self.description = description
        self.content = content
        self.path = path

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r}, description={self.description!r})"


def load_skill(skill_dir: Path) -> Skill | None:
    """Load a single skill from a directory containing SKILL.md."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to read skill %s: %s", skill_dir.name, e)
        return None

    # Parse YAML frontmatter
    name = skill_dir.name
    description = ""
    match = _FRONTMATTER_PATTERN.match(content)
    if match:
        frontmatter = match.group(1)
        for line in frontmatter.split("\n"):
            line = line.strip()
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("description:"):
                desc_val = line.split(":", 1)[1].strip()
                # Handle multiline description (simple approach)
                description = desc_val.strip('"').strip("'")

    # Remove frontmatter from content for injection
    if match:
        body = content[match.end():]
    else:
        body = content

    return Skill(name=name, description=description, content=body.strip(), path=skill_md)


def load_all_skills(skills_dir: Path | None = None) -> dict[str, Skill]:
    """Load all skills from the skills directory.

    Returns a dict of skill_name -> Skill.
    """
    if skills_dir is None:
        skills_dir = Path.home() / ".nexusagent" / "skills"

    skills: dict[str, Skill] = {}

    if not skills_dir.exists():
        logger.debug("Skills directory not found: %s", skills_dir)
        return skills

    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        # Skip hidden dirs and special dirs
        if entry.name.startswith(".") or entry.name.startswith("__"):
            continue

        skill = load_skill(entry)
        if skill:
            skills[skill.name] = skill
            logger.debug("Loaded skill: %s", skill.name)

    logger.info("Loaded %d skills from %s", len(skills), skills_dir)
    return skills


def get_skills_summary(skills: dict[str, Skill]) -> str:
    """Format skills as a summary for the system prompt."""
    if not skills:
        return ""

    lines = ["", "## Available Skills", ""]
    for name, skill in sorted(skills.items()):
        desc = skill.description or "No description"
        lines.append(f"- **{name}**: {desc}")

    lines.append("")
    lines.append("To use a skill, read its SKILL.md file for detailed instructions.")
    return "\n".join(lines)


def get_skill_content(skills: dict[str, Skill], name: str) -> str | None:
    """Get the full content of a specific skill."""
    skill = skills.get(name)
    if skill is None:
        return None
    return f"---\nname: {skill.name}\ndescription: {skill.description}\n---\n\n{skill.content}"
