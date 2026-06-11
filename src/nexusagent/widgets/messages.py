"""Message widgets for NexusAgent TUI.

Each message type is a separate Textual widget with its own CSS styling.
This follows the deepagents pattern: individual widgets mounted into a
Container with layout:stream for O(1) append performance.
"""

from __future__ import annotations

import logging
from typing import Any

from textual.containers import Vertical
from textual.content import Content
from textual.widgets import Static

logger = logging.getLogger(__name__)


class UserMessage(Static):
    """Widget displaying a user message.

    Styled with a left border accent (like Claude Code's user messages).
    Height is auto — expands to fit content with word wrapping.
    """

    DEFAULT_CSS = """
    UserMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0 0 0;
        background: transparent;
        border-left: wide $primary;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    def __init__(self, content: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._content = content

    def render(self) -> Content:
        return Content(self._content)


class AssistantMessage(Static):
    """Widget displaying an assistant message.

    Renders markdown-like content with text wrapping.
    Height auto-expands to fit content.
    """

    DEFAULT_CSS = """
    AssistantMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0;
        background: transparent;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    def __init__(self, content: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._content = content

    def render(self) -> Content:
        return Content(self._content)


class ToolCallMessage(Static):
    """Widget displaying a tool call with collapsible output.

    Shows tool name + args in a compact header.
    Output is shown inline for short results, collapsible for long ones.
    """

    DEFAULT_CSS = """
    ToolCallMessage {
        height: auto;
        padding: 0 1;
        margin: 0 0 0 2;
        background: transparent;
        border-left: wide $warning;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    ToolCallMessage:hover {
        border-left: wide $secondary;
    }
    """

    def __init__(self, tool: str, args: str, output: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tool = tool
        self._args = args
        self._output = output

    def render(self) -> Content:
        header = f"⚙ {self._tool}({self._args})"
        if self._output:
            # Truncate long output
            output = self._output
            if len(output) > 200:
                output = output[:197] + "..."
            return Content.assemble(
                (header, "bold orange"),
                "\n",
                (output, "dim"),
            )
        return Content(header)


class AppMessage(Static):
    """Widget displaying a system/app message (thinking, status, etc.)."""

    DEFAULT_CSS = """
    AppMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0;
        color: $text-muted;
        text-style: italic;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._message = message

    def render(self) -> Content:
        return Content(self._message)


class ErrorMessage(Static):
    """Widget displaying an error message."""

    DEFAULT_CSS = """
    ErrorMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0;
        color: $error;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._message = message

    def render(self) -> Content:
        return Content.assemble(("✗ ", "bold error"), self._message)


class WelcomeBanner(Static):
    """Compact welcome banner shown at session start.

    Single widget — doesn't scroll away like RichLog.write() calls.
    """

    DEFAULT_CSS = """
    WelcomeBanner {
        height: auto;
        padding: 1 2;
        margin: 0 0 1 0;
        background: $surface;
        border: solid $panel;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    def __init__(self, session_id: str, **kwargs: Any) -> None:
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M")
        text = (
            f"[b cyan]╔══════════════════════════════════════╗[/b cyan]\n"
            f"[b cyan]║[/b cyan]  [b white]NexusAgent[/b white] — AI Coding Agent    [b cyan]║[/b cyan]\n"
            f"[b cyan]║[/b cyan]  Session: [yellow]{session_id}[/yellow]  {ts}        [b cyan]║[/b cyan]\n"
            f"[b cyan]╚══════════════════════════════════════╝[/b cyan]\n"
            f"\n"
            f"[dim]Type a message or /help for commands. Ctrl+C to interrupt.[/dim]"
        )
        super().__init__(text, **kwargs)
