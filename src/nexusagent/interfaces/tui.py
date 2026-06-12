"""Terminal UI for NexusAgent — real-time streaming chat interface.

Features:
- Word-wrapped conversation log (no horizontal scroll)
- Real-time tool call/result streaming with collapsible output
- Greeting screen with help on login
- Slash commands: /new, /sessions, /help, /clear, /expand, /collapse, /quit, /compact, /copy, /version, /tokens, /model, /threads, /theme
- Markdown rendering for agent responses
- Status bar with spinner, state, and queued message count
- Interrupt support (Ctrl+C, Ctrl+U) — cancels running agent turn
- Error display when tools fail (web search, subagent, etc.)
- Auto-scroll with manual override
- Per-tool output formatters for shell, read_file, write_file/edit_file, git_*, search_web, spawn_subagent
- Session metadata tracking (tokens)
- Auto-approve mode toggle (Ctrl+_)
"""

import asyncio
import json
import logging
import os
import re
import signal as _signal
import textwrap
import uuid
from datetime import datetime
from typing import Any, ClassVar

logger = logging.getLogger(__name__)

import websockets
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Header,
    Input,
    RichLog,
    Static,
)

from nexusagent.infrastructure.config import settings

# Import extracted widgets
from nexusagent.interfaces.tui_widgets import (
    ApprovalModal,
    Breakpoint,
    ErrorModal,
    SpinnerLabel,
    NO_COLOR,
    _get_terminal_size,
    _sigwinch_handler,
    classify_breakpoint,
    debounce_resize,
    is_no_color,
)

# Import extracted formatters
from nexusagent.interfaces.tui_formatters import (
    format_arg_value,
    format_tool_output_generic,
    format_tool_result_for_display,
    render_markdown,
    truncate,
    truncate_output,
    _escape,
)

# Color themes for /theme cycling
NEXUS_THEMES = [
    {"name": "midnight", "header_bg": "#1f2937", "accent": "#10b981", "bg": "#111827"},
    {"name": "ocean", "header_bg": "#0e4d6e", "accent": "#38bdf8", "bg": "#0c1929"},
    {"name": "forest", "header_bg": "#14532d", "accent": "#4ade80", "bg": "#052e16"},
    {"name": "sunset", "header_bg": "#7c2d12", "accent": "#fb923c", "bg": "#1c1010"},
    {"name": "lavender", "header_bg": "#3b3864", "accent": "#a78bfa", "bg": "#1a1830"},
]


# ═══════════════════════════════════════════════════════════════════════════
# NexusApp — main TUI application
# ═══════════════════════════════════════════════════════════════════════════

class NexusApp(App):
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
        layers: base overlay;
        background: #111827;
    }

    /* ── Conversation log ── */
    #log-container {
        width: 100%;
        height: 1fr;
        border: solid #1f2937;
        margin: 0 1;
    }

    #conversation-log {
        width: 100%;
        max-width: 100%;
        height: auto;
        min-height: 100%;
        background: #111827;
        padding: 1 2;
        overflow-y: auto;
        overflow-x: hidden;
        text-wrap: wrap;
        word-wrap: break-word;
    }

    /* ── Streaming response ── */
    #streaming-response {
        height: auto;
        min-height: 1;
        width: 100%;
        max-width: 100%;
        color: #93c5fd;
        padding: 1 2;
        margin: 0 1;
        background: #1f2937;
        border-left: wide #3b82f6;
        overflow-x: hidden;
        text-wrap: wrap;
        word-wrap: break-word;
    }

    /* ── Input area ── */
    #input-area {
        border: solid #374151;
        height: 3;
        margin: 0 1;
        padding: 0 1;
        background: #1f2937;
    }
    #input-area:focus {
        border: solid #10b981;
    }

    /* ── Status bar ── */
    #status-bar {
        height: 1;
        background: #1f2937;
        color: #9ca3af;
        padding: 0 2;
    }
    #status-bar SpinnerLabel { width: 100%; }

    /* ── Auto-approve indicator ── */
    #auto-approve-badge {
        height: 1;
        background: #1f2937;
        color: #fbbf24;
        text-style: bold;
        padding: 0 2;
    }

    /* ── Queue status ── */
    #queue-status {
        color: #6b7280;
        text-style: italic;
        height: 1;
        padding: 0 2;
    }

    /* ── Collapsible tool results ── */
    Collapsible {
        border-left: wide #fbbf24;
        margin: 1 2;
        padding: 0 0 0 1;
        background: #1f2937;
    }
    Collapsible > .collapsible--content {
        padding: 1 2;
        color: #d1d5db;
    }
    Collapsible > .collapsible--header {
        color: #fbbf24;
        text-style: bold;
        padding: 0 1;
    }
    Collapsible.-collapsed > .collapsible--header {
        color: #6b7280;
    }

    /* ── Approval / Error modal ── */
    #approval-dialog {
        width: 80%;
        height: auto;
        max-height: 20;
        border: solid #fbbf24;
        background: #1f2937;
        padding: 1 2;
    }
    #approval-title {
        text-style: bold;
        color: #fbbf24;
        padding: 0 0 1 0;
    }
    #approval-args {
        color: #d1d5db;
        padding: 0 0 1 0;
    }
    #approval-buttons {
        height: 3;
        align: right middle;
    }
    #approval-buttons Button {
        margin-left: 1;
    }
    #approval-scroll {
        max-height: 12;
    }

    /* ── Header / Footer ── */
    Header {
        background: #1f2937;
        color: #10b981;
        text-style: bold;
    }
    Footer {
        background: #1f2937;
        color: #6b7280;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            RichLog(id="conversation-log", markup=True, auto_scroll=True, wrap=True),
            id="log-container",
        )
        yield Static("", id="streaming-response")
        yield SpinnerLabel("Ready", id="status-bar")
        yield Static("", id="auto-approve-badge")
        yield Static("", id="queue-status")
        yield Input(
            placeholder="Type a message, @file to inject, or /help for commands...",
            id="input-area",
        )
        yield Footer()

    def __init__(self, session_id: str | None = None, yolo: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self._yolo_default = yolo
        self._breakpoint: Breakpoint = Breakpoint.STANDARD
        self._resize_state: dict[str, float] = {}
        self._no_color: bool = NO_COLOR

    def on_mount(self) -> None:
        self.session_id = str(uuid.uuid4())[:8]
        self.log_widget = self.query_one("#conversation-log", RichLog)
        self.status_widget = self.query_one("#status-bar", SpinnerLabel)
        self.queue_status = self.query_one("#queue-status", Static)
        self._streaming_widget = self.query_one("#streaming-response", Static)
        self._streaming_response: str = ""  # accumulated streaming text
        self._input_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._busy = False
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._collapsibles: list[Collapsible] = []
        self._pending_inputs: list[str] = []
        self._current_task: asyncio.Task | None = None  # for interrupt
        self._auto_approve = self._yolo_default or settings.agent.yolo
        self._auto_approve_task: asyncio.Task | None = None
        self._interrupt_task: asyncio.Task | None = None
        self._theme_index = 0
        self._total_tokens_used = 0
        self._request_count = 0
        self._auto_approve_badge = self.query_one("#auto-approve-badge", Static)
        self._auto_approve_badge.update("")

        self._show_greeting()
        self._ws_task = asyncio.create_task(self._ws_loop())

        # Install SIGWINCH handler for responsive layout
        self._install_sigwinch()

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

    def _is_ascii_terminal(self) -> bool:
        """Detect if we're in an ASCII-only terminal (no color support)."""
        if is_no_color():
            return True
        if os.environ.get("TERM") == "dumb":
            return True
        if not os.environ.get("COLORTERM"):
            return True
        return False

    # ── Greeting ──────────────────────────────────────────────────────

    def _show_greeting(self):
        ts = datetime.now().strftime("%H:%M")
        self.log_widget.write("", shrink=False)
        self.log_widget.write(
            "[b cyan]╔══════════════════════════════════════════╗[/b cyan]",
            shrink=False,
        )
        self.log_widget.write(
            "[b cyan]║[/b cyan]  [b white]NexusAgent[/b white] — Interactive AI Agent    [b cyan]║[/b cyan]",
            shrink=False,
        )
        self.log_widget.write(
            f"[b cyan]║[/b cyan]  Session: [yellow]{self.session_id}[/yellow]  {ts}              [b cyan]║[/b cyan]",
            shrink=False,
        )
        self.log_widget.write(
            "[b cyan]╚══════════════════════════════════════════╝[/b cyan]",
            shrink=False,
        )
        self.log_widget.write("", shrink=False)
        self.log_widget.write(
            "[dim]Commands: [b]/help[/b]  [b]/new[/b]  [b]/clear[/b]  [b]/expand[/b]  [b]/collapse[/b]  [b]/quit[/b][/dim]",
            shrink=False,
        )
        self.log_widget.write(
            "[dim]Keys: [b]Ctrl+C[/b]=interrupt  [b]Q[/b]=quit  [b]C[/b]=clear  [b]E[/b]=expand  [b]A[/b]=collapse[/dim]",
            shrink=False,
        )
        self.log_widget.write("", shrink=False)

    # ── WebSocket loop ──────────────────────────────────────────────

    async def _ws_loop(self) -> None:
        api_key = settings.client.api_key
        ws_url = f"ws://127.0.0.1:{settings.server.api_port}/sessions/{self.session_id}/ws"
        if api_key:
            ws_url += f"?api_key={api_key}"
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                self._ws = ws
                self.log_widget.write("[green]● Connected to server[/green]", shrink=False)
                self.status_widget.set_text("Ready")

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
            self.log_widget.write(f"[red][b]✗ Cannot connect to server at port {settings.server.api_port}[/b][/red]", shrink=False)
            self.status_widget.set_text("Disconnected")
        except websockets.exceptions.ConnectionClosedOK:
            self.log_widget.write("[dim]Session closed.[/dim]", shrink=False)
            self.status_widget.set_text("Disconnected")
        except websockets.exceptions.ConnectionClosedError as e:
            self.log_widget.write(f"[red]Connection lost: {e}[/red]", shrink=False)
            self.status_widget.set_text("Disconnected")
        except Exception as e:
            self.log_widget.write(f"[red]Error: {e}[/red]", shrink=False)
            self.status_widget.set_text("Error")
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
                self.log_widget.write(
                    f"[dim italic]  ⟶ {_escape(content)}[/dim italic]",
                    shrink=False,
                )

        elif etype == "tool_call":
            tool = event.get("tool", "?")
            args = event.get("args", {})
            self._last_tool_name = tool  # store for per-tool result formatting
            if isinstance(args, dict):
                args_str = ", ".join(
                    f"[yellow]{k}[/yellow]=[white]{truncate(format_arg_value(v), 60)}[/white]"
                    for k, v in args.items()
                )
            else:
                args_str = truncate(format_arg_value(args), 80)
            self.log_widget.write(
                f"[dim]⚙[/dim] [b orange]{tool}[/b orange]({args_str})",
                shrink=False,
            )
            # Auto-approve check: if auto-approve is on, send approval immediately
            if self._auto_approve and tool != "tool_search":
                call_id = event.get("call_id", "")
                self._auto_approve_task = asyncio.create_task(self._send_approval(call_id, True))
            self.status_widget.set_text(f"Running: {tool}", spinning=True)

        elif etype == "tool_result":
            output = event.get("output", "")
            success = event.get("success", True)
            call_id = event.get("call_id", "")
            self._write_tool_result(success, output, call_id)
            self.status_widget.set_text("Processing response...", spinning=True)

        elif etype == "tool_error":
            """Server-emitted event when a tool fails."""
            tool = event.get("tool", "?")
            error = event.get("error", "Unknown error")
            self.log_widget.write(
                f"[red]✗ {tool} failed: {_escape(error)}[/red]",
                shrink=False,
            )
            self.status_widget.set_text(f"Error in {tool}")

        elif etype == "approval_request":
            tool = event.get("tool", "?")
            args = event.get("args", {})
            call_id = event.get("call_id", "")
            self.status_widget.set_text("Awaiting approval...", spinning=False)
            approved = await self.push_screen_wait(ApprovalModal(tool, args, call_id))
            await self._send_approval(call_id, approved)
            self.status_widget.set_text("Ready")

        elif etype == "response_chunk":
            # Streaming token — append to the current response in-place
            content = event.get("content", "")
            self._write_response_chunk(content)

        elif etype == "response":
            # Final response event — if streaming was active, the last chunk
            # already updated the display. This event confirms completion.
            content = event.get("content", "")
            self._finalize_response(content)
            self._busy = False
            self._request_count += 1
            # Track token usage if provided by server
            tokens = event.get("tokens_used", 0)
            if tokens:
                self._total_tokens_used += tokens
            self._process_next_in_queue()
            self.status_widget.set_text("Ready")

        elif etype == "error":
            message = event.get("message", "Unknown error")
            self.log_widget.write(f"[red][b]✗ Error:[/b] {_escape(message)}[/red]", shrink=False)
            self._busy = False
            self._process_next_in_queue()
            self.status_widget.set_text("Error")

        elif etype == "session_closed":
            self.log_widget.write("[dim]Session closed by server.[/dim]", shrink=False)
            self._busy = False
            self._ws = None
            self.status_widget.set_text("Disconnected")

    # ── Display helpers ──────────────────────────────────────────────

    def _write_tool_result(self, success: bool, output: str, call_id: str):
        """Write a tool result — short results inline, long results collapsible."""
        tool_name = getattr(self, "_last_tool_name", "")
        max_chars = settings.agent.max_tool_output_chars

        display = format_tool_result_for_display(tool_name, success, output, max_chars)

        if len(display) <= max_chars:
            icon = "✓" if success else "✗"
            color = "green" if success else "red"
            self.log_widget.write(
                f"   [{color}]{icon}[/{color}] {display}",
                shrink=False,
            )
        else:
            truncated = truncate_output(display, max_chars)
            icon = "✓" if success else "✗"
            color = "green" if success else "red"
            collapsible = Collapsible(
                Static(truncated),
                title=f"[{color}]{icon}[/{color}] Tool result ({len(output):,} chars)",
                collapsed=True,
            )
            self._collapsibles.append(collapsible)
            self.log_widget.mount(collapsible)
            self.log_widget.scroll_end(animate=False)

    def _write_response(self, content: str):
        """Write the final agent response with markdown formatting."""
        ts = datetime.now().strftime("%H:%M")
        formatted = render_markdown(content, code_blocks=True)
        self.log_widget.write("", shrink=False)
        self.log_widget.write(
            f"[b green][{ts}] Agent:[/b green] {formatted}",
            shrink=False,
        )
        self.log_widget.write("", shrink=False)

    # ── Slash commands ───────────────────────────────────────────────

    async def _handle_slash_command(self, cmd: str) -> bool:
        """Handle slash commands. Returns True if handled."""
        parts = cmd.strip().lower().split()
        command = parts[0] if parts else ""
        parts[1:] if len(parts) > 1 else []

        if command == "/help" or command == "/h":
            self._show_help()
            return True

        elif command == "/new" or command == "/n":
            self._show_greeting()
            self.log_widget.write(
                "[yellow]⟶ New conversation started. Previous context cleared.[/yellow]",
                shrink=False,
            )
            self.log_widget.clear()
            self._collapsibles.clear()
            self._show_greeting()
            return True

        elif command == "/clear":
            self.log_widget.clear()
            self._collapsibles.clear()
            self._streaming_response = ""
            self._streaming_widget.update("")
            self._show_greeting()
            return True

        elif command == "/expand" or command == "/e":
            for c in self._collapsibles:
                c.collapsed = False
            return True

        elif command == "/collapse" or command == "/a":
            for c in self._collapsibles:
                c.collapsed = True
            return True

        elif command == "/quit" or command == "/q":
            self.action_quit()
            return True

        elif command == "/sessions":
            self.log_widget.write(
                "[dim]Session management coming soon. Current session: "
                f"{self.session_id}[/dim]",
                shrink=False,
            )
            return True

        elif command == "/status":
            status = "busy" if self._busy else "ready"
            auto = "ON" if self._auto_approve else "OFF"
            self.log_widget.write(
                f"[dim]Status: {status} | Session: {self.session_id} | "
                f"Queued: {len(self._pending_inputs)} | "
                f"Auto-approve: {auto} | "
                f"Tokens: {self._total_tokens_used:,} | "
                f"Requests: {self._request_count}[/dim]",
                shrink=False,
            )
            return True

        elif command == "/interrupt":
            self.action_interrupt()
            return True

        elif command == "/compact":
            self.log_widget.write(
                "[yellow]⟶ Context compaction requested.[/yellow]",
                shrink=False,
            )
            if self._ws and self._ws.open:
                await self._ws.send(json.dumps({"type": "compact"}))
                self.status_widget.set_text("Compacting...", spinning=True)
            else:
                self.log_widget.write(
                    "[red]Cannot compact — not connected to server.[/red]",
                    shrink=False,
                )
            return True

        elif command == "/copy":
            self.log_widget.write(
                "[dim]Copy is not available in the TUI. Use your terminal's "
                "selection mechanism.[/dim]",
                shrink=False,
            )
            return True

        elif command == "/version":
            model = settings.agent.default_model
            self.log_widget.write(
                f"[dim]NexusAgent v0.1.0 | Model: {model} | "
                f"Session: {self.session_id} | "
                f"Theme: {NEXUS_THEMES[self._theme_index]['name']}[/dim]",
                shrink=False,
            )
            return True

        elif command == "/auto":
            self.action_toggle_auto_approve()
            return True

        elif command == "/tokens":
            model = settings.agent.default_model
            self.log_widget.write("[b cyan]Token Usage[/b cyan]", shrink=False)
            self.log_widget.write(
                f"  Total tokens used: [yellow]{self._total_tokens_used:,}[/yellow]",
                shrink=False,
            )
            self.log_widget.write(
                f"  Requests made: [yellow]{self._request_count}[/yellow]",
                shrink=False,
            )
            self.log_widget.write(
                f"  Model: [yellow]{model}[/yellow]",
                shrink=False,
            )
            self.log_widget.write(
                f"  Session: [yellow]{self.session_id}[/yellow]",
                shrink=False,
            )
            if self._request_count > 0 and self._total_tokens_used > 0:
                avg = self._total_tokens_used // self._request_count
                self.log_widget.write(
                    f"  Avg tokens/request: [yellow]{avg:,}[/yellow]",
                    shrink=False,
                )
            return True

        elif command == "/model":
            model = settings.agent.default_model
            provider = settings.agent.primary_provider
            self.log_widget.write("[b cyan]Model Info[/b cyan]", shrink=False)
            self.log_widget.write(f"  Model: [yellow]{model}[/yellow]", shrink=False)
            self.log_widget.write(
                f"  Provider: [yellow]{provider}[/yellow]", shrink=False
            )
            self.log_widget.write(
                f"  Session: [yellow]{self.session_id}[/yellow]", shrink=False
            )
            return True

        elif command == "/threads":
            self.log_widget.write(
                "[dim]Recent sessions (via server):[/dim]",
                shrink=False,
            )
            if self._ws and self._ws.open:
                await self._ws.send(json.dumps({"type": "list_sessions"}))
            else:
                self.log_widget.write(
                    f"[dim]  Current session: {self.session_id}[/dim]",
                    shrink=False,
                )
            return True

        elif command == "/theme":
            self._theme_index = (self._theme_index + 1) % len(NEXUS_THEMES)
            theme = NEXUS_THEMES[self._theme_index]
            self._apply_theme(theme)
            self.log_widget.write(
                f"[yellow]⟶ Theme switched to: {theme['name']}[/yellow]",
                shrink=False,
            )
            return True

        elif command == "/undo":
            if self._ws and self._ws.open:
                await self._ws.send(json.dumps({"type": "undo"}))
                self.log_widget.write(
                    "[yellow]⟶ Undo requested.[/yellow]",
                    shrink=False,
                )
            else:
                self.log_widget.write("[dim]Not connected — cannot undo.[/dim]", shrink=False)
            return True

        elif command == "/redo":
            if self._ws and self._ws.open:
                await self._ws.send(json.dumps({"type": "redo"}))
                self.log_widget.write(
                    "[yellow]⟶ Redo requested.[/yellow]",
                    shrink=False,
                )
            else:
                self.log_widget.write("[dim]Not connected — cannot redo.[/dim]", shrink=False)
            return True

        elif command == "/skills":
            from nexusagent.skills import load_all_skills, get_skills_summary

            skills = load_all_skills()
            if skills:
                get_skills_summary(skills)
                self.log_widget.write("[b cyan]Available Skills[/b cyan]", shrink=False)
                for name, skill in sorted(skills.items()):
                    desc = skill.description or "No description"
                    self.log_widget.write(f"  [yellow]{name}[/white]: {desc}", shrink=False)
            else:
                self.log_widget.write("[dim]No skills found in ~/.hermes/skills/[/dim]", shrink=False)
            return True

        elif command == "/skill":
            skill_name = parts[1] if len(parts) > 1 else ""
            if not skill_name:
                self.log_widget.write("[yellow]Usage: /skill <name>[/yellow]", shrink=False)
                return True
            from nexusagent.skills import load_all_skills, get_skill_content

            skills = load_all_skills()
            content = get_skill_content(skills, skill_name)
            if content:
                self.log_widget.write(f"[b cyan]Skill: {skill_name}[/b cyan]", shrink=False)
                for line in content.split("\n")[:20]:
                    self.log_widget.write(f"  {line}", shrink=False)
                if len(content.split("\n")) > 20:
                    self.log_widget.write(f"  [dim]... ({len(content.split(chr(10)))} lines total)[/dim]", shrink=False)
            else:
                self.log_widget.write(f"[red]Skill '{skill_name}' not found.[/red]", shrink=False)
            return True

        else:
            self.log_widget.write(
                f"[red]Unknown command: {command}. Type /help for available commands.[/red]",
                shrink=False,
            )
            return True

    def _apply_theme(self, theme: dict) -> None:
        """Apply a color theme by updating CSS."""
        self.styles.background = theme["bg"]
        self.query_one(Header).styles.background = theme["header_bg"]
        self.query_one(Header).styles.color = theme["accent"]

    def _show_help(self):
        self.log_widget.write("", shrink=False)
        self.log_widget.write("[b cyan]Available Commands:[/b cyan]", shrink=False)
        self.log_widget.write("  [b]/help[/b]      Show this help message", shrink=False)
        self.log_widget.write("  [b]/new[/b]       Start a new conversation", shrink=False)
        self.log_widget.write("  [b]/clear[/b]     Clear the conversation log + greeting", shrink=False)
        self.log_widget.write("  [b]/expand[/b]    Expand all tool results", shrink=False)
        self.log_widget.write("  [b]/collapse[/b]  Collapse all tool results", shrink=False)
        self.log_widget.write("  [b]/status[/b]    Show session status", shrink=False)
        self.log_widget.write("  [b]/compact[/b]   Trigger context compaction", shrink=False)
        self.log_widget.write("  [b]/copy[/b]      Copy placeholder", shrink=False)
        self.log_widget.write("  [b]/version[/b]   Show version info", shrink=False)
        self.log_widget.write("  [b]/tokens[/b]    Show token usage", shrink=False)
        self.log_widget.write("  [b]/model[/b]     Show current model info", shrink=False)
        self.log_widget.write("  [b]/threads[/b]   List recent sessions", shrink=False)
        self.log_widget.write("  [b]/theme[/b]     Cycle color theme", shrink=False)
        self.log_widget.write("  [b]/interrupt[/b] Cancel current agent turn", shrink=False)
        self.log_widget.write("  [b]/quit[/b]      Exit the application", shrink=False)
        self.log_widget.write("", shrink=False)
        self.log_widget.write("[b cyan]Keyboard Shortcuts:[/b cyan]", shrink=False)
        self.log_widget.write("  [b]Ctrl+C[/b]  Interrupt current turn", shrink=False)
        self.log_widget.write("  [b]Ctrl+U[/b]  Interrupt current turn", shrink=False)
        self.log_widget.write("  [b]Q[/b]       Quit", shrink=False)
        self.log_widget.write("  [b]C[/b]       Clear log", shrink=False)
        self.log_widget.write("  [b]E[/b]       Expand all", shrink=False)
        self.log_widget.write("  [b]A[/b]       Collapse all", shrink=False)
        self.log_widget.write("  [b]Ctrl+_[/b]  Toggle auto-approve", shrink=False)
        self.log_widget.write("", shrink=False)

    # ── Streaming response ───────────────────────────────────────────

    def _write_response_chunk(self, content: str) -> None:
        """Append a streaming token to the in-progress response."""
        self._streaming_response += content
        self._streaming_widget.update(
            f"[b green]Agent:[/b green] {self._streaming_response}"
        )

    def _finalize_response(self, content: str) -> None:
        """Finalize the streaming response."""
        if self._streaming_response:
            final = content if content else self._streaming_response
            ts = datetime.now().strftime("%H:%M")
            formatted = render_markdown(final, code_blocks=True)
            self.log_widget.write("", shrink=False)
            self.log_widget.write(
                f"[b green][{ts}] Agent:[/b green]",
                shrink=False,
            )
            self.log_widget.write(formatted, shrink=False)
            self.log_widget.write("", shrink=False)
        elif content:
            self._write_response(content)

        # Clear the streaming widget
        self._streaming_widget.update("")
        self._streaming_response = ""

    # ── Queue management ────────────────────────────────────────────

    def _process_next_in_queue(self):
        if not self._pending_inputs:
            return
        next_msg = self._pending_inputs.pop(0)
        self._busy = True
        self.log_widget.write(f"[b cyan]You:[/b cyan] {next_msg}", shrink=False)
        self.status_widget.set_text("Thinking...", spinning=True)
        asyncio.create_task(self._input_queue.put(next_msg))  # noqa: RUF006
        self._update_queue_status()

    def _update_queue_status(self):
        count = len(self._pending_inputs)
        if count > 0:
            self.queue_status.update(f"⏳ {count} message{'s' if count > 1 else ''} queued")
        else:
            self.queue_status.update("")

    async def _send_approval(self, call_id: str, approved: bool):
        if self._ws and self._ws.open:
            await self._ws.send(json.dumps({
                "type": "approval",
                "call_id": call_id,
                "approved": approved,
            }))
        else:
            self.log_widget.write("[red]Failed to send approval (disconnected)[/red]", shrink=False)

    # ── Input handling ──────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        # Accept input from any Input widget (the chat input has id="input-area")
        message = event.value.strip()
        if not message:
            return

        # Slash commands
        if message.startswith("/"):
            event.input.value = ""
            await self._handle_slash_command(message)
            return

        if self._busy:
            self._pending_inputs.append(message)
            self.log_widget.write(f"[dim]⏳ Queued:[/dim] {message}", shrink=False)
            self._update_queue_status()
            event.input.value = ""
            return

        self._busy = True
        self.log_widget.write(f"[b cyan]You:[/b cyan] {message}", shrink=False)
        event.input.value = ""
        self.status_widget.set_text("Thinking...", spinning=True)
        await self._input_queue.put(message)

    # ── Actions ─────────────────────────────────────────────────────

    def action_clear(self) -> None:
        self.log_widget.clear()
        self._collapsibles.clear()
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
            self.status_widget.set_text("Interrupting...", spinning=True)
            self.log_widget.write("[yellow]⏹ Interrupt sent — waiting for agent to stop...[/yellow]", shrink=False)

    def action_expand_all(self) -> None:
        for c in self._collapsibles:
            c.collapsed = False

    def action_collapse_all(self) -> None:
        for c in self._collapsibles:
            c.collapsed = True

    def action_toggle_auto_approve(self) -> None:
        self._auto_approve = not self._auto_approve
        if self._auto_approve:
            self._auto_approve_badge.update("[bold yellow]⚡ AUTO-APPROVE ON[/bold yellow]")
            self.log_widget.write(
                "[yellow]⟶ Auto-approve enabled — tool calls will be approved automatically.[/yellow]",
                shrink=False,
            )
        else:
            self._auto_approve_badge.update("")
            self.log_widget.write(
                "[dim]⟶ Auto-approve disabled — tool calls require manual approval.[/dim]",
                shrink=False,
            )


def main(yolo: bool = False) -> None:
    app = NexusApp(yolo=yolo)
    app.run()


if __name__ == "__main__":
    main()
