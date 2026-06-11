"""Chat input widget for NexusAgent TUI.

Multiline input with:
- Enter to submit, Shift+Enter for newline
- Up/Down for command history
- @ triggers completion
- Image paste support

Design: Linear-inspired, uses $surface background, $border for border.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from textual.binding import Binding
from textual.widgets import TextArea

logger = logging.getLogger(__name__)


class ChatInput(TextArea):
    """Multiline chat input widget.

    Extends TextArea with:
    - Key bindings for submit/history
    - Image path detection
    - Slash command completion trigger
    """

    BINDINGS: list[Binding] = [
        Binding("enter", "submit", "Submit", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    ChatInput {
        height: auto;
        min-height: 3;
        max-height: 15;
        background: $surface;
        border: solid $border;
        padding: 0 1;
        text-wrap: wrap;
    }
    ChatInput:focus {
        border: solid $border-focus;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._history: list[str] = []
        self._history_idx = -1

    def on_mount(self) -> None:
        self.border_title = "Message"

    def action_submit(self) -> None:
        """Submit the current input."""
        text = self.text.strip()
        if not text:
            return

        # Add to history
        self._history.append(text)
        self._history_idx = len(self._history)

        # Parse images from text
        images = self._extract_images(text)

        # Clear input
        self.text = ""

        # Notify parent
        self.post_message(self.Submitted(text, images))

    def action_cancel(self) -> None:
        """Cancel current input."""
        self.text = ""

    def _extract_images(self, text: str) -> list[str]:
        """Extract image paths/URLs from text.

        Looks for:
        - /path/to/image.png
        - ~/path/to/image.jpg
        - https://example.com/image.png
        """
        import re
        images = []
        # Match URLs
        for m in re.finditer(r'https?://\S+\.(?:png|jpg|jpeg|webp|gif|bmp)\b', text, re.IGNORECASE):
            images.append(m.group())
        # Match local paths (simple heuristic)
        for m in re.finditer(r'(?:[/~]\S+\.(?:png|jpg|jpeg|webp|gif|bmp))\b', text, re.IGNORECASE):
            images.append(m.group())
        return images

    class Submitted(TextArea.Changed):
        """Message posted when input is submitted."""

        def __init__(self, text: str, images: list[str]) -> None:
            super().__init__()
            self.text = text
            self.images = images
