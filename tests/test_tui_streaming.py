# SPDX-License-Identifier: MIT

"""Tests for the conversational TUI."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from nexusagent.interfaces.tui import ApprovalModal, ErrorModal, NexusApp
from nexusagent.widgets.messages import ToolCallMessage


class TestTuiCompose:
    """Verify the app can be instantiated and composed without errors."""

    def test_tui_compose(self):
        """Creating a NexusApp instance should not raise."""
        app = NexusApp()
        assert app is not None

    def test_error_modal_creation(self):
        """Creating an ErrorModal should not raise."""
        modal = ErrorModal("test error")
        assert modal.error_message == "test error"


class TestApprovalModal:
    """Verify the ApprovalModal works as expected."""

    def test_approval_modal_creation(self):
        """Creating an ApprovalModal should not raise."""
        modal = ApprovalModal("bash", {"cmd": "ls -la"})
        assert modal.tool_name == "bash"
        assert modal.tool_args == {"cmd": "ls -la"}


class TestTuiExpandCollapse:
    """Verify that expanding/collapsing tool call messages works correctly via actions and slash commands."""

    def _make_app(self) -> NexusApp:
        """Create a minimally mocked NexusApp."""
        app = NexusApp.__new__(NexusApp)
        app.session_id = "test-expand-collapse"
        app._yolo_default = False
        app._busy = False
        app._pending_inputs = []
        app._current_assistant = None
        app._current_tool = None
        app._theme_name = "nexus-dark"
        app._gc_frozen = False
        app._breakpoint = MagicMock()
        app._resize_state = {}
        app._auto_approve = False
        app._total_tokens_used = 0
        app._request_count = 0
        app._last_tool_name = ""
        app._context_used = 0
        app._context_limit = 0
        app._ws = None
        app._ws_task = None
        app._input_queue = asyncio.Queue()
        app.messages_container = MagicMock()
        app.status_bar = MagicMock()
        app.chat_input = MagicMock()
        return app

    def test_action_expand_all(self):
        """action_expand_all must expand all collapsed ToolCallMessage widgets."""
        app = self._make_app()

        # Create mock ToolCallMessage widgets
        collapsed_widget = MagicMock(spec=ToolCallMessage)
        collapsed_widget._collapsed = True
        collapsed_widget.toggle_collapse = MagicMock()

        expanded_widget = MagicMock(spec=ToolCallMessage)
        expanded_widget._collapsed = False
        expanded_widget.toggle_collapse = MagicMock()

        # Set up messages_container query mock
        app.messages_container.query.return_value = [collapsed_widget, expanded_widget]

        # Call the expand all action
        app.action_expand_all()

        # Only the collapsed widget should be toggled
        collapsed_widget.toggle_collapse.assert_called_once()
        expanded_widget.toggle_collapse.assert_not_called()

    def test_action_collapse_all(self):
        """action_collapse_all must collapse all expanded ToolCallMessage widgets with output."""
        app = self._make_app()

        # Create mock ToolCallMessage widgets
        collapsed_widget = MagicMock(spec=ToolCallMessage)
        collapsed_widget._collapsed = True
        collapsed_widget._output = "some output"
        collapsed_widget.toggle_collapse = MagicMock()

        expanded_widget_with_output = MagicMock(spec=ToolCallMessage)
        expanded_widget_with_output._collapsed = False
        expanded_widget_with_output._output = "some output"
        expanded_widget_with_output.toggle_collapse = MagicMock()

        expanded_widget_no_output = MagicMock(spec=ToolCallMessage)
        expanded_widget_no_output._collapsed = False
        expanded_widget_no_output._output = ""
        expanded_widget_no_output.toggle_collapse = MagicMock()

        # Set up messages_container query mock
        app.messages_container.query.return_value = [
            collapsed_widget,
            expanded_widget_with_output,
            expanded_widget_no_output,
        ]

        # Call the collapse all action
        app.action_collapse_all()

        # Only the expanded widget with output should be toggled
        collapsed_widget.toggle_collapse.assert_not_called()
        expanded_widget_with_output.toggle_collapse.assert_called_once()
        expanded_widget_no_output.toggle_collapse.assert_not_called()

    def test_slash_command_expand(self):
        """Slash commands /expand and /e must invoke action_expand_all."""
        app = self._make_app()
        app.action_expand_all = MagicMock()

        # Trigger /expand command
        res1 = asyncio.run(app._handle_slash_command("/expand"))
        assert res1 is True
        app.action_expand_all.assert_called_once()

        app.action_expand_all.reset_mock()

        # Trigger /e command
        res2 = asyncio.run(app._handle_slash_command("/e"))
        assert res2 is True
        app.action_expand_all.assert_called_once()

    def test_slash_command_collapse(self):
        """Slash commands /collapse and /a must invoke action_collapse_all."""
        app = self._make_app()
        app.action_collapse_all = MagicMock()

        # Trigger /collapse command
        res1 = asyncio.run(app._handle_slash_command("/collapse"))
        assert res1 is True
        app.action_collapse_all.assert_called_once()

        app.action_collapse_all.reset_mock()

        # Trigger /a command
        res2 = asyncio.run(app._handle_slash_command("/a"))
        assert res2 is True
        app.action_collapse_all.assert_called_once()
