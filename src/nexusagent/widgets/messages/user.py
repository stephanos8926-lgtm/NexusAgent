"""User message widget — left-border accent, timestamp prefix."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from textual.content import Content
from textual.widgets import Static


class UserMessage(Static):
    """Widget displaying a user message.

    Styled with a left border accent (like Claude Code / Linear).
    Height auto-expands to fit content with proper word wrapping.
    Includes a dim timestamp prefix.
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
        """Initialize the user message widget.

        Args:
            content: The user's message text.
            **kwargs: Additional keyword arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._content = content

    def render(self) -> Content:
        """Render the user message with a dim timestamp prefix.

        Returns:
            Content with timestamp and message text.
        """
        ts = datetime.now().strftime("%H:%M")
        return Content.assemble(
            (f"  {ts}  ", "text-dim"),
            self._content,
        )
