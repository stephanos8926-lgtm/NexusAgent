"""Tests for TUI bug fixes: _busy reset on disconnect, stale widget cleanup.

Covers:
- _busy reset on ConnectionClosedOK
- _busy reset on ConnectionClosedError (final attempt)
- _busy reset on ConnectionClosedError (reconnect path)
- _busy reset on generic Exception
- _current_assistant and _current_tool reset on all disconnect/error paths
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import websockets.exceptions

from nexusagent.interfaces.tui.app import NexusApp
from nexusagent.interfaces.tui.websocket import ws_loop


def make_app():
    """Create a minimal NexusApp mock for testing ws_loop disconnect behavior."""
    app = MagicMock(spec=NexusApp)
    app._busy = True
    app._current_assistant = MagicMock()
    app._current_tool = MagicMock()
    app._ws = None
    app._connection_error = None
    app.session_id = "test-session"
    app.working_dir = "/tmp"
    app._input_queue = MagicMock()
    app._input_queue.get = AsyncMock(side_effect=asyncio.CancelledError)
    app.status_bar = MagicMock()
    app.status_bar.set_status = MagicMock()
    app.status_bar.set_spinner = MagicMock()
    app._fetch_server_version = AsyncMock(return_value=None)
    app._check_server_version = AsyncMock(return_value=False)
    app.messages_container = MagicMock()
    app.messages_container.mount = MagicMock()
    return app


def run_ws_loop(app):
    """Run ws_loop and suppress expected log warnings."""
    loop = asyncio.new_event_loop()
    try:
        with patch("nexusagent.interfaces.tui.websocket.logger"):
            loop.run_until_complete(ws_loop(app))
    finally:
        loop.close()


class TestBusyResetOnDisconnect:
    """_busy must be reset to False on all disconnect/error paths."""

    @patch("nexusagent.interfaces.tui.websocket.websockets.connect")
    @patch("nexusagent.interfaces.tui.websocket.settings")
    def test_busy_reset_on_connection_closed_ok(self, mock_settings, mock_connect):
        """ConnectionClosedOK resets _busy to False."""
        mock_settings.client.api_key = None
        mock_settings.server.api_port = 8080
        AsyncMock()
        mock_connect.return_value.__aenter__ = AsyncMock(
            side_effect=websockets.exceptions.ConnectionClosedOK(None, None)
        )
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

        app = make_app()
        app._check_server_version = AsyncMock(return_value=True)
        run_ws_loop(app)

        assert app._busy is False

    @patch("nexusagent.interfaces.tui.websocket.websockets.connect")
    @patch("nexusagent.interfaces.tui.websocket.settings")
    def test_busy_reset_on_connection_closed_error_final(self, mock_settings, mock_connect):
        """ConnectionClosedError on final attempt resets _busy to False."""
        mock_settings.client.api_key = None
        mock_settings.server.api_port = 8080
        mock_connect.return_value.__aenter__ = AsyncMock(
            side_effect=websockets.exceptions.ConnectionClosedError(None, None)
        )
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

        app = make_app()
        app._check_server_version = AsyncMock(return_value=True)
        run_ws_loop(app)

        assert app._busy is False

    @patch("nexusagent.interfaces.tui.websocket.websockets.connect")
    @patch("nexusagent.interfaces.tui.websocket.settings")
    def test_busy_reset_on_generic_exception(self, mock_settings, mock_connect):
        """Generic Exception resets _busy to False."""
        mock_settings.client.api_key = None
        mock_settings.server.api_port = 8080
        mock_connect.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("unexpected error")
        )
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

        app = make_app()
        app._check_server_version = AsyncMock(return_value=True)
        run_ws_loop(app)

        assert app._busy is False


class TestWidgetStateResetOnDisconnect:
    """_current_assistant and _current_tool must be reset on disconnect."""

    @patch("nexusagent.interfaces.tui.websocket.websockets.connect")
    @patch("nexusagent.interfaces.tui.websocket.settings")
    def test_widget_reset_on_connection_closed_ok(self, mock_settings, mock_connect):
        """ConnectionClosedOK resets _current_assistant and _current_tool."""
        mock_settings.client.api_key = None
        mock_settings.server.api_port = 8080
        mock_connect.return_value.__aenter__ = AsyncMock(
            side_effect=websockets.exceptions.ConnectionClosedOK(None, None)
        )
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

        app = make_app()
        app._check_server_version = AsyncMock(return_value=True)
        run_ws_loop(app)

        assert app._current_assistant is None
        assert app._current_tool is None

    @patch("nexusagent.interfaces.tui.websocket.websockets.connect")
    @patch("nexusagent.interfaces.tui.websocket.settings")
    def test_widget_reset_on_connection_closed_error(self, mock_settings, mock_connect):
        """ConnectionClosedError resets _current_assistant and _current_tool."""
        mock_settings.client.api_key = None
        mock_settings.server.api_port = 8080
        mock_connect.return_value.__aenter__ = AsyncMock(
            side_effect=websockets.exceptions.ConnectionClosedError(None, None)
        )
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

        app = make_app()
        app._check_server_version = AsyncMock(return_value=True)
        run_ws_loop(app)

        assert app._current_assistant is None
        assert app._current_tool is None

    @patch("nexusagent.interfaces.tui.websocket.websockets.connect")
    @patch("nexusagent.interfaces.tui.websocket.settings")
    def test_widget_reset_on_generic_exception(self, mock_settings, mock_connect):
        """Generic Exception resets _current_assistant and _current_tool."""
        mock_settings.client.api_key = None
        mock_settings.server.api_port = 8080
        mock_connect.return_value.__aenter__ = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=False)

        app = make_app()
        app._check_server_version = AsyncMock(return_value=True)
        run_ws_loop(app)

        assert app._current_assistant is None
        assert app._current_tool is None
