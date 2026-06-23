# tests/test_skills.py
"""Tests for the skills system."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

import pytest

from nexusagent.skills import (
    get_skill_content,
    get_skills_summary,
    load_all_skills,
    load_skill,
)


@pytest.fixture
def sample_skill_dir(tmp_path):
    """Create a sample skill directory with SKILL.md."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: test-skill\n"
        "description: A test skill for unit testing\n"
        "---\n"
        "# Test Skill\n\n"
        "This is a test skill.\n\n"
        "## Instructions\n\n"
        "1. Do this\n"
        "2. Do that\n"
    )
    return skill_dir


@pytest.fixture
def sample_skills_dir(tmp_path, sample_skill_dir):
    """Create a skills directory with multiple skills."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Copy sample skill
    import shutil
    shutil.copytree(sample_skill_dir, skills_dir / "test-skill")

    # Create another skill
    skill2_dir = skills_dir / "code-review"
    skill2_dir.mkdir()
    (skill2_dir / "SKILL.md").write_text(
        "---\n"
        "name: code-review\n"
        "description: Review code for quality and security\n"
        "---\n"
        "# Code Review Skill\n\n"
        "Review the code for:\n"
        "- Security issues\n"
        "- Performance problems\n"
        "- Code style\n"
    )

    # Create a skill without frontmatter
    skill3_dir = skills_dir / "simple-skill"
    skill3_dir.mkdir()
    (skill3_dir / "SKILL.md").write_text("# Simple Skill\n\nNo frontmatter here.\n")

    return skills_dir


class TestLoadSkill:
    def test_load_skill_with_frontmatter(self, sample_skill_dir):
        skill = load_skill(sample_skill_dir)
        assert skill is not None
        assert skill.name == "test-skill"
        assert skill.description == "A test skill for unit testing"
        assert "Test Skill" in skill.content
        assert "Instructions" in skill.content

    def test_load_skill_without_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "no-frontmatter"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Simple\n\nContent here.\n")

        skill = load_skill(skill_dir)
        assert skill is not None
        assert skill.name == "no-frontmatter"
        assert skill.description == ""
        assert "Simple" in skill.content

    def test_load_skill_missing_file(self, tmp_path):
        skill_dir = tmp_path / "empty-dir"
        skill_dir.mkdir()

        skill = load_skill(skill_dir)
        assert skill is None


class TestLoadAllSkills:
    def test_load_all_skills(self, sample_skills_dir):
        skills = load_all_skills(sample_skills_dir)
        assert len(skills) == 3
        assert "test-skill" in skills
        assert "code-review" in skills
        assert "simple-skill" in skills

    def test_load_all_skills_empty_dir(self, tmp_path):
        skills_dir = tmp_path / "empty-skills"
        skills_dir.mkdir()

        skills = load_all_skills(skills_dir)
        assert len(skills) == 0

    def test_load_all_skills_nonexistent_dir(self):
        skills = load_all_skills(Path("/nonexistent/path"))
        assert len(skills) == 0

    def test_load_all_skills_skips_hidden(self, sample_skills_dir):
        # Create a hidden directory
        hidden_dir = sample_skills_dir / ".hidden-skill"
        hidden_dir.mkdir()
        (hidden_dir / "SKILL.md").write_text("---\nname: hidden\n---\n# Hidden\n")

        skills = load_all_skills(sample_skills_dir)
        assert "hidden" not in skills


class TestGetSkillsSummary:
    def test_summary_with_skills(self, sample_skills_dir):
        skills = load_all_skills(sample_skills_dir)
        summary = get_skills_summary(skills)

        assert "Available Skills" in summary
        assert "test-skill" in summary
        assert "code-review" in summary
        assert "A test skill for unit testing" in summary

    def test_summary_empty(self):
        summary = get_skills_summary({})
        assert summary == ""


class TestGetSkillContent:
    def test_get_existing_skill(self, sample_skills_dir):
        skills = load_all_skills(sample_skills_dir)
        content = get_skill_content(skills, "test-skill")

        assert content is not None
        assert "Test Skill" in content
        assert "Instructions" in content

    def test_get_missing_skill(self, sample_skills_dir):
        skills = load_all_skills(sample_skills_dir)
        content = get_skill_content(skills, "nonexistent")

        assert content is None


class TestSkillRepr:
    def test_repr(self, sample_skill_dir):
        skill = load_skill(sample_skill_dir)
        assert "test-skill" in repr(skill)
