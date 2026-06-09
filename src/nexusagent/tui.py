import asyncio
import json
import uuid
from typing import ClassVar

import websockets
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Log, Static

from nexusagent.config import settings


class ErrorModal(ModalScreen):
    def __init__(self, error_message: str) -> None:
        super().__init__()
        self.error_message = error_message

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"Terminal Error: {self.error_message}", id="error-text"),
            Input(placeholder="Provide correction guidance..."),
            Button("Retry", id="retry"),
            Button("Abort", id="abort"),
        )


class ApprovalModal(ModalScreen[bool]):
    def __init__(self, tool_name: str, tool_args: dict, call_id: str = "") -> None:
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.call_id = call_id

    def compose(self) -> ComposeResult:
        args_str = "\n".join(f"  {k}: {v}" for k, v in self.tool_args.items())
        yield Vertical(
            Static(f"Approval Required: {self.tool_name}", id="approval-title"),
            Static(args_str, id="approval-args"),
            Button("Approve", id="approve", variant="success"),
            Button("Reject", id="reject", variant="error"),
            Button("Cancel", id="cancel"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve":
            self.dismiss(True)
        elif event.button.id == "reject":
            self.dismiss(False)
        else:
            self.dismiss(False)


class NexusApp(App):
    BINDINGS: ClassVar = [("q", "quit", "Quit"), ("c", "clear", "Clear")]
    CSS = """
    #error-text { color: red; text-style: bold; }
    #conversation-log { border: solid #333; background: #000; color: #0f0; }
    #task-input { border: double #555; }
    .thinking { color: #888; text-style: italic; }
    .tool-call { color: #ff0; }
    .response { color: #0f0; }
    .error { color: #f00; text-style: bold; }
    #approval-title { text-style: bold; color: #ff0; }
    #approval-args { color: #ccc; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(id="conversation-log")
        yield Input(placeholder="Enter message... (Enter to submit)", id="task-input")
        yield Footer()

    def on_mount(self) -> None:
        self.session_id = str(uuid.uuid4())[:8]
        self.log_widget = self.query_one(Log)
        self.log_widget.write(f"[Session {self.session_id}] Connecting to NexusAgent via WebSocket...")
        self._ws_task = asyncio.create_task(self._ws_loop())

    async def _ws_loop(self) -> None:
        """Maintain WebSocket connection: send user input, stream agent events."""
        ws_url = f"ws://127.0.0.1:{settings.server.api_port}/sessions/{self.session_id}/ws"
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                self.log_widget.write(f"[Session {self.session_id}] Connected.")

                async def send_messages():
                    """Read from the TUI input queue and send to WS."""
                    while True:
                        # Wait for input from the TUI event handler
                        msg = await self._input_queue.get()
                        if msg is None:
                            break
                        await ws.send(json.dumps({"type": "user_input", "content": msg}))

                async def receive_events():
                    """Read WS events and write to the log."""
                    async for raw in ws:
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        await self._handle_event(event)

                await asyncio.gather(send_messages(), receive_events())

        except ConnectionRefusedError:
            self.log_widget.write("[Error] Cannot connect to NexusAgent server.")
            self.log_widget.write("Start the server with: nexus-server")
        except websockets.exceptions.ConnectionClosedOK:
            self.log_widget.write("[Session closed]")
        except websockets.exceptions.ConnectionClosedError as e:
            self.log_widget.write(f"[Connection lost: {e}]")
        except Exception as e:
            self.log_widget.write(f"[Error: {e}]")

    async def _handle_event(self, event: dict) -> None:
        """Route a server event to the appropriate UI update."""
        etype = event.get("type")

        if etype == "session_status":
            status = event.get("status", "?")
            if status == "active":
                self.log_widget.write("[Session active]")
            else:
                self.log_widget.write(f"[Session {status}]")

        elif etype == "thinking":
            content = event.get("content", "")
            self.log_widget.write(f"[Thinking] {content}")

        elif etype == "tool_call":
            tool = event.get("tool", "?")
            args = event.get("args", {})
            call_id = event.get("call_id", "")
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            self.log_widget.write(f"[Tool] {tool}({args_str})")

        elif etype == "tool_result":
            call_id = event.get("call_id", "")
            output = event.get("output", "")
            success = event.get("success", True)
            status = "✓" if success else "✗"
            self.log_widget.write(f"[Result {status}] {output[:200]}")

        elif etype == "approval_request":
            tool = event.get("tool", "?")
            args = event.get("args", {})
            call_id = event.get("call_id", "")
            # Show approval modal
            self.log_widget.write(f"[Approval Required] {tool}")
            approved = await self.push_screen_wait(ApprovalModal(tool, args, call_id))
            # Send approval response via WS
            try:
                ws_url = f"ws://127.0.0.1:{settings.server.api_port}/sessions/{self.session_id}/ws"
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({
                        "type": "approval",
                        "call_id": call_id,
                        "approved": approved,
                    }))
            except Exception:
                self.log_widget.write("[Error] Failed to send approval response")

        elif etype == "response":
            content = event.get("content", "")
            self.log_widget.write(f"Agent: {content}")

        elif etype == "error":
            message = event.get("message", "Unknown error")
            self.log_widget.write(f"[Error] {message}")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "task-input":
            message = event.value.strip()
            if not message:
                return
            self.log_widget.write(f"User: {message}")
            event.input.value = ""
            # Queue the message for the WS sender
            if not hasattr(self, '_input_queue'):
                self._input_queue = asyncio.Queue()
            await self._input_queue.put(message)

    def action_clear(self) -> None:
        self.log_widget.clear()

    def action_quit(self) -> None:
        """Clean shutdown: close WS task."""
        if hasattr(self, '_ws_task'):
            self._ws_task.cancel()
        super().action_quit()


def main() -> None:
    app = NexusApp()
    app.run()


if __name__ == "__main__":
    main()
