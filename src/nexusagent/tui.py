"""Terminal UI for NexusAgent — real-time streaming chat interface.

Features:
- Word-wrapped conversation log (no horizontal scroll)
- Real-time tool call/result streaming with collapsible output
- Greeting screen with help on login
- Slash commands: /new, /sessions, /help, /clear, /expand, /collapse, /quit
- Markdown rendering for agent responses
- Status bar with spinner, state, and queued message count
- Interrupt support (Ctrl+C) — cancels running agent turn
- Error display when tools fail (web search, subagent, etc.)
- Auto-scroll with manual override
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import ClassVar

import websockets
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    RichLog,
    Static,
    Collapsible,
    Label,
)
from textual.timer import Timer
from textual.reactive import reactive
from textual.widgets import Markdown

from nexusagent.config import settings

MAX_TOOL_OUTPUT_VISIBLE = 400  # chars before collapsing


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
        Binding("e", "expand_all", "Expand", show=True),
        Binding("a", "collapse_all", "Collapse", show=True),
    ]

    CSS = """
    Screen { layers: base overlay; }

    /* Conversation log — word wrap, no horizontal scroll */
    #conversation-log {
        border: solid #444;
        background: #1a1a1a;
        padding: 0 1;
        overflow-y: auto;
        overflow-x: hidden;
    }

    /* Input */
    #task-input {
        border: solid #666;
        height: 3;
    }
    #task-input:focus {
        border: solid #88f;
    }

    /* Status bar */
    #status-bar {
        height: 1;
        background: #222;
        color: #888;
        padding: 0 1;
    }
    #status-bar SpinnerLabel { width: 100%; }

    /* Streaming response */
    #streaming-response {
        height: auto;
        min-height: 1;
        color: #ddd;
        padding: 0 1;
        overflow-y: hidden;
        overflow-x: hidden;
    }

    /* Queue status */
    #queue-status {
        color: #666;
        text-style: italic;
        height: 1;
        padding: 0 1;
    }

    /* Collapsible tool results */
    Collapsible {
        border: solid #333;
        margin: 0 0 1 0;
    }
    Collapsible > .collapsible--content {
        padding-left: 2;
        padding-top: 0;
        padding-bottom: 0;
    }
    Collapsible > .collapsible--header {
        color: #fa0;
        text-style: bold;
    }
    Collapsible.-collapsed > .collapsible--header {
        color: #888;
    }

    /* Approval modal */
    #approval-dialog {
        width: 80%;
        height: auto;
        max-height: 20;
        border: solid #fa0;
        background: #222;
        padding: 1 2;
    }
    #approval-title {
        text-style: bold;
        color: #fa0;
        padding: 0 0 1 0;
    }
    #approval-args { color: #ccc; padding: 0 0 1 0; }
    #approval-buttons { height: 3; align: right middle; }
    #approval-buttons Button { margin-left: 1; }
    #approval-scroll { max-height: 12; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            RichLog(id="conversation-log", markup=True, auto_scroll=True, wrap=True),
            id="log-container",
        )
        yield Static("", id="streaming-response")
        yield SpinnerLabel("Ready", id="status-bar")
        yield Static("", id="queue-status")
        yield Input(
            placeholder="Type a message or /help for commands...",
            id="task-input",
        )
        yield Footer()

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

        self._show_greeting()
        self._ws_task = asyncio.create_task(self._ws_loop())

    # ── Greeting ──────────────────────────────────────────────────────

    def _show_greeting(self):
        ts = datetime.now().strftime("%H:%M")
        self.log_widget.write("", shrink=False)
        self.log_widget.write(
            f"[b cyan]╔══════════════════════════════════════════╗[/b cyan]",
            shrink=False,
        )
        self.log_widget.write(
            f"[b cyan]║[/b cyan]  [b white]NexusAgent[/b white] — Interactive AI Agent    [b cyan]║[/b cyan]",
            shrink=False,
        )
        self.log_widget.write(
            f"[b cyan]║[/b cyan]  Session: [yellow]{self.session_id}[/yellow]  {ts}              [b cyan]║[/b cyan]",
            shrink=False,
        )
        self.log_widget.write(
            f"[b cyan]╚══════════════════════════════════════════╝[/b cyan]",
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
        ws_url = f"ws://127.0.0.1:{settings.server.api_port}/sessions/{self.session_id}/ws"
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
            self.log_widget.write("[red][b]✗ Cannot connect to server at port {}[/b][/red]".format(
                settings.server.api_port
            ), shrink=False)
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
            if isinstance(args, dict):
                args_str = ", ".join(
                    f"[yellow]{k}[/yellow]=[white]{self._truncate(str(v), 60)}[/white]"
                    for k, v in args.items()
                )
            else:
                args_str = self._truncate(str(args), 80)
            self.log_widget.write(
                f"[dim]⚙[/dim] [b orange]{tool}[/b orange]({args_str})",
                shrink=False,
            )
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
            self._process_next_in_queue()
            self.status_widget.set_text("Ready")

        elif etype == "error":
            message = event.get("message", "Unknown error")
            self.log_widget.write(f"[red][b]✗ Error:[/b] {self._escape(message)}[/red]", shrink=False)
            self._busy = False
            self._process_next_in_queue()
            self.status_widget.set_text("Error")

    # ── Display helpers ──────────────────────────────────────────────

    def _write_tool_result(self, success: bool, output: str, call_id: str):
        """Write a tool result — short results inline, long results collapsible."""
        icon = "✓" if success else "✗"
        color = "green" if success else "red"

        # Try to parse JSON output for cleaner display
        display = self._format_tool_output(output)

        if len(display) <= MAX_TOOL_OUTPUT_VISIBLE:
            self.log_widget.write(
                f"   [{color}]{icon}[/{color}] {display}",
                shrink=False,
            )
        else:
            truncated = self._truncate_output(display)
            collapsible = Collapsible(
                Static(truncated),
                title=f"[{color}]{icon} Tool result ({len(output)} chars)[/{color}]",
                collapsed=True,
            )
            self._collapsibles.append(collapsible)
            self.log_widget.mount(collapsible)
            self.log_widget.scroll_end(animate=False)

    def _format_tool_output(self, output: str) -> str:
        """Format tool output for display — parse JSON, clean up common formats."""
        if not output:
            return "[dim](empty)[/dim]"

        # Try to parse as JSON and extract meaningful content
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                # Common patterns
                if "content" in data:
                    return self._escape(str(data["content"]))
                if "result" in data:
                    return self._escape(str(data["result"]))
                if "output" in data:
                    return self._escape(str(data["output"]))
                if "stdout" in data:
                    return self._escape(str(data["stdout"]))
                # Show first few keys
                preview = {k: self._truncate(str(v), 80) for k, v in list(data.items())[:5]}
                return self._escape(json.dumps(preview, indent=2))
            if isinstance(data, list):
                if len(data) == 0:
                    return "[dim](empty list)[/dim]"
                # Show first few items
                preview = data[:5]
                suffix = f"\n[dim]... ({len(data)} items total)[/dim]" if len(data) > 5 else ""
                return self._escape(json.dumps(preview, indent=2)) + suffix
        except (json.JSONDecodeError, TypeError):
            pass

        # Not JSON — show as-is (escaped)
        return self._escape(output.strip())

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
        args = parts[1:] if len(parts) > 1 else []

        if command == "/help" or command == "/h":
            self._show_help()
            return True

        elif command == "/new" or command == "/n":
            self._show_greeting()
            self.log_widget.write(
                "[yellow]⟶ New conversation started. Previous context cleared.[/yellow]",
                shrink=False,
            )
            # Reset conversation history on server side by creating new session
            # For now, just clear the log
            self.log_widget.clear()
            self._collapsibles.clear()
            self._show_greeting()
            return True

        elif command == "/clear":
            self.log_widget.clear()
            self._collapsibles.clear()
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
            self.log_widget.write(
                f"[dim]Status: {status} | Session: {self.session_id} | "
                f"Queued: {len(self._pending_inputs)}[/dim]",
                shrink=False,
            )
            return True

        elif command == "/interrupt":
            self.action_interrupt()
            return True

        else:
            self.log_widget.write(
                f"[red]Unknown command: {command}. Type /help for available commands.[/red]",
                shrink=False,
            )
            return True

    def _show_help(self):
        self.log_widget.write("", shrink=False)
        self.log_widget.write("[b cyan]Available Commands:[/b cyan]", shrink=False)
        self.log_widget.write("  [b]/help[/b]      Show this help message", shrink=False)
        self.log_widget.write("  [b]/new[/b]       Start a new conversation", shrink=False)
        self.log_widget.write("  [b]/clear[/b]     Clear the conversation log", shrink=False)
        self.log_widget.write("  [b]/expand[/b]    Expand all tool results", shrink=False)
        self.log_widget.write("  [b]/collapse[/b]  Collapse all tool results", shrink=False)
        self.log_widget.write("  [b]/status[/b]    Show session status", shrink=False)
        self.log_widget.write("  [b]/interrupt[/b] Cancel current agent turn", shrink=False)
        self.log_widget.write("  [b]/quit[/b]      Exit the application", shrink=False)
        self.log_widget.write("", shrink=False)
        self.log_widget.write("[b cyan]Keyboard Shortcuts:[/b cyan]", shrink=False)
        self.log_widget.write("  [b]Ctrl+C[/b]  Interrupt current turn", shrink=False)
        self.log_widget.write("  [b]Q[/b]       Quit", shrink=False)
        self.log_widget.write("  [b]C[/b>       Clear log", shrink=False)
        self.log_widget.write("  [b]E[/b>       Expand all", shrink=False)
        self.log_widget.write("  [b]A[/b>       Collapse all", shrink=False)
        self.log_widget.write("", shrink=False)

    # ── Streaming response ───────────────────────────────────────────

    def _write_response_chunk(self, content: str) -> None:
        """Append a streaming token to the in-progress response.

        Updates the streaming-response Static widget in-place so the user
        sees text appearing token-by-token, similar to deepagents' MarkdownStream.
        """
        self._streaming_response += content
        self._streaming_widget.update(
            f"[b green]Agent:[/b green] {self._streaming_response}"
        )

    def _finalize_response(self, content: str) -> None:
        """Finalize the streaming response.

        If streaming was active, the widget already shows the accumulated content.
        Writes the final response into the RichLog for history, clears the
        streaming widget, and resets state.
        """
        if self._streaming_response:
            # Write the complete response to the conversation log for history
            final = content if content else self._streaming_response
            ts = datetime.now().strftime("%H:%M")
            self.log_widget.write("", shrink=False)
            self.log_widget.write(
                f"[b green][{ts}] Agent:[/b green] {self._simple_markdown(final)}",
                shrink=False,
            )
            self.log_widget.write("", shrink=False)
        elif content:
            # No streaming occurred — write full response normally
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
        asyncio.create_task(self._input_queue.put(next_msg))
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
        if event.input.id != "task-input":
            return
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

    def action_quit(self) -> None:
        asyncio.create_task(self._input_queue.put(None))
        if hasattr(self, '_ws_task'):
            self._ws_task.cancel()
        self.exit()

    def action_interrupt(self) -> None:
        if self._ws and self._ws.open:
            asyncio.create_task(self._ws.send(json.dumps({"type": "interrupt"})))
            self.status_widget.set_text("Interrupting...", spinning=True)
            self.log_widget.write("[yellow]⏹ Interrupt sent — waiting for agent to stop...[/yellow]", shrink=False)

    def action_expand_all(self) -> None:
        for c in self._collapsibles:
            c.collapsed = False

    def action_collapse_all(self) -> None:
        for c in self._collapsibles:
            c.collapsed = True

    # ── Helpers ─────────────────────────────────────────────────────

    def _truncate_output(self, output: str) -> str:
        max_chars = MAX_TOOL_OUTPUT_VISIBLE
        if len(output) <= max_chars:
            return output
        head = output[:max_chars // 2]
        tail = output[-(max_chars // 2):]
        return f"{head}\n[dim]... ({len(output)} chars total) ...[/dim]\n{tail}"

    def _truncate(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."

    def _escape(self, text: str) -> str:
        return text.replace("[", "\\[").replace("]", "\\]")

    def _simple_markdown(self, text: str) -> str:
        import re
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
