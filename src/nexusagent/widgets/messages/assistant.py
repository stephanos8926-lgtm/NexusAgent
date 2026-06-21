"""Assistant message widget — uses Textual Markdown for rich rendering."""

from __future__ import annotations

from typing import Any

from textual.widgets import Markdown, Static


class AssistantMessage(Static):
    """Widget displaying an assistant message with streaming support.

    Streams token-by-token into a plain Static buffer, then swaps to a
    Textual Markdown widget on finalize() for full rich rendering:
    headings, lists, fenced code blocks, bold, italic, inline code.
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
    AssistantMessage .assistant-ts {
        color: $text-dim;
    }
    AssistantMessage Markdown {
        background: transparent;
        padding: 0;
        margin: 0;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the assistant message widget with an empty buffer."""
        super().__init__("", **kwargs)
        self._buffer = ""
        self._finalized = False

    async def append_token(self, token: str) -> None:
        """Append a streaming token — renders as plain text during stream."""
        self._buffer += token
        # Direct update without call_next — call_next schedules for the next
        # Textual message pump which may not run if we're in a tight async loop.
        # update() with plain string is thread-safe and triggers immediate render.
        # Using string instead of Content() ensures CSS text-wrap: wrap is respected.
        if not self._finalized:
            self.update(self._buffer)

    def finalize(self, content: str) -> None:
        """Swap to a Markdown widget for full rich rendering."""
        self._buffer = content
        self._finalized = True
        # Replace our plain-text content with a mounted Markdown widget
        self.update("")
        try:
            md = Markdown(content)
            self.mount(md)
        except Exception:
            # Fallback: plain text if Markdown widget fails
            self.update(content)

    def render(self) -> Content:
        """Render the buffered content as plain text.

        Returns:
            Content wrapping the current buffer string.
        """
        from textual.content import Content
        return Content(self._buffer)
