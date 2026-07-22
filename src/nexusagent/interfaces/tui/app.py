"""NexusApp — core TUI application class.

Composes the layout, manages lifecycle, and delegates to:
- websocket.py: WebSocket connection and event loop
- streaming.py: Event handling and slash commands
- input.py: Chat input handling and queue management
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import signal as _signal
import uuid
from typing import Any, ClassVar

import websockets
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll

from nexusagent.infrastructure.config import settings
from nexusagent.interfaces.tui.input import (
    on_chat_input_submitted as _on_chat_input_submitted,
)
from nexusagent.interfaces.tui.streaming import (
    cycle_theme,
    handle_event,
    handle_slash_command,
    show_help,
)
from nexusagent.interfaces.tui.websocket import (
    check_server_version,
    fetch_server_version,
    ws_loop,
)
from nexusagent.interfaces.tui_widgets import (
    Breakpoint,
    _sigwinch_handler,
)
from nexusagent.widgets.chat_input import ChatInput
from nexusagent.widgets.messages import (
    AppMessage,
    AssistantMessage,
    ToolCallMessage,
    WelcomeBanner,
)
from nexusagent.widgets.status import StatusBar
from nexusagent.widgets.theme import register_themes

logger = logging.getLogger(__name__)


class NexusApp(App):
    """Main NexusAgent TUI application."""

    TITLE = "NexusAgent"
    SUB_TITLE = "AI Coding Agent"

    BINDINGS: ClassVar = [
        Binding("ctrl+q", "quit", "Quit", priority=True, show=True),
        Binding("ctrl+c", "interrupt", "Interrupt", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
        Binding("ctrl+t", "cycle_theme", "Theme", show=True),
        Binding("ctrl+underscore", "toggle_auto_approve", "Auto-approve", show=False),
        Binding("ctrl+y", "toggle_auto_approve", "YOLO", show=True),
        Binding("f1", "show_help", "Help", show=True),
        # Legacy single-key bindings (lower priority so they don't eat input)
        Binding("q", "quit", "Quit", priority=False, show=False),
        Binding("escape", "quit", "Quit", priority=False, show=False),
        Binding("c", "clear", "Clear", show=False),
        Binding("ctrl+u", "interrupt", "Interrupt", show=False),
        Binding("e", "expand_all", "Expand", show=False),
        Binding("a", "collapse_all", "Collapse", show=False),
    ]

    CSS = """
    Screen {
        layout: vertical;
        layers: base overlay;
        background: $background;
    }
    * {
        scrollbar-size-vertical: 1;
    }
    #chat {
        height: 1fr;
        padding: 0 1;
        background: $background;
        overflow-y: scroll;
        overflow-x: hidden;
    }
    #messages {
        layout: stream;
        height: auto;
    }
    #input-area {
        height: auto;
        min-height: 3;
        max-height: 15;
        background: $surface;
        border: solid $border;
        padding: 0 1;
    }
    #input-area:focus {
        border: solid $primary;
    }
    #status-bar {
        height: 1;
        dock: bottom;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the TUI layout: chat area, input, and status bar."""
        register_themes(self)
        self.theme = self._theme_name

        with VerticalScroll(id="chat"):
            yield Container(id="messages")
        yield ChatInput(id="input-area")
        yield StatusBar(id="status-bar")

    def __init__(self, session_id: str | None = None, yolo: bool = False, **kwargs: Any) -> None:
        """Initialize the NexusAgent TUI application.

        Args:
            session_id: Optional session identifier. Auto-generated if not provided.
            yolo: If True, enable auto-approve mode by default.
            **kwargs: Additional keyword arguments passed to the App base class.
        """
        super().__init__(**kwargs)
        self.session_id = session_id or str(uuid.uuid4())
        self._yolo_default = yolo
        self._busy = False
        self._pending_inputs: list[str] = []
        self._pending_inputs_max = 100  # Prevent memory exhaustion from spam
        self._current_assistant: AssistantMessage | None = None
        self._current_tool: ToolCallMessage | None = None
        self._theme_name = "nexus-dark"
        self._gc_frozen = False
        self._breakpoint: Breakpoint = Breakpoint.STANDARD
        self._resize_state: dict[str, float] = {}
        self._auto_approve = self._yolo_default or settings.agent.yolo
        self._auto_approve_lock = asyncio.Lock()  # Prevent TOCTOU race in approval
        self._total_tokens_used = 0
        self._request_count = 0
        self._last_tool_name = ""
        self._context_used = 0
        self._context_limit = 0
        # Track seen tool calls/results to prevent duplicate rendering (for /new command)
        self._seen_tool_calls = set()
        self._seen_tool_results = set()
        self._call_id_to_tool: dict[str, str] = {}
        self._approved_call_ids: set[str] = set()
        # Collapse repeated identical failures (tool name + error text)
        self._last_failure_key: tuple[str, str] | None = None
        self._failure_repeat_count: int = 0
        self._failure_summary_widget: ToolCallMessage | None = None

    # ── Message widget sliding window ────────────────────────────────────

    _MAX_MESSAGE_WIDGETS = 50

    def _mount_message(self, widget) -> None:
        """Mount a message widget with a sliding window limit.

        Keeps only the last _MAX_MESSAGE_WIDGETS mounted. When the limit
        is exceeded, the oldest widget is removed to bound memory usage.
        """
        self.messages_container.mount(widget)
        children = list(self.messages_container.children)
        while len(children) > self._MAX_MESSAGE_WIDGETS:
            oldest = children.pop(0)
            oldest.remove()

    def _mount_with_limit(self, widget) -> None:
        """Mount any widget with the global _MAX_MESSAGE_WIDGETS limit.

        Alias for _mount_message — keeps all mount paths under the same limit.
        """
        self._mount_message(widget)

    def on_mount(self) -> None:
        """Set up the TUI on mount: initialize queues, widgets, and start WebSocket loop."""
        self._input_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=100)
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._ws_task: asyncio.Task | None = None
        self._auto_approve_task: asyncio.Task | None = None
        self._interrupt_task: asyncio.Task | None = None

        self.messages_container = self.query_one("#messages", Container)
        self.status_bar = self.query_one("#status-bar", StatusBar)
        self.chat_input = self.query_one("#input-area", ChatInput)

        self.status_bar.set_status("Connecting...")
        self.status_bar.set_cwd(str(pathlib.Path.cwd()))
        self.status_bar.set_model(settings.agent.primary_provider, settings.agent.default_model)
        self.status_bar.set_spinner(True)

        self._show_greeting()
        self._ws_task = asyncio.create_task(ws_loop(self))
        self._install_sigwinch()
        self._refresh_git_branch()

        if not self._gc_frozen:
            import gc

            gc.freeze()
            self._gc_frozen = True

    # ── Git branch detection ────────────────────────────────────────────

    def _refresh_git_branch(self) -> None:
        """Schedule asynchronous detection of git branch and status to update the status bar."""
        async def _async_detect():
            import subprocess

            from nexusagent.widgets.status import GitStatus

            def _get_git_info():
                try:
                    res_branch = subprocess.run(
                        ["git", "branch", "--show-current"],
                        capture_output=True,
                        text=True,
                        timeout=3,
                        cwd=str(pathlib.Path.cwd()),
                    )
                    branch = res_branch.stdout.strip() if res_branch.returncode == 0 else ""
                    status = GitStatus.detect()
                    return branch, status
                except Exception:
                    return "", None

            branch, status = await asyncio.to_thread(_get_git_info)
            if branch:
                self.status_bar.set_branch(branch)
                self.status_bar.set_git_status(status)

        asyncio.create_task(_async_detect())

    # ── Greeting ──────────────────────────────────────────────────────

    def _show_greeting(self) -> None:
        """Show welcome banner at top of message stream (scrolls away as chat grows)."""
        welcome = WelcomeBanner(session_id=self.session_id)
        self._mount_message(welcome)
        # Show connection error as a hint (not as a message widget)
        if getattr(self, "_connection_error", None):
            from nexusagent.widgets.messages import AppMessage

            hint = AppMessage(
                f"⚠ {self._connection_error} Start the server with: nexusagent.server"
            )
            self._mount_message(hint)

    # ── SIGWINCH (responsive resize) ────────────────────────────────────

    def _install_sigwinch(self) -> None:
        """Install SIGWINCH signal handler for responsive terminal resizing."""
        try:
            sig = _signal.SIGWINCH
        except AttributeError:
            logger.debug("SIGWINCH not available on this platform")
            return

        def _handler(signum: int, frame: Any) -> None:
            self._sigwinch_pending = True

        self._sigwinch_pending = False
        self._original_sigwinch = _signal.getsignal(sig)
        _signal.signal(sig, _handler)
        logger.debug("SIGWINCH handler installed")

    def _check_sigwinch(self) -> None:
        """Check if a SIGWINCH was received and process it."""
        if getattr(self, "_sigwinch_pending", False):
            self._sigwinch_pending = False
            _sigwinch_handler(self)

    def _restore_sigwinch(self) -> None:
        """Restore the original SIGWINCH signal handler."""
        if hasattr(self, "_original_sigwinch"):
            try:
                _signal.signal(_signal.SIGWINCH, self._original_sigwinch)
                logger.debug("SIGWINCH handler restored")
            except Exception as exc:
                logger.debug(f"Failed to restore SIGWINCH handler: {exc}")

    # ── Actions ─────────────────────────────────────────────────────

    def action_clear(self) -> None:
        """Clear all messages and show the welcome greeting."""
        self.messages_container.clear()
        self._current_assistant = None
        self._current_tool = None
        if hasattr(self, "_seen_tool_calls"):
            self._seen_tool_calls.clear()
        if hasattr(self, "_seen_tool_results"):
            self._seen_tool_results.clear()
        if hasattr(self, "_call_id_to_tool"):
            self._call_id_to_tool.clear()
        if hasattr(self, "_approved_call_ids"):
            self._approved_call_ids.clear()
        self._show_greeting()

    def action_quit(self) -> None:
        """Quit the TUI application, canceling background tasks."""
        _ = asyncio.create_task(self._input_queue.put(None))
        if hasattr(self, "_ws_task"):
            self._ws_task.cancel()
        self.exit()

    def action_interrupt(self) -> None:
        """Send an interrupt signal to the running agent."""
        if self._ws:
            self._interrupt_task = asyncio.create_task(
                self._ws.send(json.dumps({"type": "interrupt"}))
            )
            self.status_bar.set_status("Interrupting...")
            msg = AppMessage("Interrupt sent — waiting for agent to stop...")
            self._mount_message(msg)

    def action_expand_all(self) -> None:
        """Expand all collapsed tool call outputs."""
        for widget in self.messages_container.query(ToolCallMessage):
            if widget._collapsed:
                widget.toggle_collapse()

    def action_collapse_all(self) -> None:
        """Collapse all expanded tool call outputs."""
        for widget in self.messages_container.query(ToolCallMessage):
            if not widget._collapsed and widget._output:
                widget.toggle_collapse()

    def action_cycle_theme(self) -> None:
        """Cycle through available themes (Ctrl+T)."""
        cycle_theme(self)

    def action_show_help(self) -> None:
        """Show help panel (F1)."""
        show_help(self)

    def action_toggle_auto_approve(self) -> None:
        """Toggle auto-approve mode for tool calls on or off."""
        self._auto_approve = not self._auto_approve
        if self._auto_approve:
            msg = AppMessage("Auto-approve enabled")
            self._mount_message(msg)
        else:
            msg = AppMessage("Auto-approve disabled")
            self._mount_message(msg)

    # ── Input handling (delegates to input.py) ──────────────────────────

    async def on_chat_input_submitted(self, event) -> None:
        """Handle chat input submission. Delegates to input module."""
        await _on_chat_input_submitted(self, event)
        self._refresh_git_branch()

    # ── Internal method wrappers for backward compat (tests call these) ──

    async def _handle_event(self, event: dict) -> None:
        """Handle a WebSocket event. Delegates to streaming module."""
        await handle_event(self, event)

    async def _check_server_version(self) -> bool:
        """Check server version. Delegates to websocket module."""
        return await check_server_version(self)

    async def _fetch_server_version(self) -> dict | None:
        """Fetch server version. Delegates to websocket module."""
        return await fetch_server_version(self)

    async def _ws_loop(self) -> None:
        """WebSocket event loop. Delegates to websocket module."""
        await ws_loop(self)

    async def _handle_slash_command(self, cmd: str) -> bool:
        """Handle a slash command. Delegates to streaming module."""
        return await handle_slash_command(self, cmd)


import click


@click.command()
@click.option(
    "--yolo",
    "-y",
    "--auto-approve",
    is_flag=True,
    default=False,
    help="Enable YOLO auto-approve mode for all tools by default."
)
def main(yolo: bool = False) -> None:
    """Entry point for launching the NexusAgent TUI."""
    app = NexusApp(yolo=yolo)
    app.run()


if __name__ == "__main__":
    main()
