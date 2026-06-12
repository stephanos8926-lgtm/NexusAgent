"""App message widget — dim italic styling for system messages."""

from __future__ import annotations

from typing import Any

from textual.content import Content
from textual.widgets import Static


class AppMessage(Static):
    """Widget displaying a system/app message (thinking, status, etc.).

    Dim italic styling to de-emphasize vs user/assistant content.
    """

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
        return Content.assemble(("○ ", "text-muted"), (self._message, "text-muted"))
