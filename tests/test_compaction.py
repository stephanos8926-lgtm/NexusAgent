"""Tests for the context compaction pipeline."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.memory.compaction import CompactionPipeline, pre_compaction_flush

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_messages(count: int, content_size: int = 100) -> list[dict]:
    """Generate a list of alternating user/assistant messages."""
    msgs = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append(
            {
                "role": role,
                "content": f"Message {i} " + "x" * content_size,
            }
        )
    return msgs


def _make_messages_with_tools(count: int, tool_every: int = 3) -> list[dict]:
    """Generate messages that include tool results every N turns."""
    msgs = []
    for i in range(count):
        if i > 0 and i % tool_every == 0:
            msgs.append(
                {
                    "role": "tool",
                    "content": f"Tool result {i} " + "y" * 200,
                    "tool_call_id": f"tc-{i}",
                }
            )
        else:
            role = "user" if i % 2 == 0 else "assistant"
            msgs.append(
                {
                    "role": role,
                    "content": f"Message {i} " + "x" * 100,
                }
            )
    return msgs


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_empty_list(self):
        pipeline = CompactionPipeline()
        assert pipeline.estimate_tokens([]) == 0

    def test_single_message(self):
        pipeline = CompactionPipeline()
        msgs = [{"role": "user", "content": "hello"}]
        # 5 chars // 4 = 1
        assert pipeline.estimate_tokens(msgs) == 1

    def test_multiple_messages(self):
        pipeline = CompactionPipeline()
        msgs = [
            {"role": "user", "content": "a" * 100},
            {"role": "assistant", "content": "b" * 200},
        ]
        # 300 chars // 4 = 75
        assert pipeline.estimate_tokens(msgs) == 75

    def test_list_content(self):
        pipeline = CompactionPipeline()
        msgs = [{"role": "user", "content": [{"type": "text", "text": "hello world"}]}]
        # len(str(dict)) for the block
        tokens = pipeline.estimate_tokens(msgs)
        assert tokens > 0


# ---------------------------------------------------------------------------
# should_compact
# ---------------------------------------------------------------------------


class TestShouldCompact:
    def test_under_threshold(self):
        pipeline = CompactionPipeline(context_window_tokens=1000, compaction_threshold=0.75)
        msgs = [{"role": "user", "content": "a" * 100}]  # 25 tokens
        assert pipeline.should_compact(msgs) is False

    def test_over_threshold(self):
        pipeline = CompactionPipeline(context_window_tokens=100, compaction_threshold=0.5)
        # 204 chars // 4 = 51 tokens; threshold = 50 → over
        msgs = [{"role": "user", "content": "a" * 204}]
        assert pipeline.should_compact(msgs) is True

    def test_exactly_at_threshold(self):
        pipeline = CompactionPipeline(context_window_tokens=100, compaction_threshold=0.5)
        # 200 chars // 4 = 50 tokens; threshold = 50 → not over (strict >)
        msgs = [{"role": "user", "content": "a" * 200}]
        assert pipeline.should_compact(msgs) is False


# ---------------------------------------------------------------------------
# _clear_tool_results
# ---------------------------------------------------------------------------


class TestClearToolResults:
    def test_no_tool_results(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages(15)
        result = pipeline._clear_tool_results(msgs)
        assert result == msgs  # no tool messages, unchanged

    def test_clears_old_tool_results(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages_with_tools(20)
        result = pipeline._clear_tool_results(msgs)

        # Tool messages in the old section should be cleared
        tool_msgs_old = [m for m in result[:-10] if m["role"] == "tool"]
        for m in tool_msgs_old:
            assert m["content"] == "[Previous tool result content cleared]"

    def test_keeps_recent_tool_results(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages_with_tools(20)
        result = pipeline._clear_tool_results(msgs)

        # Tool messages in the recent section should be intact
        tool_msgs_recent = [m for m in result[-10:] if m["role"] == "tool"]
        for m in tool_msgs_recent:
            assert "Tool result" in m["content"]

    def test_short_list_unchanged(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages_with_tools(5)
        result = pipeline._clear_tool_results(msgs)
        assert len(result) == len(msgs)

    def test_preserves_message_structure(self):
        pipeline = CompactionPipeline()
        msgs = [
            {"role": "tool", "content": "old result", "tool_call_id": "tc-1"},
            *_make_messages(12),
        ]
        result = pipeline._clear_tool_results(msgs)
        old_tool = result[0]
        assert old_tool["role"] == "tool"
        assert old_tool["tool_call_id"] == "tc-1"
        assert old_tool["content"] == "[Previous tool result content cleared]"


# ---------------------------------------------------------------------------
# _microcompact
# ---------------------------------------------------------------------------


class TestMicrocompact:
    def test_removes_old_tool_results(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages_with_tools(20)
        result = pipeline._microcompact(msgs)

        # Tool messages in the old section should be cleared
        old_section = result[:-6]
        for m in old_section:
            if m["role"] == "tool":
                assert m["content"] == "[Previous tool result content cleared]"

    def test_keeps_user_and_assistant(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages_with_tools(20)
        result = pipeline._microcompact(msgs)

        # User and assistant messages should be intact everywhere
        for m in result:
            if m["role"] in ("user", "assistant"):
                assert "Message" in m["content"]

    def test_short_list_unchanged(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages(4)
        result = pipeline._microcompact(msgs)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# _summarize_old_messages
# ---------------------------------------------------------------------------


class TestSummarizeOldMessages:
    def test_replaces_old_with_summary(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages(20)
        result = pipeline._summarize_old_messages(msgs, keep_last=10)

        # First message should be a system summary
        assert result[0]["role"] == "system"
        assert "Conversation summary" in result[0]["content"]

        # Should have 1 summary + 10 kept = 11
        assert len(result) == 11

    def test_summary_mentions_user_messages(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages(20)
        result = pipeline._summarize_old_messages(msgs, keep_last=10)
        summary = result[0]["content"]
        assert "user messages" in summary

    def test_keeps_last_n_intact(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages(20)
        result = pipeline._summarize_old_messages(msgs, keep_last=10)

        # The last 10 messages should be the original recent messages
        assert result[1:] == msgs[10:]

    def test_short_list_unchanged(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages(5)
        result = pipeline._summarize_old_messages(msgs, keep_last=10)
        assert result == msgs


# ---------------------------------------------------------------------------
# _emergency_truncate
# ---------------------------------------------------------------------------


class TestEmergencyTruncate:
    def test_keeps_last_n(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages(20)
        result = pipeline._emergency_truncate(msgs, keep_last=5)

        # 1 warning + 5 kept
        assert len(result) == 6
        assert result[0]["role"] == "system"
        assert "Context truncated" in result[0]["content"]
        assert result[1:] == msgs[-5:]

    def test_short_list_unchanged(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages(3)
        result = pipeline._emergency_truncate(msgs, keep_last=5)
        assert result == msgs

    def test_warning_message(self):
        pipeline = CompactionPipeline()
        msgs = _make_messages(10)
        result = pipeline._emergency_truncate(msgs, keep_last=5)
        assert "Context truncated due to length" in result[0]["content"]


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


class TestCompactionPipeline:
    def test_no_compaction_needed(self):
        pipeline = CompactionPipeline(context_window_tokens=1_000_000)
        msgs = _make_messages(10)
        result = pipeline.compact(msgs)
        assert result == msgs

    def test_compaction_reduces_size(self):
        """Create messages over threshold, compact, verify reduction."""
        # Small window so we trigger compaction
        pipeline = CompactionPipeline(context_window_tokens=200, compaction_threshold=0.5)
        # Each message ~26 chars // 4 = 6 tokens; 50 msgs = ~300 tokens > 100 threshold
        msgs = _make_messages(50, content_size=100)
        assert pipeline.should_compact(msgs)

        result = pipeline.compact(msgs)
        assert pipeline.estimate_tokens(result) < pipeline.estimate_tokens(msgs)

    def test_compaction_ends_under_threshold(self):
        """After compaction, the result should be under threshold."""
        pipeline = CompactionPipeline(context_window_tokens=5000, compaction_threshold=0.5)
        msgs = _make_messages(100, content_size=200)
        assert pipeline.should_compact(msgs)

        result = pipeline.compact(msgs)
        assert not pipeline.should_compact(result)

    def test_preserves_recent_messages(self):
        """Recent messages should survive compaction."""
        pipeline = CompactionPipeline(context_window_tokens=200, compaction_threshold=0.5)
        msgs = _make_messages(50, content_size=100)
        result = pipeline.compact(msgs)

        # The very last message should always be preserved
        assert result[-1] == msgs[-1]


# ---------------------------------------------------------------------------
# pre_compaction_flush
# ---------------------------------------------------------------------------


class TestPreCompactionFlush:
    @pytest.mark.asyncio
    async def test_flush_writes_to_daily_log(self):
        """Verify flush writes to daily log via hybrid_memory."""
        mock_session = MagicMock()
        mock_session.hybrid_memory.flush = AsyncMock()

        summary = "Test compaction summary"
        result = await pre_compaction_flush(mock_session, summary)

        mock_session.hybrid_memory.flush.assert_called_once_with(summary)
        assert "Before compaction" in result
        assert summary in result

    @pytest.mark.asyncio
    async def test_flush_handles_errors_gracefully(self):
        """If flush fails, should not raise."""
        mock_session = MagicMock()
        mock_session.hybrid_memory.flush = AsyncMock(side_effect=RuntimeError("DB error"))

        result = await pre_compaction_flush(mock_session, "test summary")
        assert "Before compaction" in result
