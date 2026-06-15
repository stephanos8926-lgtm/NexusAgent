"""Welcome banner widget — compact design, shown on first load."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from textual.content import Content
from textual.widgets import Static


class WelcomeBanner(Static):
    """Compact welcome banner shown at session start.

    Single widget — doesn't scroll away like RichLog.write() calls.
    Auto-removed after first user message.
    Clean compact design with session info and help hint.
    """

    DEFAULT_CSS = """
    WelcomeBanner {
        height: auto;
        padding: 1 2;
        margin: 0 0 1 0;
        background: $surface;
        border: solid $border;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    def __init__(self, session_id: str, **kwargs: Any) -> None:
        """Initialize the welcome banner widget.

        Args:
            session_id: The session identifier to display.
            **kwargs: Additional keyword arguments passed to Static.
        """
        ts = datetime.now().strftime("%H:%M")
        self._session_id = session_id
        self._ts = ts
        super().__init__(**kwargs)

    def render(self) -> Content:
        """Render the welcome banner with session info and help hint.

        Returns:
            Content with styled session information.
        """
        return Content.assemble(
            ("NexusAgent", "bold primary"),
            (" — AI Coding Agent  ", ""),
            ("session: ", "text-muted"),
            (self._session_id, "warning"),
            (f"  {self._ts}", "text-muted"),
            ("\n", ""),
            ("Type a message or /help for commands. Ctrl+C to interrupt.", "text-muted"),
        )
