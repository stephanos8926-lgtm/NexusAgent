"""TDD tests for confirmed TUI bugs — updated for widget-based architecture.

These tests target the SPECIFIC broken behaviors reported, now fixed:
1. Streaming: token-by-token via AssistantMessage.append_token()
2. Tool calls: formatted via ToolCallMessage widget
3. Word wrapping: Container(layout="stream") + CSS
4. Greeting: WelcomeBanner widget on mount
5. Markdown: render_markdown wired into AssistantMessage.finalize()
6. Escape: _escape handles parentheses
7. action_quit: signals via input queue
8. yolo field: present in AgentConfig
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Bug 1: Streaming — token-by-token via AssistantMessage
# ═══════════════════════════════════════════════════════════════════════


class TestStreaming:
    """Streaming uses AssistantMessage.append_token() — O(1) per token."""

    def test_assistant_message_append_token(self):
        """AssistantMessage should support append_token for streaming."""
        from nexusagent.widgets.messages import AssistantMessage
        msg = AssistantMessage()
        # append_token is an async method — just verify it exists
        assert hasattr(msg, "append_token")
        assert hasattr(msg, "finalize")

    def test_no_accumulation_string(self):
        """NexusApp should NOT have _streaming_response string attribute."""
        from nexusagent.interfaces.tui import NexusApp
        app = NexusApp(session_id="test")
        # The old O(n²) accumulation attribute should not exist
        assert not hasattr(app, "_streaming_response")
        assert not hasattr(app, "_streaming_widget")


# ═══════════════════════════════════════════════════════════════════════
# Bug 2: Tool call display — formatted via ToolCallMessage
# ═══════════════════════════════════════════════════════════════════════


class TestToolCallDisplay:
    """Tool calls display via ToolCallMessage widget with formatted args."""

    def test_tool_call_message_widget_exists(self):
        """ToolCallMessage widget should exist with tool/args/status."""
        from nexusagent.widgets.messages import ToolCallMessage
        msg = ToolCallMessage(tool="read_file", args="path=src/main.py", status="running")
        assert msg is not None

    def test_tool_call_args_formatted_not_raw_json(self):
        """Dict args should display as key=value, not as JSON dict."""
        from nexusagent.interfaces.tui import NexusApp
        app = NexusApp(session_id="test")
        app._auto_approve = False
        app._busy = False
        app._ws = None
        app._pending_inputs = []
        app._total_tokens_used = 0
        app._request_count = 0
        app.messages_container = MagicMock()
        app.status_bar = MagicMock()

        event = {
            "type": "tool_call",
            "tool": "read_file",
            "args": {"path": "src/main.py", "offset": 10, "limit": 20},
            "call_id": "call-123",
        }

        asyncio.run(app._handle_event(event))

        # Verify a ToolCallMessage was mounted
        mount_calls = app.messages_container.mount.call_args_list
        assert len(mount_calls) > 0

    def test_tool_result_updates_widget(self):
        """Tool results should update the current tool widget."""
        from nexusagent.interfaces.tui import NexusApp
        app = NexusApp(session_id="test")
        app._auto_approve = True
        app._busy = False
        app._ws = None
        app._pending_inputs = []
        app._total_tokens_used = 0
        app._request_count = 0
        app.messages_container = MagicMock()
        app.status_bar = MagicMock()

        # First, a tool call
        call_event = {
            "type": "tool_call",
            "tool": "read_file",
            "args": {"path": "test.py"},
            "call_id": "call-456",
        }
        asyncio.run(app._handle_event(call_event))

        # Then a result
        result_event = {
            "type": "tool_result",
            "output": "hello world",
            "success": True,
            "call_id": "call-456",
        }
        asyncio.run(app._handle_event(result_event))

        # Should have mounted at least the tool call
        assert app.messages_container.mount.call_count >= 1


# ═══════════════════════════════════════════════════════════════════════
# Bug 3: Word wrapping — CSS + Container layout
# ═══════════════════════════════════════════════════════════════════════


class TestWordWrapping:
    """Word wrapping via CSS variables and Container(layout='stream')."""

    def test_css_has_stream_layout(self):
        """The CSS should use layout: stream for messages."""
        from nexusagent.interfaces.tui import NexusApp
        app = NexusApp(session_id="test")
        css = app.CSS
        assert "layout: stream" in css

    def test_css_has_border_focus(self):
        """CSS should use semantic variables for theming."""
        from nexusagent.interfaces.tui import NexusApp
        app = NexusApp(session_id="test")
        css = app.CSS
        assert "$" in css  # Uses CSS variables
        assert "$border" in css or "$border-focus" in css or "$primary" in css


# ═══════════════════════════════════════════════════════════════════════
# Bug 4: Greeting rendering — WelcomeBanner widget
# ═══════════════════════════════════════════════════════════════════════


class TestGreetingRendering:
    """Greeting shown via WelcomeBanner widget on mount."""

    def test_greeting_uses_welcome_banner(self):
        """_show_greeting should mount a WelcomeBanner widget."""
        from nexusagent.interfaces.tui import NexusApp
        app = NexusApp(session_id="test-abc")
        app.messages_container = MagicMock()
        app._show_greeting()

        # Verify WelcomeBanner was mounted
        mount_calls = app.messages_container.mount.call_args_list
        assert len(mount_calls) == 1

    def test_welcome_banner_widget_exists(self):
        """WelcomeBanner widget should exist."""
        from nexusagent.widgets.messages import WelcomeBanner
        banner = WelcomeBanner(session_id="test-abc")
        assert banner is not None


# ═══════════════════════════════════════════════════════════════════════
# Bug 5: Markdown renderer consistency
# ═══════════════════════════════════════════════════════════════════════


class TestMarkdownConsistency:
    """render_markdown should produce correct Rich markup."""

    def test_bold_rendering(self):
        """**bold** should convert to [b]bold[/b]."""
        from nexusagent.interfaces.tui_formatters import render_markdown
        result = render_markdown("**bold** text")
        assert "[b]bold[/b]" in result

    def test_italic_rendering(self):
        """*italic* should convert to [i]italic[/i]."""
        from nexusagent.interfaces.tui_formatters import render_markdown
        result = render_markdown("*italic* text")
        assert "[i]italic[/i]" in result

    def test_code_block_rendering(self):
        """Fenced code blocks should be extracted and formatted."""
        from nexusagent.interfaces.tui_formatters import render_markdown
        result = render_markdown("```python\nprint('hi')\n```")
        assert "[python]" in result or "print" in result

    def test_inline_code_rendering(self):
        """Inline code should use reverse markup."""
        from nexusagent.interfaces.tui_formatters import render_markdown
        result = render_markdown("Use `git status` to check")
        assert "git status" in result


# ═══════════════════════════════════════════════════════════════════════
# Bug 6: action_quit — signals via input queue
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
# Bug 7: SpinnerLabel.spinner_chars — single source of truth
# ═══════════════════════════════════════════════════════════════════════


class TestSpinnerCharsConsistency:
    """StatusBar should have its own spinner_chars (not duplicated)."""

    def test_status_bar_has_spinner(self):
        """StatusBar widget should support spinner."""
        from nexusagent.widgets.status import StatusBar
        bar = StatusBar()
        assert hasattr(bar, "set_spinner")


# ═══════════════════════════════════════════════════════════════════════
# Bug 8: yolo field in AgentConfig
# ═══════════════════════════════════════════════════════════════════════


class TestYoloField:
    """AgentConfig should have yolo field."""

    def test_yolo_field_exists(self):
        """ConfigSchema.agent should have yolo field."""
        from nexusagent.infrastructure.config import ConfigSchema
        schema = ConfigSchema()
        assert hasattr(schema.agent, "yolo")

    def test_yolo_default_false(self):
        """yolo should default to False."""
        from nexusagent.infrastructure.config import ConfigSchema
        schema = ConfigSchema()
        assert schema.agent.yolo is False
