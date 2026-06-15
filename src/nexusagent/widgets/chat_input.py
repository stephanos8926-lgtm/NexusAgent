"""Chat input widget for NexusAgent TUI.

Multiline input with:
- Enter to submit, Shift+Enter for newline
- Up/Down for command history
- @ triggers completion
- Image paste support
- Slash command autocomplete (Tab to complete)

Design: Linear-inspired, uses $surface background, $border for border.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, ClassVar

from textual.binding import Binding
from textual.events import Key as KeyEvent
from textual.widgets import TextArea

logger = logging.getLogger(__name__)

# Known slash commands for autocomplete
SLASH_COMMANDS: list[str] = sorted([
    "/help",
    "/new",
    "/clear",
    "/resume",
    "/status",
    "/version",
    "/tokens",
    "/model",
    "/theme",
    "/theme-preview",
    "/auto",
    "/compact",
    "/context",
    "/logs",
    "/skills",
    "/skill",
    "/sessions",
    "/threads",
    "/interrupt",
    "/undo",
    "/redo",
    "/copy",
    "/quit",
])
# History file path
_HISTORY_DIR = Path.home() / ".nexusagent"
_HISTORY_FILE = _HISTORY_DIR / "history.json"
_MAX_HISTORY = 200


def _load_history() -> list[str]:
    """Load command history from ``~/.nexusagent/history.json``.

    Returns a list of previously submitted command strings, up to
    ``_MAX_HISTORY`` entries. Returns an empty list if the file
    is missing or corrupt.

    Returns:
        List of historical command strings.
    """
    try:
        if _HISTORY_FILE.exists():
            with open(_HISTORY_FILE) as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data[-_MAX_HISTORY:]
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load command history: {e}")
    return []


def _save_history(history: list[str]) -> None:
    """Persist command history to ``~/.nexusagent/history.json``.

    Writes up to ``_MAX_HISTORY`` most recent entries. Logs a
    warning on failure instead of raising.

    Args:
        history: The full list of command history entries.
    """
    try:
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        with open(_HISTORY_FILE, "w") as f:
            json.dump(history[-_MAX_HISTORY:], f, ensure_ascii=False)
    except OSError as e:
        logger.warning(f"Failed to save command history: {e}")


class ChatInput(TextArea):
    """Multiline chat input widget.

    Extends TextArea with:
    - Key bindings for submit/history
    - Image path detection
    - Slash command completion trigger
    - Command history persistence to ~/.nexusagent/history.json
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "submit", "Submit", show=False),
        Binding("shift+enter", "newline", "Newline", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("tab", "autocomplete", "Autocomplete", show=False),
        Binding("up", "history_prev", "History ↑", show=False),
        Binding("down", "history_next", "History ↓", show=False),
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
        border: solid $primary;
    }
    ChatInput .hint {
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the chat input widget.

        Loads command history from disk and initializes internal state
        for slash command matching and hint display.

        Args:
            **kwargs: Additional keyword arguments passed to TextArea.
        """
        super().__init__(**kwargs)
        self._history: list[str] = _load_history()
        self._history_idx = len(self._history)
        self._slash_matches: list[str] = []
        self._slash_match_idx: int = -1
        self._hint: str | None = None

    def on_mount(self) -> None:
        """Set up the widget on mount: configure border title and hint."""
        self.border_title = "Message"
        self._update_hint()

    def _update_hint(self) -> None:
        """Update the border subtitle with slash command hints."""
        self._hint = self._get_slash_hint()
        if self._hint:
            self.border_subtitle = self._hint
        else:
            self.border_subtitle = ""

    def action_history_prev(self) -> None:
        """Navigate to the previous history entry."""
        if not self._history:
            return
        # Only navigate history when on a single-line input (first row)
        row, _ = self.cursor_location
        if row != 0:
            return
        if self._history_idx > 0:
            self._history_idx -= 1
            self.text = self._history[self._history_idx]
            # Move cursor to end
            self.move_cursor_relative(columns=len(self.text))

    def action_history_next(self) -> None:
        """Navigate to the next history entry (or blank if at end)."""
        row, _ = self.cursor_location
        if row != 0 and self._history_idx < len(self._history) - 1:
            return
        if self._history_idx < len(self._history):
            self._history_idx += 1
        if self._history_idx >= len(self._history):
            self.text = ""
        else:
            self.text = self._history[self._history_idx]

    def on_key(self, event: KeyEvent) -> None:
        """Intercept Enter before TextArea's internal handler.

        TextArea._on_key() inserts '\\n' on Enter and stops the event,
        preventing our Binding("enter", "submit") from ever firing.
        We handle Enter/Shift+Enter here instead.
        """
        if event.key == "enter" and not event.shift:
            # Submit on Enter (without Shift)
            event.stop()
            event.prevent_default()
            self.action_submit()
        elif event.key == "enter" and event.shift:
            # Allow newline on Shift+Enter (let TextArea handle it)
            pass
        else:
            # Delegate everything else to TextArea
            super().on_key(event)

    def action_submit(self) -> None:
        """Submit the current input."""
        text = self.text.strip()
        if not text:
            return

        # Add to history
        self._history.append(text)
        self._history_idx = len(self._history)

        # Persist history to disk
        _save_history(self._history)

        # Parse images from text
        images = self._extract_images(text)

        # Clear input
        self.text = ""

        # Reset slash match state
        self._slash_matches = []
        self._slash_match_idx = -1

        # Clear hint
        self._update_hint()

        # Notify parent
        self.post_message(self.Submitted(text, images))

    def action_cancel(self) -> None:
        """Cancel current input."""
        self.text = ""
        self._slash_matches = []
        self._slash_match_idx = -1
        self._update_hint()

    def on_input_changed(self, event: TextArea.Changed) -> None:
        """Update slash command hint as user types."""
        self._update_hint()

    def action_autocomplete(self) -> None:
        """Tab autocomplete for slash commands."""
        text = self.text.strip()
        if text.startswith("/") and len(text) > 0:
            # If we already have matches, cycle through them
            if self._slash_matches:
                self._slash_match_idx = (self._slash_match_idx + 1) % len(self._slash_matches)
                self.text = self._slash_matches[self._slash_match_idx]
                self.cursor_location = (0, len(self.text))
            else:
                # Find matching commands
                matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(text)]
                if matches:
                    self._slash_matches = matches
                    self._slash_match_idx = 0
                    self.text = matches[0]
                    self.cursor_location = (0, len(self.text))
        else:
            # Default tab behavior: insert spaces
            self.insert("    ")

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

    def _get_slash_hint(self) -> str | None:
        """Return a hint string for slash commands, or None if not applicable."""
        text = self.text.strip()
        if text == "/":
            return "  ".join(SLASH_COMMANDS)
        if text.startswith("/") and len(text) > 1:
            matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(text)]
            if matches:
                return "  ".join(matches)
        return None

    class Submitted(TextArea.Changed):
        """Message posted when input is submitted."""

        # NOTE: We extend TextArea.Changed only to reuse Textual's message routing.
        # The `text` and `images` attributes below are the only fields callers
        # should use; the inherited Changed state is irrelevant.
        BUBBLE = True

        def __init__(self, text: str, images: list[str]) -> None:
            """Initialize a Submitted message.

            Bypasses the TextArea.Changed contract by calling
            Message.__init__ directly.

            Args:
                text: The submitted message text.
                images: List of image paths/URLs extracted from the text.
            """
            # TextArea.Changed requires a TextArea instance; pass None and let
            # Textual set `control` via the normal message routing machinery.
            # We call Message.__init__ directly to avoid the Changed contract.
            from textual.message import Message
            Message.__init__(self)
            self.text = text
            self.images = images
