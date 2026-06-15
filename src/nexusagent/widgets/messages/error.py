"""Error message widget — icon + border accent for clear visual distinction."""

from __future__ import annotations

from typing import Any

from textual.content import Content
from textual.widgets import Static


class ErrorMessage(Static):
    """Widget displaying an error message.

    Uses $error color with icon and left-border accent for clear visual distinction.
    """

    DEFAULT_CSS = """
    ErrorMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0;
        color: $error;
        border-left: wide $error;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    def __init__(self, message: str, **kwargs: Any) -> None:
        """Initialize the error message widget.

        Args:
            message: The error message text to display.
            **kwargs: Additional keyword arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._message = message

    def render(self) -> Content:
        """Render the error message with a ✗ prefix and error styling.

        Returns:
            Content with bold error icon and message.
        """
        return Content.assemble(("✗ Error: ", "bold error"), (self._message, "error"))
