"""TDD tests for confirmed TUI bugs — RED phase.

These tests target the SPECIFIC broken behaviors reported:
1. Fake streaming: tokens accumulated then dumped as single event
2. Tool calls show raw JSON instead of formatted output
3. Word wrapping broken despite wrap=True in RichLog CSS
4. Greeting may not render on mount
5. _write_response / _enhanced_markdown redundancy
6. _escape misses parentheses which RichLog interprets as markup
7. action_quit race condition (no event loop)
8. Missing yolo field in AgentConfig
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Bug 1: Streaming double-write
# ═══════════════════════════════════════════════════════════════════════


class TestStreamingDoubleWrite:
    """When streaming is active, _finalize_response should write to log
    and clear the streaming widget — but the response should appear exactly
    ONCE in the log, not twice."""

    def test_finalize_does_not_double_write(self):
        """The response should appear exactly ONCE in the log writes."""
        from nexusagent.interfaces.tui import NexusApp

        app = NexusApp(session_id="test")
        app._streaming_response = ""
        app._streaming_widget = MagicMock()
        app.log_widget = MagicMock()

        # Stream tokens
        app._write_response_chunk("Hello")
        app._write_response_chunk(" World")

        # Finalize
        app._finalize_response("Hello World")

        # Count occurrences in log writes
        log_calls = app.log_widget.write.call_args_list
        full_log = str(log_calls)
        count = full_log.count("Hello World")
        assert count == 1, (
            f"Response appears {count} times in log — should be exactly 1."
        )

    def test_streaming_widget_cleared_after_finalize(self):
        """After finalize, the streaming widget must be empty."""
        from nexusagent.interfaces.tui import NexusApp

        app = NexusApp(session_id="test")
        app._streaming_response = "some content"
        app._streaming_widget = MagicMock()
        app.log_widget = MagicMock()

        app._finalize_response("some content")

        last_call = app._streaming_widget.update.call_args
        assert last_call[0][0] == "", (
            f"Streaming widget not cleared after finalize. Last call: {last_call}"
        )

    def test_finalize_with_empty_streaming_writes_to_log(self):
        """When no streaming activity, finalize should still write to log."""
        from nexusagent.interfaces.tui import NexusApp

        app = NexusApp(session_id="test")
        app._streaming_response = ""
        app._streaming_widget = MagicMock()
        app.log_widget = MagicMock()

        app._finalize_response("Full response text")

        log_text = str(app.log_widget.write.call_args_list)
        assert "Full response text" in log_text


# ═══════════════════════════════════════════════════════════════════════
# Bug 2: Tool call display
# ═══════════════════════════════════════════════════════════════════════


class TestToolCallDisplay:
    """Tool call arguments should be formatted as key=value, not raw JSON."""

    def _make_app(self):
        """Create a NexusApp with all required attributes."""
        from nexusagent.interfaces.tui import NexusApp

        app = NexusApp(session_id="test")
        app._auto_approve = False
        app._busy = False
        app._ws = None
        app._collapsibles = []
        app._pending_inputs = []
        app._streaming_response = ""
        app._total_tokens_used = 0
        app._request_count = 0
        app._theme_index = 0
        app.log_widget = MagicMock()
        app.status_widget = MagicMock()
        app._streaming_widget = MagicMock()
        return app

    def test_tool_call_args_formatted_not_raw_json(self):
        """Dict args should display as key=value, not as JSON dict."""
        from nexusagent.interfaces.tui import NexusApp

        app = self._make_app()

        event = {
            "type": "tool_call",
            "tool": "read_file",
            "args": {"path": "src/main.py", "offset": 10, "limit": 20},
            "call_id": "call-123",
        }

        asyncio.run(app._handle_event(event))

        log_text = str(app.log_widget.write.call_args_list)
        # Should NOT contain raw JSON
        assert '{"path"' not in log_text
        # Should contain formatted key=value
        assert "path" in log_text

    def test_tool_result_json_prettified(self):
        """JSON tool results should be formatted, not raw."""
        from nexusagent.interfaces.tui import NexusApp

        app = self._make_app()
        app._last_tool_name = "read_file"

        event = {
            "type": "tool_result",
            "output": '{"content": "hello world", "lines": 42}',
            "success": True,
            "call_id": "call-456",
        }

        asyncio.run(app._handle_event(event))

        log_text = str(app.log_widget.write.call_args_list)
        assert "hello world" in log_text


# ═══════════════════════════════════════════════════════════════════════
# Bug 3: Word wrapping
# ═══════════════════════════════════════════════════════════════════════


class TestWordWrapping:
    """RichLog should have wrap=True and CSS text-wrap for word wrapping."""

    def test_css_has_text_wrap(self):
        """The CSS must include text-wrap: wrap for word wrapping."""
        from nexusagent.interfaces.tui import NexusApp

        app = NexusApp(session_id="test")
        css = app.CSS
        assert "text-wrap: wrap" in css, "CSS must include text-wrap: wrap"
        assert "overflow-x: hidden" in css, "CSS must hide horizontal overflow"

    def test_conversation_log_wrap_css(self):
        """The #conversation-log rule must have wrap enabled."""
        from nexusagent.interfaces.tui import NexusApp

        app = NexusApp(session_id="test")
        css = app.CSS
        assert "#conversation-log" in css
        assert "text-wrap: wrap" in css


# ═══════════════════════════════════════════════════════════════════════
# Bug 4: Greeting rendering
# ═══════════════════════════════════════════════════════════════════════


class TestGreetingRendering:
    """The greeting should be shown on mount."""

    def test_greeting_writes_to_log(self):
        """_show_greeting should write the banner to the log widget."""
        from nexusagent.interfaces.tui import NexusApp

        app = NexusApp(session_id="test")
        app.session_id = "test-abc"
        app.log_widget = MagicMock()

        app._show_greeting()

        log_text = str(app.log_widget.write.call_args_list)
        assert "NexusAgent" in log_text
        assert "Session:" in log_text
        assert "/help" in log_text

    def test_greeting_shown_on_mount(self):
        """on_mount should call _show_greeting."""
        from nexusagent.interfaces.tui import NexusApp

        async def _test():
            app = NexusApp(session_id="test")
            app.log_widget = MagicMock()
            app.status_widget = MagicMock()
            app.queue_status = MagicMock()
            app._streaming_widget = MagicMock()
            app._auto_approve_badge = MagicMock()

            def mock_query_one(selector, widget_type=None):
                if "conversation-log" in selector:
                    return app.log_widget
                if "status-bar" in selector:
                    return app.status_widget
                if "queue-status" in selector:
                    return app.queue_status
                if "streaming" in selector:
                    return app._streaming_widget
                if "auto-approve" in selector:
                    return app._auto_approve_badge
                return MagicMock()

            app.query_one = mock_query_one
            app.on_mount()
            assert app.log_widget.write.call_count > 0

        asyncio.run(_test())


# ═══════════════════════════════════════════════════════════════════════
# Bug 5: Markdown renderer consistency
# ═══════════════════════════════════════════════════════════════════════


class TestMarkdownConsistency:
    """_simple_markdown and _enhanced_markdown should produce consistent output."""

    def test_bold_rendering_consistent(self):
        """Both renderers should convert **bold** to [b]bold[/b]."""
        from nexusagent.interfaces.tui import NexusApp

        app = NexusApp(session_id="test")
        simple = app._simple_markdown("**bold** text")
        enhanced = app._enhanced_markdown("**bold** text")
        assert "[b]bold[/b]" in simple
        assert "[b]bold[/b]" in enhanced

    def test_italic_rendering_consistent(self):
        """Both renderers should convert *italic* to [i]italic[/i]."""
        from nexusagent.interfaces.tui import NexusApp

        app = NexusApp(session_id="test")
        simple = app._simple_markdown("*italic* text")
        enhanced = app._enhanced_markdown("*italic* text")
        assert "[i]italic[/i]" in simple
        assert "[i]italic[/i]" in enhanced


# ═══════════════════════════════════════════════════════════════════════
# Bug 6: action_quit race condition
# ═══════════════════════════════════════════════════════════════════════


class TestActionQuit:
    """action_quit should signal the WebSocket loop to stop."""

    def test_quit_sends_none_to_queue(self):
        """action_quit should put None on the input queue."""
        from nexusagent.interfaces.tui import NexusApp

        async def _test():
            app = NexusApp(session_id="test")
            app._input_queue = asyncio.Queue()
            app._ws_task = MagicMock()
            app.action_quit()
            item = await asyncio.wait_for(app._input_queue.get(), timeout=1.0)
            assert item is None

        asyncio.run(_test())


# ═══════════════════════════════════════════════════════════════════════
# Bug 7: SpinnerLabel.spinner_chars duplicated in StatusBar
# ═══════════════════════════════════════════════════════════════════════


class TestSpinnerCharsDuplication:
    """spinner_chars exists in both tui.py SpinnerLabel and status.py StatusBar."""

    def test_single_source_of_truth(self):
        """Both widgets should use the same spinner characters."""
        from nexusagent.interfaces.tui import SpinnerLabel
        from nexusagent.widgets.status import StatusBar

        assert SpinnerLabel.spinner_chars == StatusBar.SPINNER_CHARS
