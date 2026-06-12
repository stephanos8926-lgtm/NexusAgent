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
        super().__init__(**kwargs)
        self._message = message

    def render(self) -> Content:
        return Content.assemble(("✗ Error: ", "bold error"), (self._message, "error"))
