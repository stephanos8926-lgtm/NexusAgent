"""Assistant message widget — uses Textual Markdown for rich rendering."""

from __future__ import annotations

from typing import Any

from textual.containers import Vertical
from textual.widgets import Static


class AssistantMessage(Vertical):
    """Widget displaying an assistant message with streaming support.

    Streams token-by-token into a plain Static buffer, then swaps to a
    Textual Markdown widget on finalize() for full rich rendering:
    headings, lists, fenced code blocks, bold, italic, inline code.

    Uses Vertical container as base so that the Markdown child widget
    lays out correctly (Static does not support child layout).
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
    AssistantMessage Static {
        padding: 0;
    }
    AssistantMessage Markdown {
        background: transparent;
        padding: 0;
        margin: 0;
        overflow-x: hidden;
        overflow-y: hidden;
        height: auto;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the assistant message widget with an empty buffer."""
        super().__init__(**kwargs)
        self._buffer = ""
        self._finalized = False
        # Streaming buffer — plain Static that shows tokens as they arrive
        self._streaming_text = Static("", classes="assistant-stream")

    def _ensure_streaming_widget(self) -> None:
        """Mount the streaming buffer on first use (must be called after self is mounted)."""
        from textual.widget import MountError
        try:
            if self._streaming_text not in self.children:
                self.mount(self._streaming_text)
        except MountError:
            return  # Not mounted yet — skip, will retry on next token

    async def append_token(self, token: str) -> None:
        """Append a streaming token — renders as plain text during stream."""
        self._buffer += token
        if not self._finalized:
            self._ensure_streaming_widget()
            self._streaming_text.update(self._buffer)

    def finalize(self, content: str) -> None:
        """Swap to a Markdown widget for full rich rendering."""
        if self._finalized:
            return  # Guard against double-finalize
        self._buffer = content
        self._finalized = True
        try:
            from textual.widgets import Markdown as TextualMarkdown

            # Remove the streaming buffer, mount Markdown in its place
            self._ensure_streaming_widget()
            self._streaming_text.remove()
            md = TextualMarkdown(content)
            self.mount(md)
        except Exception:
            # Fallback: plain text if Markdown widget fails
            self._streaming_text.update(content)
