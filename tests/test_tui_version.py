"""Tests for TUI pre-connect version checking.

Covers:
- HTTP version fetch before WebSocket connect
- Version mismatch warning shown as non-blocking AppMessage
- Unreachable server handled gracefully
- /version command shows dynamic version from VERSION module
"""

import asyncio
import json
import urllib.request
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.interfaces.tui import NexusApp
from nexusagent.version import VERSION


class TestTuiVersionCheck:
    """Test the _check_server_version method on NexusApp."""

    def _make_app(self) -> NexusApp:
        """Create a NexusApp without calling on_mount."""
        app = NexusApp.__new__(NexusApp)
        app.session_id = "test123"
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

    @pytest.mark.asyncio
    async def test_tui_fetches_version_before_ws_connect(self):
        """_check_server_version should hit GET /version via urllib."""
        app = self._make_app()

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({
            "version": "0.1.0",
            "minClient": "0.1.0",
            "server": "nexusagent-server",
            "uptime": 100,
        }).encode()
        fake_response.__enter__ = MagicMock(return_value=fake_response)
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
            result = await app._check_server_version()

        assert result is True, "Version check should succeed when versions match"
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        assert "/version" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_tui_shows_version_mismatch_warning(self):
        """When server version mismatches, show AppMessage warning (non-blocking)."""
        app = self._make_app()

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({
            "version": "0.2.0",
            "minClient": "0.1.0",
            "server": "nexusagent-server",
            "uptime": 100,
        }).encode()
        fake_response.__enter__ = MagicMock(return_value=fake_response)
        fake_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake_response):
            result = await app._check_server_version()

        # Mismatch is non-blocking: returns True (don't block connect)
        assert result is True
        # But an AppMessage warning should be mounted
        app.messages_container.mount.assert_called_once()
        mounted_msg = app.messages_container.mount.call_args[0][0]
        assert "version" in mounted_msg._message.lower()
        assert "0.2.0" in mounted_msg._message

    @pytest.mark.asyncio
    async def test_tui_shows_unreachable_message(self):
        """When server is unreachable, return False and show error."""
        app = self._make_app()

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = await app._check_server_version()

        assert result is False, "Unreachable server should return False"
        app.messages_container.mount.assert_called_once()
        mounted_msg = app.messages_container.mount.call_args[0][0]
        assert "unreachable" in mounted_msg._message.lower() or "connect" in mounted_msg._message.lower()

    @pytest.mark.asyncio
    async def test_tui_version_check_timeout(self):
        """Timeout on version fetch should be handled gracefully."""
        app = self._make_app()

        with patch(
            "urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            result = await app._check_server_version()

        assert result is False

    def test_tui_version_command_shows_dynamic_version(self):
        """/version command should use VERSION module, not hardcoded string."""
        app = self._make_app()

        # Call the slash command handler directly
        result = asyncio.run(app._handle_slash_command("/version"))

        assert result is True
        app.messages_container.mount.assert_called_once()
        mounted_msg = app.messages_container.mount.call_args[0][0]
        # Must contain the dynamic version, not a hardcoded "0.1.0"
        assert VERSION in mounted_msg._message
        # Must NOT be the old hardcoded format
        assert "NexusAgent v0.1.0" not in mounted_msg._message


class TestTuiWsLoopVersionIntegration:
    """Test that _ws_loop calls _check_server_version before websockets.connect."""

    def _make_app(self) -> NexusApp:
        app = NexusApp.__new__(NexusApp)
        app.session_id = "test456"
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

    @pytest.mark.asyncio
    async def test_ws_loop_calls_version_check_before_connect(self):
        """_ws_loop should call _check_server_version before websockets.connect."""
        app = self._make_app()
        call_order = []

        async def fake_check():
            call_order.append("version_check")
            return True

        fake_ws = AsyncMock()
        fake_ws.__aenter__ = AsyncMock(return_value=fake_ws)
        fake_ws.__aexit__ = AsyncMock(return_value=False)
        fake_ws.open = True
        fake_ws.send = AsyncMock()
        fake_ws.__aiter__ = AsyncMock(return_value=iter([]))

        app._check_server_version = fake_check

        with patch("websockets.connect", return_value=fake_ws) as mock_ws_connect:
            # Run _ws_loop but stop after first iteration
            task = asyncio.create_task(app._ws_loop())
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        assert "version_check" in call_order, "version check must be called"
        # version_check should come before websockets.connect
        version_idx = call_order.index("version_check")
        ws_idx = call_order.index("ws_connect") if "ws_connect" in call_order else len(call_order)
        assert version_idx < ws_idx, "version check must precede ws connect"
