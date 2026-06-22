"""Chat input handling for the TUI.

Handles:
- Chat input submission (slash commands vs user messages)
- Input queue management
"""

from __future__ import annotations

from nexusagent.interfaces.tui.streaming import (  # noqa: I001
    handle_slash_command,
    update_queue_status,
)
from nexusagent.widgets.messages import AppMessage, UserMessage  # noqa: I001


async def on_chat_input_submitted(app, event) -> None:
    """Handle chat input submission from the user.

    Routes slash commands to the command handler or sends user messages
    to the WebSocket server.

    Args:
        app: The NexusApp instance.
        event: The ChatInput.Submitted event.
    """
    message = event.text.strip()
    if not message:
        return

    if message.startswith("/"):
        if event.input is not None:
            event.input.value = ""
        await handle_slash_command(app, message)
        return

    if app._busy:
        app._pending_inputs.append(message)
        msg = AppMessage(f"Queued: {message}")
        app.messages_container.mount(msg)
        update_queue_status(app)
        event.input.value = ""
        return

    app._busy = True
    user_msg = UserMessage(content=message)
    app.messages_container.mount(user_msg)
    app.chat_input.text = ""
    app.status_bar.set_status("Thinking...")
    app.status_bar.set_spinner(True)
    await app._input_queue.put(message)
