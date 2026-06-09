"""Terminal UI for NexusAgent — real-time streaming chat interface.

Features:
- Real-time tool call/result streaming with collapsible output
- Token-by-token thinking display
- Markdown rendering for agent responses
- Status bar with spinner, state, and queued message count
- Interrupt support (Ctrl+C)
- Keyboard shortcuts (Q quit, C clear, E expand all, A collapse all)
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

from nexusagent.config import settings

MAX_TOOL_OUTPUT_VISIBLE = 300  # chars before collapsing


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


class ApprovalModal(ModalScreen[bool]):
    """Modal dialog for approving/rejecting tool calls."""

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


class NexusApp(App):
    """Main TUI application."""

    BINDINGS: ClassVar = [
        Binding("q", "quit", "Quit", priority=True, show=True),
        Binding("escape", "quit", "Quit", priority=True, show=False),
        Binding("c", "clear", "Clear", show=True),
        Binding("ctrl+c", "interrupt", "Interrupt", show=True),
        Binding("e", "expand_all", "Expand", show=True),
        Binding("a", "collapse_all", "Collapse", show=True),
    ]

    CSS = """
    Screen {
        layers: base overlay;
    }

    /* Conversation log */
    #conversation-log {
        border: solid #444;
        background: #1a1a1a;
        padding: 0 1;
        overflow-y: auto;
        overflow-x: auto;
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
    #status-bar SpinnerLabel {
        width: 100%;
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

    /* Status message (queued count etc) */
    #queue-status {
        color: #666;
        text-style: italic;
        height: 1;
        padding: 0 1;
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
    #approval-args {
        color: #ccc;
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

    /* Tool call inline */
    .tool-call {
        color: #fa0;
    }
    .tool-result-ok {
        color: #0f0;
    }
    .tool-result-err {
        color: #f44;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(RichLog(id="conversation-log", markup=True, auto_scroll=True), id="log-container")
        yield SpinnerLabel("Ready", id="status-bar")
        yield Static("", id="queue-status")
        yield Input(placeholder="Enter message... (Enter to submit, Ctrl+C to interrupt, Q to quit)", id="task-input")
        yield Footer()

    def on_mount(self) -> None:
        self.session_id = str(uuid.uuid4())[:8]
        self.log_widget = self.query_one("#conversation-log", RichLog)
        self.status_widget = self.query_one("#status-bar", SpinnerLabel)
        self.queue_status = self.query_one("#queue-status", Static)
        self._input_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._busy = False
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._collapsibles: list[Collapsible] = []  # track for expand/collapse all
        self._pending_inputs: list[str] = []  # queued messages

        self.log_widget.write(
            f"[b][cyan]Session {self.session_id}[/cyan][/b] — Connecting...",
            shrink=False,
        )
        self._ws_task = asyncio.create_task(self._ws_loop())

    # ── WebSocket loop ──────────────────────────────────────────────

    async def _ws_loop(self) -> None:
        ws_url = f"ws://127.0.0.1:{settings.server.api_port}/sessions/{self.session_id}/ws"
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                self._ws = ws
                self.log_widget.write("[green]Connected.[/green]", shrink=False)
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
            self.log_widget.write("[red][b]Cannot connect to server.[/b][/red]", shrink=False)
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
            pass  # no noise

        elif etype == "thinking":
            content = event.get("content", "")
            self._write_thinking(content)

        elif etype == "tool_call":
            tool = event.get("tool", "?")
            args = event.get("args", {})
            if isinstance(args, dict):
                args_str = ", ".join(f"[yellow]{k}[/yellow]=[white]{v}[/white]" for k, v in args.items())
            else:
                args_str = str(args)
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
            self.status_widget.set_text("Processing response...")

        elif etype == "approval_request":
            tool = event.get("tool", "?")
            args = event.get("args", {})
            call_id = event.get("call_id", "")
            self.status_widget.set_text("Awaiting approval...", spinning=False)
            approved = await self.push_screen_wait(ApprovalModal(tool, args, call_id))
            # Send approval over the existing connection via the queue
            # We need a separate channel — use a direct send since we can't
            # use the queue (it's for user_input). Create a one-shot approval.
            await self._send_approval(call_id, approved)
            self.status_widget.set_text("Ready")

        elif etype == "response":
            content = event.get("content", "")
            self._write_response(content)
            self._busy = False
            # Process queued messages
            self._process_next_in_queue()
            self.status_widget.set_text("Ready")

        elif etype == "error":
            message = event.get("message", "Unknown error")
            self.log_widget.write(f"[red][b]Error:[/b] {message}[/red]", shrink=False)
            self._busy = False
            self._process_next_in_queue()
            self.status_widget.set_text("Error")

    def _write_thinking(self, content: str):
        """Write a thinking token inline."""
        if not content:
            return
        # Dim italic — shows model's reasoning as it streams
        self.log_widget.write(f"[dim italic]⟶ {content}[/dim italic]", shrink=False)

    def _write_tool_result(self, success: bool, output: str, call_id: str):
        """Write a tool result as a collapsible section."""
        icon = "✓" if success else "✗"
        color = "green" if success else "red"
        tool_desc = f"[b {color}]{icon} Tool result[/b {color}]"

        if len(output) <= MAX_TOOL_OUTPUT_VISIBLE:
            # Short output — show inline
            display = output.strip()
            self.log_widget.write(
                f"   {tool_desc}: [dim]{self._escape(display)}[/dim]",
                shrink=False,
            )
        else:
            # Long output — make a collapsible
            display = self._truncate_output(output)
            collapsible = Collapsible(
                Static(f"[dim]{self._escape(display)}[/dim]"),
                title=f"{tool_desc} ({len(output)} chars)",
                collapsed=True,
            )
            self._collapsibles.append(collapsible)
            self.log_widget.mount(collapsible)
            self.log_widget.scroll_end(animate=False)

    def _write_response(self, content: str):
        """Write the final agent response with markdown-style formatting."""
        ts = datetime.now().strftime("%H:%M")
        # Simple markdown — bold, italic, code blocks
        formatted = self._simple_markdown(content)
        self.log_widget.write("", shrink=False)  # spacer
        self.log_widget.write(
            f"[b green][{ts}] Agent:[/b green] {formatted}",
            shrink=False,
        )
        self.log_widget.write("", shrink=False)  # spacer

    # ── Queue management ────────────────────────────────────────────

    def _process_next_in_queue(self):
        """Send the next queued message if any."""
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
        """Send an approval decision back to the server."""
        # We need to send through the existing WS but the send loop only
        # reads from _input_queue. Use a separate message type.
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
        """Send an interrupt to cancel the current agent turn."""
        if self._ws and self._ws.open:
            asyncio.create_task(self._ws.send(json.dumps({"type": "interrupt"})))
            self.status_widget.set_text("Interrupting...", spinning=True)
            self.log_widget.write("[yellow]⏹ Interrupt sent[/yellow]", shrink=False)

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
        return f"{head}\n... ({len(output)} chars total) ...\n{tail}"

    def _escape(self, text: str) -> str:
        """Escape Rich markup characters in tool output."""
        return text.replace("[", "\\[").replace("]", "\\]")

    def _simple_markdown(self, text: str) -> str:
        """Convert simple markdown to Rich markup."""
        import re
        # Bold: **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'[b]\1[/b]', text)
        # Italic: *text*
        text = re.sub(r'\*(.+?)\*', r'[i]\1[/i]', text)
        # Inline code: `text`
        text = re.sub(r'`(.+?)`', r'[reverse]\1[/reverse]', text)
        # Code blocks: ```lang\n...\n``` — just strip backticks
        text = re.sub(r'```\w*\n?', '', text)
        text = re.sub(r'```', '', text)
        return text


def main() -> None:
    app = NexusApp()
    app.run()


if __name__ == "__main__":
    main()
