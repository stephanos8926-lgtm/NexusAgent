"""NexusAgent Terminal User Interface (TUI).

Features:
- Individual message widgets in Container(layout="stream") for O(1) append
- Semantic color system with Linear-inspired dark theme + 6 community themes
- VerticalScroll for chat area with smart auto-scroll
- Compact status bar with model, CWD, branch, tokens, spinner
- Chat input with history and image detection
- Token-by-token streaming via AssistantMessage.append_token()
- Welcome banner that doesn't scroll away
- Responsive design with 4 breakpoints
- NO_COLOR + ASCII fallback support
- gc.freeze() before first paint
- 7 themes: nexus-dark, tokyo-night, rose-pine, solarized-dark, catppuccin-mocha, gruvbox-dark, nord
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import signal as _signal
import uuid
from datetime import datetime
from typing import Any, ClassVar

import websockets
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.events import Resize
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from nexusagent.infrastructure.config import settings

from nexusagent.widgets.messages import (
    AssistantMessage,
    ErrorMessage,
    ToolCallMessage,
    UserMessage,
    WelcomeBanner,
)
from nexusagent.widgets.status import StatusBar
from nexusagent.widgets.theme import get_css_variable_defaults, register_themes
from nexusagent.widgets.chat_input import ChatInput

# ── Re-exports for backward compatibility (tests import from tui.py) ──
from nexusagent.interfaces.tui_widgets import (  # noqa: F401
    NO_COLOR,
    SpinnerLabel,
    is_no_color,
    _get_terminal_size,
    debounce_resize,
    classify_breakpoint,
)
from nexusagent.interfaces.tui_widgets import ErrorModal as _ErrorModal  # noqa: F401

# Alias for test compatibility
ErrorModal = _ErrorModal
from nexusagent.interfaces.tui_widgets import (
    ApprovalModal,
    Breakpoint,
    _sigwinch_handler,
    classify_breakpoint,
    debounce_resize,
)
from nexusagent.interfaces.tui_formatters import (
    format_arg_value,
    format_tool_output_generic,
    format_tool_result_for_display,
    render_markdown,
    truncate,
    truncate_output,
    _escape,
)

logger = logging.getLogger(__name__)


class NexusApp(App):
    """Main NexusAgent TUI application."""

    TITLE = "NexusAgent"
    SUB_TITLE = "AI Coding Agent"

    BINDINGS: ClassVar = [
        Binding("q", "quit", "Quit", priority=True, show=True),
        Binding("escape", "quit", "Quit", priority=True, show=False),
        Binding("c", "clear", "Clear", show=True),
        Binding("ctrl+c", "interrupt", "Interrupt", show=True),
        Binding("ctrl+u", "interrupt", "Interrupt", show=True),
        Binding("e", "expand_all", "Expand", show=True),
        Binding("a", "collapse_all", "Collapse", show=True),
        Binding("ctrl+underscore", "toggle_auto_approve", "Auto-approve", show=False),
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
        border: solid $border-focus;
    }
    #status-bar {
        height: 1;
        dock: bottom;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        register_themes(self)
        self.theme = self._theme_name

        with VerticalScroll(id="chat"):
            yield Container(id="messages")
        yield ChatInput(id="input-area")
        yield StatusBar(id="status-bar")

    def __init__(self, session_id: str | None = None, yolo: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self._yolo_default = yolo
        self._busy = False
        self._pending_inputs: list[str] = []
        self._current_assistant: AssistantMessage | None = None
        self._current_tool: ToolCallMessage | None = None
        self._theme_name = "nexus-dark"
        self._gc_frozen = False
        self._breakpoint: Breakpoint = Breakpoint.STANDARD
        self._resize_state: dict[str, float] = {}
        self._auto_approve = self._yolo_default or settings.agent.yolo
        self._total_tokens_used = 0
        self._request_count = 0
        self._last_tool_name = ""

    def on_mount(self) -> None:
        self._input_queue: asyncio.Queue[str | None] = asyncio.Queue()
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
        self._ws_task = asyncio.create_task(self._ws_loop())
        self._install_sigwinch()

        if not self._gc_frozen:
            import gc
            gc.freeze()
            self._gc_frozen = True

    # ── Greeting ──────────────────────────────────────────────────────

    def _show_greeting(self) -> None:
        """Show welcome banner at top of message stream (scrolls away as chat grows)."""
        welcome = WelcomeBanner(session_id=self.session_id)
        self.messages_container.mount(welcome)

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

    # ── WebSocket loop ──────────────────────────────────────────────

    async def _ws_loop(self) -> None:
        api_key = settings.client.api_key
        ws_url = f"ws://127.0.0.1:{settings.server.api_port}/sessions/{self.session_id}/ws"
        if api_key:
            ws_url += f"?api_key={api_key}"
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                self._ws = ws
                self.status_bar.set_status("Connected")
                self.status_bar.set_spinner(False)

                async def send_messages():
                    while True:
                        msg = await self._input_queue.get()
                        if msg is None:
                            break
                        await ws.send(json.dumps({"type": "user_input", "content": msg}))

                async def receive_events():
                    async for raw in ws:
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        await self._handle_event(event)

                await asyncio.gather(send_messages(), receive_events())

        except ConnectionRefusedError:
            self.status_bar.set_status("Connection refused")
            self._mount_error(f"Cannot connect to server at port {settings.server.api_port}")
        except websockets.exceptions.ConnectionClosedOK:
            self.status_bar.set_status("Disconnected")
        except websockets.exceptions.ConnectionClosedError as e:
            self.status_bar.set_status("Connection lost")
            self._mount_error(f"Connection lost: {e}")
        except Exception as e:
            self.status_bar.set_status("Error")
            self._mount_error(f"Error: {e}")
        finally:
            self._ws = None

    # ── Event handling ──────────────────────────────────────────────

    async def _handle_event(self, event: dict) -> None:
        etype = event.get("type")

        if etype == "session_status":
            pass

        elif etype == "thinking":
            content = event.get("content", "")
            if content and content != "Processing...":
                thinking = AppMessage(content=content)
                self.messages_container.mount(thinking)
                self.status_bar.set_status("Thinking...")

        elif etype == "tool_call":
            tool = event.get("tool", "?")
            args = event.get("args", {})
            self._last_tool_name = tool

            args_str = self._format_args_str(args)

            if isinstance(args, dict):
                args_display = ", ".join(
                    f"{k}={truncate(format_arg_value(v), 60)}"
                    for k, v in args.items()
                )
            else:
                args_display = truncate(format_arg_value(args), 80)

            msg = ToolCallMessage(
                tool=tool,
                args=args_display,
                status="running",
            )
            self._current_tool = msg
            self.messages_container.mount(msg)

            if self._auto_approve and tool != "tool_search":
                call_id = event.get("call_id", "")
                self._auto_approve_task = asyncio.create_task(self._send_approval(call_id, True))

            self.status_bar.set_status(f"Running: {tool}")

        elif etype == "tool_result":
            output = event.get("output", "")
            success = event.get("success", True)

            if self._current_tool:
                self._current_tool.update_output(output)
                self._current_tool.update_status("success" if success else "failed")
            else:
                msg = ToolCallMessage(
                    tool=self._last_tool_name,
                    args="",
                    output=output,
                    status="success" if success else "failed",
                )
                self.messages_container.mount(msg)

            self.status_bar.set_status("Processing response...")

        elif etype == "tool_error":
            tool = event.get("tool", "?")
            error = event.get("error", "Unknown error")
            err_msg = ErrorMessage(message=f"{tool}: {error}")
            self.messages_container.mount(err_msg)
            self.status_bar.set_status(f"Error in {tool}")

        elif etype == "approval_request":
            tool = event.get("tool", "?")
            args = event.get("args", {})
            call_id = event.get("call_id", "")
            self.status_bar.set_status("Awaiting approval...")
            approved = await self.push_screen_wait(ApprovalModal(tool, args, call_id))
            await self._send_approval(call_id, approved)
            self.status_bar.set_status("Ready")

        elif etype == "response_chunk":
            content = event.get("content", "")
            if self._current_assistant is None:
                self._current_assistant = AssistantMessage()
                self.messages_container.mount(self._current_assistant)
            await self._current_assistant.append_token(content)
            self.status_bar.set_status("Streaming...")

        elif etype == "response":
            content = event.get("content", "")
            if self._current_assistant:
                final = render_markdown(content) if content else None
                if final:
                    self._current_assistant.finalize(final)
                self._current_assistant = None
            elif content:
                msg = AssistantMessage()
                msg.finalize(render_markdown(content))
                self.messages_container.mount(msg)

            self._busy = False
            self._request_count += 1
            tokens = event.get("tokens_used", 0)
            if tokens:
                self._total_tokens_used += tokens
                self.status_bar.set_tokens(self._total_tokens_used)

            self._process_next_in_queue()
            self.status_bar.set_status("Ready")
            self._current_tool = None

        elif etype == "error":
            message = event.get("message", "Unknown error")
            self._mount_error(message)
            self._busy = False
            self._process_next_in_queue()
            self.status_bar.set_status("Error")

        elif etype == "session_closed":
            self.status_bar.set_status("Disconnected")
            self._busy = False
            self._ws = None

    def _format_args_str(self, args: dict) -> str:
        if not isinstance(args, dict):
            return truncate(format_arg_value(args), 80)
        parts = []
        for k, v in args.items():
            parts.append(f"{k}={truncate(format_arg_value(v), 60)}")
        return ", ".join(parts)

    def _mount_error(self, message: str) -> None:
        err = ErrorMessage(message=message)
        self.messages_container.mount(err)

    # ── Slash commands ───────────────────────────────────────────────

    async def _handle_slash_command(self, cmd: str) -> bool:
        parts = cmd.strip().lower().split()
        command = parts[0] if parts else ""
        rest = parts[1:] if len(parts) > 1 else []

        if command in ("/help", "/h"):
            self._show_help()
            return True
        if command in ("/new", "/n"):
            self.messages_container.clear()
            self._show_greeting()
            return True
        if command == "/clear":
            self.messages_container.clear()
            self._show_greeting()
            return True
        if command in ("/expand", "/e"):
            return True  # Widgets auto-expand
        if command in ("/collapse", "/a"):
            return True  # TODO: collapse all
        if command in ("/quit", "/q"):
            self.action_quit()
            return True
        if command == "/status":
            status = "busy" if self._busy else "ready"
            auto = "ON" if self._auto_approve else "OFF"
            msg = AppMessage(
                f"Status: {status} | Session: {self.session_id} | "
                f"Queued: {len(self._pending_inputs)} | Auto-approve: {auto} | "
                f"Tokens: {self._total_tokens_used:,} | Requests: {self._request_count}"
            )
            self.messages_container.mount(msg)
            return True
        if command == "/version":
            msg = AppMessage(
                f"NexusAgent v0.1.0 | Model: {settings.agent.default_model} | "
                f"Session: {self.session_id} | Theme: {self._theme_name}"
            )
            self.messages_container.mount(msg)
            return True
        if command == "/tokens":
            avg = self._total_tokens_used // self._request_count if self._request_count > 0 else 0
            msg = AppMessage(
                f"Token Usage\n"
                f"  Total: {self._total_tokens_used:,}\n"
                f"  Requests: {self._request_count}\n"
                f"  Avg/request: {avg:,}\n"
                f"  Model: {settings.agent.default_model}"
            )
            self.messages_container.mount(msg)
            return True
        if command == "/model":
            msg = AppMessage(
                f"Model: {settings.agent.default_model}\n"
                f"Provider: {settings.agent.primary_provider}\n"
                f"Session: {self.session_id}"
            )
            self.messages_container.mount(msg)
            return True
        if command == "/theme":
            self._cycle_theme()
            return True
        if command == "/auto":
            self.action_toggle_auto_approve()
            return True
        if command == "/compact":
            if self._ws and self._ws.open:
                await self._ws.send(json.dumps({"type": "compact"}))
                self.status_bar.set_status("Compacting...")
            return True
        if command == "/copy":
            msg = AppMessage("Copy not available — use terminal selection")
            self.messages_container.mount(msg)
            return True
        if command == "/sessions":
            msg = AppMessage(f"Session: {self.session_id}")
            self.messages_container.mount(msg)
            return True
        if command == "/threads":
            if self._ws and self._ws.open:
                await self._ws.send(json.dumps({"type": "list_sessions"}))
            return True
        if command == "/interrupt":
            self.action_interrupt()
            return True
        if command == "/undo":
            if self._ws and self._ws.open:
                await self._ws.send(json.dumps({"type": "undo"}))
            return True
        if command == "/redo":
            if self._ws and self._ws.open:
                await self._ws.send(json.dumps({"type": "redo"}))
            return True
        if command == "/skills":
            from nexusagent.skills import load_all_skills, get_skills_summary
            skills = load_all_skills()
            if skills:
                get_skills_summary(skills)
                lines = [f"Available Skills ({len(skills)})"]
                for name, skill in sorted(skills.items()):
                    desc = skill.description or "No description"
                    lines.append(f"  {name}: {desc}")
                msg = AppMessage("\n".join(lines))
                self.messages_container.mount(msg)
            return True
        if command.startswith("/skill"):
            skill_name = rest[0] if rest else ""
            if not skill_name:
                msg = AppMessage("Usage: /skill <name>")
                self.messages_container.mount(msg)
                return True
            from nexusagent.skills import load_all_skills, get_skill_content
            skills = load_all_skills()
            skill_content = get_skill_content(skills, skill_name)
            if skill_content:
                lines = [f"Skill: {skill_name}"]
                for line in skill_content.split("\n")[:20]:
                    lines.append(f"  {line}")
                if len(skill_content.split("\n")) > 20:
                    lines.append(f"  ... ({len(skill_content.split(chr(10)))} lines total)")
                msg = AppMessage("\n".join(lines))
                self.messages_container.mount(msg)
            return True

        msg = AppMessage(f"Unknown command: {command}. Type /help for available commands.")
        self.messages_container.mount(msg)
        return True

    def _cycle_theme(self) -> None:
        from nexusagent.widgets.theme.colors import ALL_THEMES
        try:
            idx = ALL_THEMES.index(self._theme_name)
            self._theme_name = ALL_THEMES[(idx + 1) % len(ALL_THEMES)]
        except ValueError:
            self._theme_name = "nexus-dark"
        self.theme = self._theme_name
        msg = AppMessage(f"Theme: {self._theme_name}")
        self.messages_container.mount(msg)

    def _show_help(self) -> None:
        lines = [
            "Available Commands",
            "  /help      Show this help",
            "  /new       New conversation",
            "  /clear     Clear messages",
            "  /expand    Expand all",
            "  /collapse  Collapse all",
            "  /status    Session status",
            "  /compact   Trigger compaction",
            "  /version   Version info",
            "  /tokens    Token usage",
            "  /model     Model info",
            "  /theme     Cycle theme",
            "  /auto      Toggle auto-approve",
            "  /skills    List skills",
            "  /skill <n> Show skill",
            "  /quit      Exit",
            "",
            "Keyboard Shortcuts",
            "  Ctrl+C  Interrupt",
            "  Q       Quit",
            "  C       Clear",
            "  E       Expand",
            "  A       Collapse",
        ]
        msg = AppMessage("\n".join(lines))
        self.messages_container.mount(msg)

    # ── Queue management ────────────────────────────────────────────

    def _process_next_in_queue(self) -> None:
        if not self._pending_inputs:
            return
        next_msg = self._pending_inputs.pop(0)
        self._busy = True
        user_msg = UserMessage(content=next_msg)
        self.messages_container.mount(user_msg)
        self.status_bar.set_status("Thinking...")
        self.status_bar.set_spinner(True)
        asyncio.create_task(self._input_queue.put(next_msg))  # noqa: RUF006
        self._update_queue_status()

    def _update_queue_status(self) -> None:
        count = len(self._pending_inputs)
        if count > 0:
            self.status_bar.set_status(f"{count} queued")

    async def _send_approval(self, call_id: str, approved: bool) -> None:
        if self._ws and self._ws.open:
            await self._ws.send(json.dumps({
                "type": "approval",
                "call_id": call_id,
                "approved": approved,
            }))

    # ── Input handling ──────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return

        if message.startswith("/"):
            event.input.value = ""
            await self._handle_slash_command(message)
            return

        if self._busy:
            self._pending_inputs.append(message)
            msg = AppMessage(f"Queued: {message}")
            self.messages_container.mount(msg)
            self._update_queue_status()
            event.input.value = ""
            return

        self._busy = True
        user_msg = UserMessage(content=message)
        self.messages_container.mount(user_msg)
        event.input.value = ""
        self.status_bar.set_status("Thinking...")
        self.status_bar.set_spinner(True)
        await self._input_queue.put(message)

    # ── Actions ─────────────────────────────────────────────────────

    def action_clear(self) -> None:
        self.messages_container.clear()
        self._show_greeting()

    def action_quit(self) -> None:
        asyncio.create_task(self._input_queue.put(None))  # noqa: RUF006
        if hasattr(self, '_ws_task'):
            self._ws_task.cancel()
        self.exit()

    def action_interrupt(self) -> None:
        if self._ws and self._ws.open:
            self._interrupt_task = asyncio.create_task(
                self._ws.send(json.dumps({"type": "interrupt"}))
            )
            self.status_bar.set_status("Interrupting...")
            msg = AppMessage("Interrupt sent — waiting for agent to stop...")
            self.messages_container.mount(msg)

    def action_expand_all(self) -> None:
        pass  # Widgets auto-expand

    def action_collapse_all(self) -> None:
        pass  # TODO: collapse all tool outputs

    def action_toggle_auto_approve(self) -> None:
        self._auto_approve = not self._auto_approve
        if self._auto_approve:
            msg = AppMessage("Auto-approve enabled")
            self.messages_container.mount(msg)
        else:
            msg = AppMessage("Auto-approve disabled")
            self.messages_container.mount(msg)


def main(yolo: bool = False) -> None:
    app = NexusApp(yolo=yolo)
    app.run()


if __name__ == "__main__":
    main()
