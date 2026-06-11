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
import contextlib
import json
import re
import textwrap
import uuid
from datetime import datetime
from typing import ClassVar

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

from nexusagent.config import settings

# Color themes for /theme cycling
NEXUS_THEMES = [
    {"name": "midnight", "header_bg": "#1f2937", "accent": "#10b981", "bg": "#111827"},
    {"name": "ocean", "header_bg": "#0e4d6e", "accent": "#38bdf8", "bg": "#0c1929"},
    {"name": "forest", "header_bg": "#14532d", "accent": "#4ade80", "bg": "#052e16"},
    {"name": "sunset", "header_bg": "#7c2d12", "accent": "#fb923c", "bg": "#1c1010"},
    {"name": "lavender", "header_bg": "#3b3864", "accent": "#a78bfa", "bg": "#1a1830"},
]


# ═══════════════════════════════════════════════════════════════════════════
# SpinnerLabel — animated spinner + text
# ═══════════════════════════════════════════════════════════════════════════

class SpinnerLabel(Horizontal):
    """Label with an animated spinner prefix."""
    spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    tick = reactive(0)

    def __init__(self, text: str = "Ready", **kwargs):
        super().__init__(**kwargs)
        self._text = text
        self._timer: Timer | None = None
        self._spinning = False

    def compose(self) -> ComposeResult:
        yield Static("", id="spinner-icon")
        yield Static("", id="spinner-text")

    def on_mount(self) -> None:
        self.update_display()

    def set_text(self, text: str, spinning: bool = False):
        self._text = text
        if spinning and not self._spinning:
            self._spinning = True
            self._timer = self.set_interval(0.1, self._tick_spinner)
        elif not spinning and self._spinning:
            self._spinning = False
            if self._timer:
                self._timer.stop()
                self._timer = None
        self.update_display()

    def _tick_spinner(self):
        self.tick += 1

    def watch_tick(self):
        self.update_display()

    def update_display(self):
        try:
            spinner = ""
            if self._spinning:
                spinner = self.spinner_chars[int(self.tick) % len(self.spinner_chars)]
            self.query_one("#spinner-icon", Static).update(spinner)
            self.query_one("#spinner-text", Static).update(self._text)
        except Exception:
            pass

    def on_unmount(self):
        if self._timer:
            self._timer.stop()


# ═══════════════════════════════════════════════════════════════════════════
# ApprovalModal — tool call approval dialog
# ═══════════════════════════════════════════════════════════════════════════

class ApprovalModal(ModalScreen[bool]):
    def __init__(self, tool_name: str, tool_args: dict, call_id: str = "") -> None:
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.call_id = call_id

    def compose(self) -> ComposeResult:
        with Vertical(id="approval-dialog"):
            yield Static(f"⚡ Approval Required: {self.tool_name}", id="approval-title")
            with ScrollableContainer(id="approval-scroll"):
                args_str = "\n".join(f"  {k}: {v}" for k, v in self.tool_args.items())
                yield Static(args_str, id="approval-args")
            with Horizontal(id="approval-buttons"):
                yield Button("✓ Approve", id="approve", variant="success")
                yield Button("✗ Reject", id="reject", variant="error")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve":
            self.dismiss(True)
        else:
            self.dismiss(False)


# ═══════════════════════════════════════════════════════════════════════════
# ErrorModal — error display dialog
# ═══════════════════════════════════════════════════════════════════════════

class ErrorModal(ModalScreen[None]):
    """Modal dialog for displaying errors."""

    def __init__(self, error_message: str) -> None:
        super().__init__()
        self.error_message = error_message

    def compose(self) -> ComposeResult:
        with Vertical(id="approval-dialog"):
            yield Static("⚠ Error", id="approval-title")
            yield Static(self.error_message, id="approval-args")
            with Horizontal(id="approval-buttons"):
                yield Button("OK", id="ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


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
        max-width: 100%;
        height: 1fr;
        border: solid #1f2937;
        margin: 0 1;
        overflow-x: hidden;
    }

    #greeting {
        width: 100%;
        max-width: 100%;
        height: auto;
        background: #111827;
        padding: 0 2;
        overflow-x: hidden;
        text-wrap: wrap;
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
        text-align: left;
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
        yield Static("", id="greeting")
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

    def on_mount(self) -> None:
        self.session_id = str(uuid.uuid4())[:8]
        self.log_widget = self.query_one("#conversation-log", RichLog)
        self._greeting_widget = self.query_one("#greeting", Static)
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
        self._auto_approve = False
        self._auto_approve_task: asyncio.Task | None = None
        self._interrupt_task: asyncio.Task | None = None
        self._theme_index = 0
        self._total_tokens_used = 0
        self._request_count = 0
        self._auto_approve_badge = self.query_one("#auto-approve-badge", Static)
        self._auto_approve_badge.update("")

        self._show_greeting()
        self._ws_task = asyncio.create_task(self._ws_loop())

    # ── Greeting ──────────────────────────────────────────────────────

    def _show_greeting(self):
        ts = datetime.now().strftime("%H:%M")
        greeting_text = (
            "[b cyan]╔══════════════════════════════════════════╗[/b cyan]\n"
            "[b cyan]║[/b cyan]  [b white]NexusAgent[/b white] — Interactive AI Agent    [b cyan]║[/b cyan]\n"
            f"[b cyan]║[/b cyan]  Session: [yellow]{self.session_id}[/yellow]  {ts}              [b cyan]║[/b cyan]\n"
            "[b cyan]╚══════════════════════════════════════════╝[/b cyan]\n"
            "\n"
            "[dim]Commands: [b]/help[/b]  [b]/new[/b]  [b]/clear[/b]  [b]/expand[/b]  [b]/collapse[/b]  [b]/quit[/b][/dim]\n"
            "[dim]Keys: [b]Ctrl+C[/b]=interrupt  [b]Q[/b]=quit  [b]C[/b]=clear  [b]E[/b]=expand  [b]A[/b]=collapse[/dim]"
        )
        self._greeting_widget.update(greeting_text)

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
                    f"[dim italic]  ⟶ {self._escape(content)}[/dim italic]",
                    shrink=False,
                )

        elif etype == "tool_call":
            tool = event.get("tool", "?")
            args = event.get("args", {})
            self._last_tool_name = tool  # store for per-tool result formatting
            if isinstance(args, dict):
                args_str = ", ".join(
                    f"[yellow]{k}[/yellow]=[white]{self._truncate(self._format_arg_value(v), 60)}[/white]"
                    for k, v in args.items()
                )
            else:
                args_str = self._truncate(self._format_arg_value(args), 80)
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
                f"[red]✗ {tool} failed: {self._escape(error)}[/red]",
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
            self.log_widget.write(f"[red][b]✗ Error:[/b] {self._escape(message)}[/red]", shrink=False)
            self._busy = False
            self._process_next_in_queue()
            self.status_widget.set_text("Error")

        elif etype == "compact_result":
            status = event.get("status", "?")
            if status == "ok":
                summary = event.get("summary", "")
                self.log_widget.write(
                    f"[green]✓ Context compacted.[/green]"
                    + (f" [dim]{summary}[/dim]" if summary else ""),
                    shrink=False,
                )
            else:
                err = event.get("error", "Unknown error")
                self.log_widget.write(
                    f"[red]Compaction failed: {err}[/red]",
                    shrink=False,
                )
            self.status_widget.set_text("Ready")

        elif etype == "session_closed":
            self.log_widget.write("[dim]Session closed by server.[/dim]", shrink=False)
            self._busy = False
            self._ws = None
            self.status_widget.set_text("Disconnected")

        elif etype == "session_list":
            sessions = event.get("sessions", [])
            error = event.get("error")
            if error:
                self.log_widget.write(
                    f"[red]Failed to list sessions: {error}[/red]",
                    shrink=False,
                )
            elif sessions:
                self.log_widget.write(
                    "[b cyan]Recent Sessions:[/b cyan]",
                    shrink=False,
                )
                for s in sessions:
                    sid = s.get("id", "?")
                    status = s.get("status", "?")
                    wdir = s.get("working_dir", ".")
                    updated = s.get("updated_at", "unknown")
                    if isinstance(updated, str) and len(updated) > 19:
                        updated = updated[:19]
                    self.log_widget.write(
                        f"  [yellow]{sid}[/yellow]  "
                        f"status=[dim]{status}[/dim]  "
                        f"dir=[dim]{wdir}[/dim]  "
                        f"updated=[dim]{updated}[/dim]",
                        shrink=False,
                    )
            else:
                self.log_widget.write(
                    "[dim]No sessions found.[/dim]",
                    shrink=False,
                )

    # ── Display helpers ──────────────────────────────────────────────

    def _write_tool_result(self, success: bool, output: str, call_id: str):
        """Write a tool result — short results inline, long results collapsible.

        Uses per-tool formatters via dispatch table for specialized output.
        """
        # Determine tool name from context (last tool_call event)
        tool_name = getattr(self, "_last_tool_name", "")

        # Use per-tool formatter if available
        display = self._format_tool_result_for_display(tool_name, success, output)
        max_chars = settings.agent.max_tool_output_chars

        if len(display) <= max_chars:
            icon = "✓" if success else "✗"
            color = "green" if success else "red"
            self.log_widget.write(
                f"   [{color}]{icon}[/{color}] {display}",
                shrink=False,
            )
        else:
            truncated = self._truncate_output(display)
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

    def _format_tool_result_for_display(self, tool_name: str, success: bool, output: str) -> str:
        """Dispatch table for per-tool output formatting."""
        if not output or not output.strip():
            return "[dim](empty)[/dim]"

        # Shell tools: show command + exit code + truncated output
        if tool_name in ("run_shell", "run_shell_streaming", "shell"):
            return self._format_shell_output(output)
        # File read: show path + line count + content preview
        elif tool_name in ("read_file", "read_multiple_files"):
            return self._format_read_file_output(output)
        # File write/edit: show path + success
        elif tool_name in ("write_file", "write_multiple_files", "edit_file", "apply_patch"):
            return self._format_write_file_output(output, tool_name)
        # Git tools: show command + result summary
        elif tool_name.startswith("git_"):
            return self._format_git_output(output, tool_name)
        # Search web: show query + result count + top URLs
        elif tool_name in ("search_web", "search_local_docs"):
            return self._format_search_output(output)
        # Subagent: show task + status
        elif tool_name == "spawn_subagent":
            return self._format_subagent_output(output)
        # Default: use existing generic JSON/smart formatter
        else:
            return self._format_tool_output(output)

    def _format_shell_output(self, output: str) -> str:
        """Format shell command output: show exit code + truncated stdout."""
        lines = output.strip().split("\n")
        # Try to find exit code indicator
        exit_code = None
        clean_lines = []
        for line in lines:
            if line.startswith("Exit code:") or line.startswith("exit code:"):
                with contextlib.suppress(ValueError):
                    exit_code = int(line.split(":")[-1].strip())
            elif not line.startswith("Error:"):
                clean_lines.append(line)

        result = "\n".join(clean_lines[:15])
        suffix = ""
        if len(clean_lines) > 15:
            suffix = f"\n[dim]... +{len(clean_lines) - 15} more lines[/dim]"

        code_str = ""
        if exit_code is not None:
            code_color = "green" if exit_code == 0 else "red"
            code_str = f"[{code_color}]exit {exit_code}[/{code_color}] "

        return f"{code_str}{result}{suffix}"

    def _format_read_file_output(self, output: str) -> str:
        """Format read_file output: show file path + line count + content preview."""
        lines = output.strip().split("\n")
        # Count content lines (skip line-number prefixed ones like "1|content")
        content_lines = [line for line in lines if not re.match(r'^\d+\|', line)]
        line_count = len(content_lines)

        preview_lines = content_lines[:12]
        preview = "\n".join(preview_lines)
        suffix = ""
        if line_count > 12:
            suffix = f"\n[dim]... +{line_count - 12} more lines[/dim]"

        return f"[b cyan]({line_count} lines)[/b cyan] {preview}{suffix}"

    def _format_write_file_output(self, output: str, tool_name: str) -> str:
        """Format write_file/edit_file output: show success indicator."""
        cleaned = output.strip()
        # Try to extract file path from output
        path_match = re.search(r'(?:written|saved|patched)\s+(?:to\s+)?["\']?([\w./~_-]+)["\']?', cleaned, re.IGNORECASE)
        path = path_match.group(0) if path_match else cleaned[:80]
        return f"[green]✓ {tool_name}[/green] → {path}"

    def _format_git_output(self, output: str, tool_name: str) -> str:
        """Format git tool output: show git command + result summary."""
        lines = output.strip().split("\n")
        # Show first 10 meaningful lines
        meaningful = [line for line in lines if line.strip()][:10]
        result = "\n".join(meaningful)
        suffix = ""
        if len(lines) > 10:
            suffix = f"\n[dim]... +{len(lines) - 10} more lines[/dim]"
        return f"[b orange]git {tool_name[4:]}[/b orange] {result}{suffix}"

    def _format_search_output(self, output: str) -> str:
        """Format search_web output: show result count + top URLs."""
        # Count Title: occurrences as proxy for result count
        result_count = output.count("Title:")
        urls = re.findall(r'URL:\s*(\S+)', output)
        url_preview = "\n".join(f"  🔗 {u}" for u in urls[:3])
        suffix = ""
        if len(urls) > 3:
            suffix = f"\n[dim]  ... +{len(urls) - 3} more URLs[/dim]"
        return f"[b cyan]({result_count} results)[/b cyan]\n{url_preview}{suffix}"

    def _format_subagent_output(self, output: str) -> str:
        """Format spawn_subagent output: show task + status."""
        cleaned = output.strip()
        # Extract worker ID and status
        id_match = re.search(r'worker\s+(\S+)', cleaned)
        status_match = re.search(r'status:\s*(\w+)', cleaned)
        worker_id = id_match.group(1) if id_match else "?"
        status = status_match.group(1) if status_match else "?"
        return f"[b purple]subagent {worker_id}[/b purple] status: [yellow]{status}[/yellow]"

    def _format_tool_output(self, output: str) -> str:
        """Format tool output for display — parse JSON into human-readable form."""
        if not output or not output.strip():
            return "[dim](empty)[/dim]"

        # Try to parse as JSON
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                # Common tool output patterns — extract meaningful content
                for key in ("content", "result", "output", "stdout", "text", "message", "data"):
                    if data.get(key):
                        val = data[key]
                        if isinstance(val, str):
                            return self._escape(val.strip())
                        return self._escape(json.dumps(val, indent=2, default=str))
                # Show key-value summary for dicts
                preview = {}
                for k, v in list(data.items())[:6]:
                    v_str = str(v)
                    if len(v_str) > 120:
                        v_str = v_str[:117] + "..."
                    preview[k] = v_str
                lines = [f"[b]{k}[/b]: {v}" for k, v in preview.items()]
                if len(data) > 6:
                    lines.append(f"[dim]... +{len(data) - 6} more keys[/dim]")
                return "\n".join(lines)
            if isinstance(data, list):
                if len(data) == 0:
                    return "[dim](empty list)[/dim]"
                if len(data) <= 5:
                    items = []
                    for item in data:
                        s = str(item)
                        if len(s) > 200:
                            s = s[:197] + "..."
                        items.append(f"  • {s}")
                    return "\n".join(items)
                # Large list: show first 5 + count
                items = []
                for item in data[:5]:
                    s = str(item)
                    if len(s) > 200:
                        s = s[:197] + "..."
                    items.append(f"  • {s}")
                items.append(f"[dim]  ... +{len(data) - 5} more items[/dim]")
                return "\n".join(items)
            # Primitive JSON value
            return self._escape(str(data))
        except (json.JSONDecodeError, TypeError):
            pass

        # Not JSON — show as-is, cleaned up
        cleaned = output.strip()
        # Collapse excessive blank lines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return self._escape(cleaned)

    def _write_response(self, content: str):
        """Write the final agent response with markdown formatting."""
        ts = datetime.now().strftime("%H:%M")
        formatted = self._simple_markdown(content)
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

        else:
            self.log_widget.write(
                f"[red]Unknown command: {command}. Type /help for available commands.[/red]",
                shrink=False,
            )
            return True

    def _apply_theme(self, theme: dict) -> None:
        """Apply a color theme by updating CSS."""
        self.styles.background = theme["bg"]
        # Update header styles
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
        """Write a streaming token directly to the conversation log.

        Each chunk is appended to the RichLog as it arrives, giving the user
        true token-by-token streaming output instead of waiting for completion.
        """
        self.log_widget.write(content, shrink=False)

    def _finalize_response(self, content: str) -> None:
        """Finalize the streaming response.

        Since chunks are written directly to the log widget in real time,
        this method only needs to clear the streaming widget and separator.
        """
        # Clear the streaming widget
        self._streaming_widget.update("")
        self._streaming_response = ""

    def _enhanced_markdown(self, text: str) -> str:
        """Enhanced markdown: syntax highlighting for code blocks, bold, italic, inline code."""
        # Extract code blocks first, replace with placeholders
        code_blocks = []
        def replace_code_block(m):
            lang = m.group(1) or ""
            code = m.group(2)
            idx = len(code_blocks)
            code_blocks.append((lang, code))
            return f"__CODE_BLOCK_{idx}__"

        # Handle fenced code blocks  ```lang\n...\n```
        text = re.sub(r'```(\w*)\n(.*?)```', replace_code_block, text, flags=re.DOTALL)

        # Handle inline code `...`
        text = re.sub(r'`([^`]+)`', r'[reverse]\1[/reverse]', text)

        # Bold and italic
        text = re.sub(r'\*\*(.+?)\*\*', r'[b]\1[/b]', text)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'[i]\1[/i]', text)

        # Restore code blocks with dim/styled formatting
        for i, (lang, code) in enumerate(code_blocks):
            lang_label = f"[dim]({lang})[/dim] " if lang else ""
            # Truncate very long code blocks
            code_lines = code.split("\n")
            if len(code_lines) > 20:
                code = "\n".join(code_lines[:20]) + f"\n[dim]... +{len(code_lines) - 20} more lines[/dim]"
            styled = f"{lang_label}[dim]{code}[/dim]"
            text = text.replace(f"__CODE_BLOCK_{i}__", styled)

        return text

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

    # ── Helpers ─────────────────────────────────────────────────────

    def _truncate_output(self, output: str) -> str:
        max_chars = settings.agent.max_tool_output_chars
        if len(output) <= max_chars:
            return output
        head = output[:max_chars // 2]
        tail = output[-(max_chars // 2):]
        return f"{head}\n[dim]... ({len(output):,} chars total) ...[/dim]\n{tail}"

    def _truncate(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."

    def _format_arg_value(self, value) -> str:
        """Format a tool argument value for display — dicts as JSON, strings escaped."""
        if isinstance(value, dict):
            return self._escape(json.dumps(value, ensure_ascii=False))
        if isinstance(value, list):
            return self._escape(json.dumps(value, ensure_ascii=False))
        if isinstance(value, str) and len(value) > 200:
            return self._escape(textwrap.shorten(value, width=200, placeholder="..."))
        return self._escape(str(value))

    def _escape(self, text: str) -> str:
        return text.replace("[", "\\[").replace("]", "\\]")

    def _simple_markdown(self, text: str) -> str:
        text = re.sub(r'\*\*(.+?)\*\*', r'[b]\1[/b]', text)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'[i]\1[/i]', text)
        text = re.sub(r'`(.+?)`', r'[reverse]\1[/reverse]', text)
        text = re.sub(r'```\w*\n?', '', text)
        text = re.sub(r'```', '', text)
        return text


def main() -> None:
    app = NexusApp()
    app.run()


if __name__ == "__main__":
    main()
