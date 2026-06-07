import uuid

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Footer, Header, Input, Log, ModalScreen, Static

from nexusagent.models import TaskSchema
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


class NexusApp(App):
    BINDINGS = [("q", "quit", "Quit")]
    CSS = """
    #error-text { color: red; text-style: bold; }
    Log { border: solid #333; background: #000; color: #0f0; }
    Input { border: double #555; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(id="log")
        yield Input(placeholder="Enter coding task...", id="task-input")
        yield Footer()

    def on_mount(self) -> None:
        # Use the stable SDK instead of raw NATS
        self.sdk = NexusSDK()
        self.log_widget = self.query_one(Log)
        self.log_widget.write("NexusAgent TUI Connected via SDK.")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "task-input":
            task_id = str(uuid.uuid4())[:8]
            task = TaskSchema(id=task_id, description=event.value)

            try:
                # The SDK submit_task is an async method
                submitted_id = await self.sdk.submit_task(task.model_dump())
                self.log_widget.write(f"Task {submitted_id} submitted: {event.value}")
            except Exception as e:
                self.push_screen(ErrorModal(str(e)))

            event.input.value = ""


def main() -> None:
    app = NexusApp()
    app.run()


if __name__ == "__main__":
    main()
