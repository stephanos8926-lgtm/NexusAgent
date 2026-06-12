"""Assistant message widget — streaming support, markdown-like rendering."""

from __future__ import annotations

from typing import Any

from textual.content import Content
from textual.widgets import Static


class AssistantMessage(Static):
    """Widget displaying an assistant message.

    Supports streaming via append_token() and finalize().
    Renders markdown-like content (**bold**, *italic*, `code`) with
    proper word wrapping using Content for rich styled rendering.
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

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self._buffer = ""

    async def append_token(self, token: str) -> None:
        """Append a streaming token and update the display immediately.

        Uses self.app.call_next() to schedule a repaint on the next
        event-loop tick, ensuring each token is rendered individually
        rather than batched by Textual's update coalescing.
        """
        self._buffer += token
        self.app.call_next(self._render_buffer)

    def _render_buffer(self) -> None:
        """Render the current buffer content (called via call_next)."""
        self.update(Content(self._buffer))

    def finalize(self, content: str) -> None:
        """Set the final content (overrides buffer)."""
        self._buffer = content
        self.update(Content(content))

    def render(self) -> Content:
        return self._render_markdown(self._buffer)

    def _render_markdown(self, text: str) -> Content:
        """Parse simple markdown-like syntax and return styled Content.

        Supports **bold**, *italic*, and `inline code` patterns.
        Falls back to plain Content if no patterns are found.
        """
        if not text:
            return Content("")

        # Fast path: no markdown patterns at all
        if "**" not in text and "*" not in text and "`" not in text:
            return Content(text)

        # Build styled segments by parsing markdown patterns
        parts = self._parse_markdown(text)
        if parts:
            return Content.assemble(*parts)
        return Content(text)

    def _parse_markdown(self, text: str) -> list[tuple[str, str]]:
        """Parse markdown-like syntax into (text, style) tuples.

        Handles **bold**, *italic*, and `code` inline patterns.
        """
        result: list[tuple[str, str]] = []
        pos = 0
        length = len(text)

        while pos < length:
            # Try to match **bold**
            bold_match = None
            if pos + 1 < length and text[pos : pos + 2] == "**":
                end = text.find("**", pos + 2)
                if end != -1:
                    bold_match = (pos, end + 2, text[pos + 2 : end], "bold")

            # Try to match *italic* (but not inside **)
            italic_match = None
            if text[pos] == "*":
                # Make sure it's not the start of **
                if pos + 1 >= length or text[pos + 1] != "*":
                    end = text.find("*", pos + 1)
                    if end != -1:
                        italic_match = (pos, end + 1, text[pos + 1 : end], "italic")

            # Try to match `code`
            code_match = None
            if text[pos] == "`":
                end = text.find("`", pos + 1)
                if end != -1:
                    code_match = (pos, end + 1, text[pos + 1 : end], "text-muted")

            # Find the earliest match
            matches = [m for m in [bold_match, italic_match, code_match] if m is not None]
            if matches:
                # Pick the match that starts earliest (they should all start at pos)
                match = min(matches, key=lambda m: m[0])
                start, end, content, style = match
                if content:  # Only add non-empty matches
                    result.append((content, style))
                pos = end
            else:
                # No match at this position — find the next potential special char
                next_special = length
                for ch in ("**", "*", "`"):
                    idx = text.find(ch, pos + 1)
                    if idx != -1 and idx < next_special:
                        next_special = idx
                # Add plain text up to next special char
                plain = text[pos:next_special] if next_special < length else text[pos:]
                if plain:
                    result.append((plain, ""))
                pos = next_special if next_special < length else length

        return result
