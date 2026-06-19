"""Tests for dream cycle integration — auto-trigger and manual trigger.

Tests cover:
1. DreamCycle.scan() finds duplicates, stale, and low-quality entries
2. DreamCycle.find_patterns() extracts observations and entity frequency
3. DreamCycle.consolidate() removes duplicates and prunes stale
4. DreamCycle.run() full 4-phase cycle
5. Session auto-triggers dream cycle every N turns
6. memory_dream tool is registered and callable
"""

import asyncio
import os
import shutil
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import nexusagent.tools.register_all  # noqa: F401
from nexusagent.memory.dream import DreamCycle, STALE_THRESHOLD_DAYS
from nexusagent.memory.memory import HybridMemoryManager
from nexusagent.memory.memory_files import FileMemory, MemoryEntryType
from nexusagent.tools.registry import get_tool_info


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_workspace():
    """Create a temporary workspace with bank/ directory."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


def _write_raw_memory(workspace, name, content):
    """Write a raw memory file (full content as-is) to bank/."""
    bank_dir = os.path.join(workspace, "bank")
    os.makedirs(bank_dir, exist_ok=True)
    filepath = os.path.join(bank_dir, f"{name}.md")
    with open(filepath, "w") as f:
        f.write(content)
    return filepath


def _write_memory(workspace, name="test-entry", content="Test content",
                  entry_type="world", description="Test desc",
                  entities=None, confidence=None, quality_score=None,
                  created=None):
    """Helper to write a test memory entry with YAML frontmatter."""
    bank_dir = os.path.join(workspace, "bank")
    os.makedirs(bank_dir, exist_ok=True)
    filepath = os.path.join(bank_dir, f"{name}.md")

    fm_lines = ["---"]
    fm_lines.append(f'name: "{name}"')
    fm_lines.append(f"description: {description}")
    fm_lines.append(f"type: {entry_type}")
    if created:
        fm_lines.append(f"created: {created}")
    else:
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


def _set_file_mtime(filepath, days_ago):
    """Set the file's mtime to N days ago."""
    old_time = time.time() - (days_ago * 86400)
    os.utime(filepath, (old_time, old_time))


# ── Phase 1: Scan tests ────────────────────────────────────────────────


class TestDreamCycleScan:
    def test_scan_empty_workspace(self, tmp_workspace):
        """Scan on empty workspace should return zero counts."""
        cycle = DreamCycle(tmp_workspace)
        report = cycle.scan()
        assert report["total"] == 0
        assert report["duplicates"] == []
        assert report["stale"] == []
        assert report["health_score"] == 1.0

    def test_scan_finds_duplicates(self, tmp_workspace):
        """Scan should detect duplicate files by content hash.

        Duplicates are detected by hashing the full file content.
        Two files with identical content (including frontmatter) are duplicates.
        """
        # Write identical raw content to two files
        raw = (
            "---\n"
            'name: "dup-test"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "Identical body text\n"
        )
        _write_raw_memory(tmp_workspace, "orig", raw)
        _write_raw_memory(tmp_workspace, "copy", raw)

        cycle = DreamCycle(tmp_workspace)
        report = cycle.scan()
        assert report["total"] == 2
        assert len(report["duplicates"]) == 1
        assert report["duplicates"][0]["duplicate"] == "copy.md"

    def test_scan_finds_stale_entries(self, tmp_workspace):
        """Scan should detect entries with mtime older than 30 days."""
        filepath = _write_memory(tmp_workspace, name="old-entry", content="Old stuff")
        # Set file mtime to 60 days ago
        _set_file_mtime(filepath, STALE_THRESHOLD_DAYS + 30)

        cycle = DreamCycle(tmp_workspace)
        report = cycle.scan()
        assert len(report["stale"]) == 1
        assert report["stale"][0]["file"] == "old-entry.md"
        assert report["stale"][0]["age_days"] >= STALE_THRESHOLD_DAYS

    def test_scan_finds_low_quality(self, tmp_workspace):
        """Scan should detect entries with quality_score < 0.2."""
        _write_memory(tmp_workspace, name="lq", content="Bad entry",
                       quality_score=0.1)

        cycle = DreamCycle(tmp_workspace)
        report = cycle.scan()
        assert len(report["low_quality"]) == 1
        assert report["low_quality"][0]["score"] == 0.1

    def test_scan_health_score_degraded(self, tmp_workspace):
        """Health score should decrease with issues."""
        # Write 1 good + 2 identical (duplicate) files
        raw = (
            "---\n"
            'name: "health-test"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "Repeated content for health\n"
        )
        _write_memory(tmp_workspace, name="good", content="Good entry")
        _write_raw_memory(tmp_workspace, "dup1", raw)
        _write_raw_memory(tmp_workspace, "dup2", raw)

        cycle = DreamCycle(tmp_workspace)
        report = cycle.scan()
        assert report["health_score"] < 1.0


# ── Phase 2: Patterns tests ────────────────────────────────────────────


class TestDreamCyclePatterns:
    def test_find_patterns_empty(self, tmp_workspace):
        """Patterns on empty workspace should return empty results."""
        cycle = DreamCycle(tmp_workspace)
        patterns = cycle.find_patterns()
        assert patterns["observations"] == []
        assert patterns["entity_frequency"] == {}
        assert patterns["total_files_scanned"] == 0

    def test_find_patterns_entity_frequency(self, tmp_workspace):
        """Patterns should count entity mentions across files."""
        _write_memory(tmp_workspace, name="e1", content="First",
                       entities=["auth", "jwt"])
        _write_memory(tmp_workspace, name="e2", content="Second",
                       entities=["auth", "oauth"])

        cycle = DreamCycle(tmp_workspace)
        patterns = cycle.find_patterns()
        assert patterns["entity_frequency"]["auth"] == 2
        assert patterns["entity_frequency"]["jwt"] == 1
        assert patterns["entity_frequency"]["oauth"] == 1

    def test_find_patterns_type_distribution(self, tmp_workspace):
        """Patterns should track type distribution."""
        _write_memory(tmp_workspace, name="w1", entry_type="world", content="Fact")
        _write_memory(tmp_workspace, name="w2", entry_type="world", content="Fact2")
        _write_memory(tmp_workspace, name="o1", entry_type="opinion", content="Opinion")

        cycle = DreamCycle(tmp_workspace)
        patterns = cycle.find_patterns()
        assert patterns["type_distribution"]["world"] == 2
        assert patterns["type_distribution"]["opinion"] == 1

    def test_find_patterns_observations(self, tmp_workspace):
        """Patterns should extract bullet points as observations."""
        content = (
            "---\n"
            'name: "obs"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "- First observation\n"
            "- Second observation\n"
        )
        _write_raw_memory(tmp_workspace, "obs", content)

        cycle = DreamCycle(tmp_workspace)
        patterns = cycle.find_patterns()
        obs = patterns["observations"]
        assert any("First observation" in o for o in obs)
        assert any("Second observation" in o for o in obs)


# ── Phase 3: Consolidate tests ─────────────────────────────────────────


class TestDreamCycleConsolidate:
    def test_consolidate_removes_duplicates(self, tmp_workspace):
        """Consolidate should remove duplicate files."""
        raw = (
            "---\n"
            'name: "cons-dup"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "Shared content\n"
        )
        _write_raw_memory(tmp_workspace, "orig", raw)
        _write_raw_memory(tmp_workspace, "dupe", raw)

        cycle = DreamCycle(tmp_workspace)
        scan_report = cycle.scan()
        assert len(scan_report["duplicates"]) == 1

        actions = cycle.consolidate(scan_report)
        assert actions["duplicates_removed"] == 1

        # Verify the duplicate file is gone
        assert not os.path.exists(os.path.join(tmp_workspace, "bank", "dupe.md"))
        # Original should still exist
        assert os.path.exists(os.path.join(tmp_workspace, "bank", "orig.md"))

    def test_consolidate_prunes_stale(self, tmp_workspace):
        """Consolidate should prune stale entries (by mtime)."""
        filepath = _write_memory(tmp_workspace, name="stale-entry", content="Old")
        _set_file_mtime(filepath, STALE_THRESHOLD_DAYS + 30)

        cycle = DreamCycle(tmp_workspace)
        scan_report = cycle.scan()
        assert len(scan_report["stale"]) == 1

        actions = cycle.consolidate(scan_report)
        assert actions["stale_pruned"] == 1
        assert not os.path.exists(os.path.join(tmp_workspace, "bank", "stale-entry.md"))

    def test_consolidate_removes_low_quality(self, tmp_workspace):
        """Consolidate should remove low-quality entries."""
        _write_memory(tmp_workspace, name="bad", content="Low quality",
                       quality_score=0.05)

        cycle = DreamCycle(tmp_workspace)
        scan_report = cycle.scan()
        assert len(scan_report["low_quality"]) == 1

        actions = cycle.consolidate(scan_report)
        assert actions["low_quality_removed"] == 1
        assert not os.path.exists(os.path.join(tmp_workspace, "bank", "bad.md"))


# ── Full cycle tests ───────────────────────────────────────────────────


class TestDreamCycleFull:
    @pytest.mark.asyncio
    async def test_full_cycle_dry_run(self, tmp_workspace):
        """Full cycle dry_run should not modify files."""
        raw = (
            "---\n"
            'name: "dry-dup"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "Dup content\n"
        )
        _write_raw_memory(tmp_workspace, "orig", raw)
        _write_raw_memory(tmp_workspace, "copy", raw)

        cycle = DreamCycle(tmp_workspace)
        report = await cycle.run(dry_run=True)

        assert report["dry_run"] is True
        assert report["duplicates_removed"] == 0
        # Files should still exist
        assert os.path.exists(os.path.join(tmp_workspace, "bank", "orig.md"))
        assert os.path.exists(os.path.join(tmp_workspace, "bank", "copy.md"))

    @pytest.mark.asyncio
    async def test_full_cycle_removes_duplicates(self, tmp_workspace):
        """Full cycle should remove duplicate files."""
        raw = (
            "---\n"
            'name: "full-dup"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "Shared content\n"
        )
        _write_memory(tmp_workspace, name="keep", content="Unique content A")
        _write_raw_memory(tmp_workspace, "orig", raw)
        _write_raw_memory(tmp_workspace, "dupe", raw)

        cycle = DreamCycle(tmp_workspace)
        report = await cycle.run(dry_run=False)

        assert report["duplicates_removed"] == 1
        assert os.path.exists(os.path.join(tmp_workspace, "bank", "keep.md"))
        assert os.path.exists(os.path.join(tmp_workspace, "bank", "orig.md"))
        assert not os.path.exists(os.path.join(tmp_workspace, "bank", "dupe.md"))

    @pytest.mark.asyncio
    async def test_full_cycle_prunes_stale(self, tmp_workspace):
        """Full cycle should prune stale entries."""
        _write_memory(tmp_workspace, name="fresh", content="Fresh entry")
        stale_fp = _write_memory(tmp_workspace, name="stale", content="Stale entry")
        _set_file_mtime(stale_fp, STALE_THRESHOLD_DAYS + 15)

        cycle = DreamCycle(tmp_workspace)
        report = await cycle.run(dry_run=False)

        assert report["stale_pruned"] == 1
        assert os.path.exists(os.path.join(tmp_workspace, "bank", "fresh.md"))
        assert not os.path.exists(os.path.join(tmp_workspace, "bank", "stale.md"))

    @pytest.mark.asyncio
    async def test_full_cycle_extracts_patterns(self, tmp_workspace):
        """Full cycle should extract patterns from memory files."""
        _write_memory(tmp_workspace, name="p1", content="- Auth uses JWT\n- Tokens expire hourly",
                       entities=["auth"])
        _write_memory(tmp_workspace, name="p2", content="- Auth requires OAuth\n- JWT is preferred",
                       entities=["auth", "jwt"])

        cycle = DreamCycle(tmp_workspace)
        report = await cycle.run(dry_run=False)

        assert report["patterns_extracted"] > 0

    @pytest.mark.asyncio
    async def test_full_cycle_health_improves(self, tmp_workspace):
        """Full cycle should improve health score after cleanup."""
        _write_memory(tmp_workspace, name="good", content="Good entry")
        raw = (
            "---\n"
            'name: "hlth-dup"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "Repeated content\n"
        )
        _write_raw_memory(tmp_workspace, "dup1", raw)
        _write_raw_memory(tmp_workspace, "dup2", raw)

        cycle = DreamCycle(tmp_workspace)
        report = await cycle.run(dry_run=False)

        assert report["health_after"] >= report["health_before"]


# ── Session auto-trigger tests ─────────────────────────────────────────


class TestSessionDreamCycleTrigger:
    @pytest.mark.asyncio
    async def test_turn_count_increments(self):
        """Session turn count should increment on each send()."""
        session = _create_mock_session()
        assert session._turn_count == 0

        await session.send("Hello")
        assert session._turn_count == 1

        await session.send("Again")
        assert session._turn_count == 2

    @pytest.mark.asyncio
    async def test_dream_cycle_triggers_at_interval(self):
        """Dream cycle should trigger every N turns."""
        session = _create_mock_session()

        # Set interval to 3 for testing
        with patch("nexusagent.core.session.session.settings") as mock_settings:
            mock_settings.agent.dream_cycle_interval = 3
            mock_settings.agent.max_conversation_history = 40
            mock_settings.agent.compaction_enabled = False
            mock_settings.hooks.hooks_enabled = False
            mock_settings.prompt.chat_file_injection = False

            # Mock DreamCycle to track calls
            with patch("nexusagent.core.session.session.DreamCycle") as mock_dream_cycle:
                mock_cycle = MagicMock()
                mock_cycle.run = AsyncMock(return_value={
                    "duplicates_removed": 0,
                    "stale_pruned": 0,
                    "patterns_extracted": 0,
                    "health_before": 1.0,
                    "health_after": 1.0,
                })
                mock_dream_cycle.return_value = mock_cycle

                # Send 3 messages — dream cycle should trigger on 3rd
                await session.send("msg1")
                await session.send("msg2")
                assert session._turn_count == 2
                # Not yet triggered
                mock_dream_cycle.assert_not_called()

                await session.send("msg3")
                assert session._turn_count == 3
                # Now it should have been called
                mock_dream_cycle.assert_called_once_with(str(session.memory_dir))

    @pytest.mark.asyncio
    async def test_dream_cycle_not_triggered_before_interval(self):
        """Dream cycle should NOT trigger before N turns."""
        session = _create_mock_session()

        with patch("nexusagent.core.session.session.settings") as mock_settings:
            mock_settings.agent.dream_cycle_interval = 10
            mock_settings.agent.max_conversation_history = 40
            mock_settings.agent.compaction_enabled = False
            mock_settings.hooks.hooks_enabled = False
            mock_settings.prompt.chat_file_injection = False

            with patch("nexusagent.core.session.session.DreamCycle") as mock_dream_cycle:
                for i in range(5):
                    await session.send(f"msg{i}")

                assert session._turn_count == 5
                mock_dream_cycle.assert_not_called()


# ── memory_dream tool tests ────────────────────────────────────────────


class TestMemoryDreamTool:
    def test_memory_dream_tool_registered(self):
        """memory_dream tool should be registered in the tool registry."""
        info = get_tool_info("memory_dream")
        assert info is not None
        assert info.name == "memory_dream"
        assert info.category == "memory"
        assert "workspace" in info.parameters
        assert "dry_run" in info.parameters

    @pytest.mark.asyncio
    async def test_memory_dream_dry_run(self, tmp_workspace):
        """memory_dream tool dry_run should not modify files."""
        from nexusagent.tools.register_all import memory_dream

        raw = (
            "---\n"
            'name: "tl-dry"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "Dup\n"
        )
        _write_raw_memory(tmp_workspace, "orig", raw)
        _write_raw_memory(tmp_workspace, "copy", raw)

        result = await memory_dream(workspace=tmp_workspace, dry_run=True)
        assert "Dream Cycle Report" in result
        assert "Dry run: True" in result
        # Files should still exist
        assert os.path.exists(os.path.join(tmp_workspace, "bank", "orig.md"))
        assert os.path.exists(os.path.join(tmp_workspace, "bank", "copy.md"))

    @pytest.mark.asyncio
    async def test_memory_dream_execute(self, tmp_workspace):
        """memory_dream tool with dry_run=False should consolidate."""
        from nexusagent.tools.register_all import memory_dream

        raw = (
            "---\n"
            'name: "tl-exec"\n'
            "description: test\n"
            "type: world\n"
            f"created: {datetime.now(UTC).isoformat()}\n"
            "---\n\n"
            "Dup\n"
        )
        _write_memory(tmp_workspace, name="keep", content="Unique")
        _write_raw_memory(tmp_workspace, "orig", raw)
        _write_raw_memory(tmp_workspace, "copy", raw)

        result = await memory_dream(workspace=tmp_workspace, dry_run=False)
        assert "Dream Cycle Report" in result
        assert "Dry run: False" in result
        # Duplicate should be removed
        assert not os.path.exists(os.path.join(tmp_workspace, "bank", "copy.md"))


# ── Config tests ───────────────────────────────────────────────────────


class TestDreamCycleConfig:
    def test_dream_cycle_interval_default(self):
        """dream_cycle_interval should default to 20."""
        from nexusagent.infrastructure.config import AgentConfig
        config = AgentConfig()
        assert config.dream_cycle_interval == 20

    def test_dream_cycle_interval_custom(self):
        """dream_cycle_interval should accept custom values."""
        from nexusagent.infrastructure.config import AgentConfig
        config = AgentConfig(dream_cycle_interval=50)
        assert config.dream_cycle_interval == 50


# ── Helpers ────────────────────────────────────────────────────────────


def _create_mock_session():
    """Create a Session with mocked dependencies for unit testing."""
    from nexusagent.core.session.session import Session

    agent = MagicMock()

    async def _astream(input_data, stream_mode=None, **kwargs):
        from langchain_core.messages import AIMessageChunk
        yield AIMessageChunk(content="response")

    agent.astream = _astream

    session = Session(
        session_id="test-dream",
        working_dir="/tmp",
        agent=agent,
        db_repo=MagicMock(),
    )
    session.db_repo.add_message = AsyncMock()
    session.db_repo.update_status = AsyncMock()
    session.hybrid_memory.get_memory_context = AsyncMock(return_value="")
    return session
