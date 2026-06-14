"""Assistant message widget — uses Textual Markdown for rich rendering."""

from __future__ import annotations

from typing import Any

from textual.content import Content
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
        super().__init__("", **kwargs)
        self._buffer = ""
        self._finalized = False

    async def append_token(self, token: str) -> None:
        """Append a streaming token — renders as plain text during stream."""
        self._buffer += token
        self.app.call_next(self._render_streaming)

    def _render_streaming(self) -> None:
        """Render buffer as plain text while streaming (fast path)."""
        if not self._finalized:
            self.update(Content(self._buffer))

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
            self.update(Content(content))

    def render(self) -> Content:
        return Content(self._buffer)
