import uuid
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Log, Static

from nexusagent.sdk import NexusSDK


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
    def __init__(self, tool_name: str, tool_args: dict) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args

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
        yield Input(placeholder="Enter coding task...", id="task-input")
        yield Footer()

    def on_mount(self) -> None:
        self.session_id = str(uuid.uuid4())[:8]
        self.sdk = NexusSDK()
        self.log_widget = self.query_one(Log)
        self.log_widget.write(f"[Session {self.session_id}] Connected to NexusAgent.")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "task-input":
            message = event.value.strip()
            if not message:
                return
            self.log_widget.write(f"User: {message}")
            event.input.value = ""
            await self._send_to_agent(message)

    async def _send_to_agent(self, message: str) -> None:
        task_id = str(uuid.uuid4())[:8]
        try:
            submitted_id = await self.sdk.submit_task({"id": task_id, "description": message})
            self.log_widget.write(f"Agent: Task {submitted_id} submitted.")
            result = await self.sdk.wait_for_result(submitted_id, timeout=300)
            if result and result.success:
                self.log_widget.write(f"Agent: {result.data}")
            elif result:
                self.log_widget.write(f"Agent Error: {result.error}")
            else:
                self.log_widget.write("Agent: No result received (timeout).")
        except Exception as e:
            self.push_screen(ErrorModal(str(e)))

    def action_clear(self) -> None:
        self.log_widget.clear()


def main() -> None:
    app = NexusApp()
    app.run()


if __name__ == "__main__":
    main()
