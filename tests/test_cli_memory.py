"""Tests for the 'nexus memory health' and 'nexus memory stats' CLI commands.

Tests cover:
1. memory health command shows expected health metrics
2. memory stats command shows type distribution and git commit count
3. Both commands handle empty workspaces gracefully
4. Both commands accept --workspace argument
"""

import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from nexusagent.interfaces.cli import main


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_workspace():
    """Create a temporary workspace with bank/ directory and git repo."""
    d = tempfile.mkdtemp()
    # Initialize git repo so stats command can count commits
    subprocess.run(["git", "init"], cwd=d, capture_output=True, timeout=10)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=d, capture_output=True, timeout=10,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=d, capture_output=True, timeout=10,
    )
    # Create initial commit
    Path(d, ".gitkeep").touch()
    subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True, timeout=10)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=d, capture_output=True, timeout=10,
    )
    yield d
    shutil.rmtree(d)


def _write_memory(workspace, name="test-entry", content="Test content",
                  entry_type="world", description="Test desc",
                  entities=None, confidence=None, quality_score=None):
    """Helper to write a test memory entry with YAML frontmatter."""
    bank_dir = os.path.join(workspace, "bank")
    os.makedirs(bank_dir, exist_ok=True)
    filepath = os.path.join(bank_dir, f"{name}.md")

    fm_lines = ["---"]
    fm_lines.append(f'name: "{name}"')
    fm_lines.append(f"description: {description}")
    fm_lines.append(f"type: {entry_type}")
    fm_lines.append(f"created: {datetime.now(UTC).isoformat()}")
    if confidence is not None:
        fm_lines.append(f"confidence: {confidence}")
    if quality_score is not None:
        fm_lines.append(f"quality_score: {quality_score}")
    if entities:
        fm_lines.append(f"entities: [{', '.join(entities)}]")
    fm_lines.append("---")
    fm_lines.append("")
    fm_lines.append(content)

    with open(filepath, "w") as f:
        f.write("\n".join(fm_lines) + "\n")

    return filepath


# ── memory health command tests ──────────────────────────────────────────


class TestMemoryHealthCommand:
    def test_health_help(self):
        """memory health --help should exit successfully."""
        runner = CliRunner()
        result = runner.invoke(main, ["memory", "health", "--help"])
        assert result.exit_code == 0
        assert "workspace" in result.output.lower()

    def test_health_empty_workspace(self, tmp_workspace):
        """Health command on empty workspace should show zero counts."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "health", "--workspace", tmp_workspace]
        )
        assert result.exit_code == 0
        assert "MEMORY HEALTH REPORT" in result.output
        assert "Total Memories:   0" in result.output
        assert "Health Score:      100% [GOOD]" in result.output

    def test_health_shows_memories(self, tmp_workspace):
        """Health command should show correct total memory count."""
        _write_memory(tmp_workspace, name="m1", content="First memory")
        _write_memory(tmp_workspace, name="m2", content="Second memory")

        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "health", "--workspace", tmp_workspace]
        )
        assert result.exit_code == 0
        assert "Total Memories:   2" in result.output
        assert "Duplicates:        0" in result.output

    def test_health_shows_duplicates(self, tmp_workspace):
        """Health command should detect and report duplicates."""
        # Write two identical files
        content = (
            "---\n"
            'name: "dup"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "Identical content here\n"
        )
        bank_dir = os.path.join(tmp_workspace, "bank")
        os.makedirs(bank_dir, exist_ok=True)
        with open(os.path.join(bank_dir, "orig.md"), "w") as f:
            f.write(content)
        with open(os.path.join(bank_dir, "copy.md"), "w") as f:
            f.write(content)

        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "health", "--workspace", tmp_workspace]
        )
        assert result.exit_code == 0
        assert "Duplicates:        1" in result.output
        assert "copy.md" in result.output
        assert "original: orig.md" in result.output

    def test_health_shows_type_distribution(self, tmp_workspace):
        """Health command should display type distribution."""
        _write_memory(tmp_workspace, name="w1", entry_type="world", content="Fact")
        _write_memory(tmp_workspace, name="w2", entry_type="world", content="Fact2")
        _write_memory(tmp_workspace, name="o1", entry_type="opinion", content="Opinion")

        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "health", "--workspace", tmp_workspace]
        )
        assert result.exit_code == 0
        assert "Type Distribution" in result.output
        assert "world" in result.output
        assert "opinion" in result.output

    def test_health_shows_entities(self, tmp_workspace):
        """Health command should display top entities."""
        _write_memory(
            tmp_workspace, name="e1", content="First",
            entities=["auth", "jwt"],
        )
        _write_memory(
            tmp_workspace, name="e2", content="Second",
            entities=["auth", "oauth"],
        )

        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "health", "--workspace", tmp_workspace]
        )
        assert result.exit_code == 0
        assert "Top Entities" in result.output
        assert "auth" in result.output

    def test_health_invalid_workspace(self):
        """Health command should error on invalid workspace path."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "health", "--workspace", "/nonexistent/path/xyz"]
        )
        assert result.exit_code != 0

    def test_health_default_workspace(self):
        """Health command with no --workspace should default to current dir."""
        runner = CliRunner()
        # Just verify command does not crash (may show empty or real workspace)
        result = runner.invoke(main, ["memory", "health"])
        # Exit code 0 or 1 depending on whether CWD has valid directory
        assert result.exit_code in (0, 1)


# ── memory stats command tests ──────────────────────────────────────────


class TestMemoryStatsCommand:
    def test_stats_help(self):
        """memory stats --help should exit successfully."""
        runner = CliRunner()
        result = runner.invoke(main, ["memory", "stats", "--help"])
        assert result.exit_code == 0
        assert "workspace" in result.output.lower()

    def test_stats_empty_workspace(self, tmp_workspace):
        """Stats command on empty workspace should show zero counts."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "stats", "--workspace", tmp_workspace]
        )
        assert result.exit_code == 0
        assert "MEMORY STATISTICS" in result.output
        assert "Total Memory Files:  0" in result.output
        assert "No memory files found." in result.output

    def test_stats_shows_type_distribution(self, tmp_workspace):
        """Stats command should show memory count by type."""
        _write_memory(tmp_workspace, name="w1", entry_type="world", content="Fact")
        _write_memory(tmp_workspace, name="w2", entry_type="world", content="Fact2")
        _write_memory(tmp_workspace, name="o1", entry_type="opinion", content="Opinion")

        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "stats", "--workspace", tmp_workspace]
        )
        assert result.exit_code == 0
        assert "Memory Count by Type" in result.output
        assert "world" in result.output
        assert "2" in result.output
        assert "opinion" in result.output

    def test_stats_shows_confidence(self, tmp_workspace):
        """Stats command should show average confidence."""
        _write_memory(tmp_workspace, name="c1", content="A", confidence=0.8)
        _write_memory(tmp_workspace, name="c2", content="B", confidence=0.6)

        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "stats", "--workspace", tmp_workspace]
        )
        assert result.exit_code == 0
        assert "Average Confidence:" in result.output
        assert "0.70" in result.output

    def test_stats_shows_git_commits(self, tmp_workspace):
        """Stats command should show git commit count."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "stats", "--workspace", tmp_workspace]
        )
        assert result.exit_code == 0
        assert "Git History" in result.output
        assert "Memory Repo Commits:" in result.output
        # We created 1 init commit in the fixture
        assert "1" in result.output

    def test_stats_no_git(self):
        """Stats command should handle missing .git gracefully."""
        d = tempfile.mkdtemp()
        try:
            bank_dir = os.path.join(d, "bank")
            os.makedirs(bank_dir)
            with open(os.path.join(bank_dir, "test.md"), "w") as f:
                f.write("---\nname: test\ndescription: t\ntype: world\n---\n\nTest\n")

            runner = CliRunner()
            result = runner.invoke(
                main, ["memory", "stats", "--workspace", d]
            )
            assert result.exit_code == 0
            assert "Memory Repo Commits: N/A (no .git directory)" in result.output
        finally:
            shutil.rmtree(d)

    def test_stats_invalid_workspace(self):
        """Stats command should error on invalid workspace path."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["memory", "stats", "--workspace", "/nonexistent/path/xyz"]
        )
        assert result.exit_code != 0


# ── memory group tests ──────────────────────────────────────────────────


class TestMemoryGroupCommand:
    def test_memory_group_help(self):
        """memory --help should list subcommands."""
        runner = CliRunner()
        result = runner.invoke(main, ["memory", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output
        assert "stats" in result.output
