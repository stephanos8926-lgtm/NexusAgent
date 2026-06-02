from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Log, Static, Button, ModalScreen
from textual.containers import Vertical
import asyncio
import nats
import json

class ErrorModal(ModalScreen):
    def __init__(self, error_message):
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
    #error-text { color: red; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(id="log")
        yield Input(placeholder="Enter coding task...", id="task-input")
        yield Footer()

    async def on_mount(self) -> None:
        self.nc = await nats.connect("nats://localhost:4222")
        self.log_widget = self.query_one(Log)
        await self.nc.subscribe("task.log", cb=self.handle_log)
        await self.nc.subscribe("task.error", cb=self.handle_error)
        self.log_widget.write("NexusAgent TUI Connected.")

    async def handle_log(self, msg):
        self.log_widget.write(msg.data.decode())

    async def handle_error(self, msg):
        error = msg.data.decode()
        self.push_screen(ErrorModal(error))

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "task-input":
            await self.nc.publish("task.new", event.value.encode())
            self.log_widget.write(f"Task submitted: {event.value}")
            event.input.value = ""

def main():
    app = NexusApp()
    app.run()

if __name__ == "__main__":
    main()
