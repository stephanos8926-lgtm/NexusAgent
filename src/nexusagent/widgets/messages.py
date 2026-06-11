"""Message widgets for NexusAgent TUI.

Each message type is a separate Textual Static widget with its own CSS styling.
This follows the deepagents pattern: individual widgets mounted into a
Container with layout:stream for O(1) append performance.

Design system: Linear-inspired dark theme with indigo-violet accent.
- Near-black background (#11181C), not pure white text (#F7F8F8)
- Single accent color (#5E6AD2) used sparingly
- Semi-transparent white borders (rgba(255,255,255,0.05-0.08))
- height:auto on all messages — expands to fit content
- text-wrap: wrap for proper word wrapping (NOT RichLog wrap=True)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from textual.containers import Vertical
from textual.content import Content
from textual.widgets import Static

logger = logging.getLogger(__name__)

# Regex to detect fenced code blocks in tool output
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`[^`]+`")


class UserMessage(Static):
    """Widget displaying a user message.

    Styled with a left border accent (like Claude Code / Linear).
    Height auto-expands to fit content with proper word wrapping.
    """

    DEFAULT_CSS = """
    UserMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0 0 0;
        background: transparent;
        border-left: wide $primary;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    def __init__(self, content: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._content = content

    def render(self) -> Content:
        return Content(self._content)


class AssistantMessage(Static):
    """Widget displaying an assistant message.

    Supports streaming via append_token() and finalize().
    Renders markdown-like content with proper word wrapping.
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
        # Schedule immediate repaint so each token renders in real-time
        # rather than being batched with subsequent updates.
        self.app.call_next(self._render_buffer)

    def _render_buffer(self) -> None:
        """Render the current buffer content (called via call_next)."""
        self.update(Content(self._buffer))

    def finalize(self, content: str) -> None:
        """Set the final content (overrides buffer)."""
        self._buffer = content
        self.update(Content(content))


class ToolCallMessage(Static):
    """Widget displaying a tool call with output.

    Shows tool name + args in a compact header.
    Output is shown inline for short results, truncated for long ones.
    Border uses $warning color to distinguish from user/assistant messages.

    Status indicators:
    - ⚙ running (default)
    - ✔ success
    - ✘ failed
    """

    DEFAULT_CSS = """
    ToolCallMessage {
        height: auto;
        padding: 0 1;
        margin: 0 0 0 2;
        background: transparent;
        border-left: wide $warning;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    ToolCallMessage:hover {
        border-left: wide $accent-light;
    }
    """

    # Status constants
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    _STATUS_ICONS = {
        STATUS_RUNNING: "⚙",
        STATUS_SUCCESS: "✔",
        STATUS_FAILED: "✘",
    }

    _STATUS_STYLES = {
        STATUS_RUNNING: "bold warning",
        STATUS_SUCCESS: "bold success",
        STATUS_FAILED: "bold error",
    }

    def __init__(
        self,
        tool: str,
        args: str,
        output: str = "",
        status: str = "running",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._tool = tool
        self._args = args
        self._output = output
        self._status = status

    def _format_args(self, raw_args: str) -> str:
        """Pretty-print args if they look like JSON, otherwise return as-is."""
        stripped = raw_args.strip()
        if not stripped:
            return ""
        # Try to parse as JSON for pretty-printing
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
                return json.dumps(parsed, indent=None, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                pass
        return raw_args

    def _detect_code(self, text: str) -> bool:
        """Return True if the output contains code blocks or inline code."""
        return bool(_CODE_BLOCK_RE.search(text) or _INLINE_CODE_RE.search(text))

    def _truncate_output(self, text: str, max_chars: int = 300) -> str:
        """Truncate output with a clear indicator of remaining characters."""
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars].rstrip()
        remaining = len(text) - max_chars
        return f"{truncated} ... ({remaining} more chars)"

    def render(self) -> Content:
        icon = self._STATUS_ICONS.get(self._status, "⚙")
        style = self._STATUS_STYLES.get(self._status, "bold warning")

        formatted_args = self._format_args(self._args)
        header = f"{icon} {self._tool}({formatted_args})"

        if not self._output:
            return Content.assemble((header, style))

        output = self._truncate_output(self._output)

        # Build output display with code detection hint
        has_code = self._detect_code(self._output)
        output_parts = [(header, style), "\n"]

        if has_code:
            output_parts.append(("  [code] ", "text-muted"))
            output_parts.append((output, "text-muted"))
        else:
            output_parts.append((output, "text-muted"))

        return Content.assemble(*output_parts)


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
        super().__init__(message, **kwargs)


class ErrorMessage(Static):
    """Widget displaying an error message.

    Uses $error color with icon for clear visual distinction.
    """

    DEFAULT_CSS = """
    ErrorMessage {
        height: auto;
        padding: 0 1;
        margin: 1 0;
        color: $error;
        text-wrap: wrap;
        overflow-x: hidden;
    }
    """

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)

    def render(self) -> Content:
        return Content.assemble(("✗ Error: ", "bold error"), self._text)


class WelcomeBanner(Static):
    """Compact welcome banner shown at session start.

    Single widget — doesn't scroll away like RichLog.write() calls.
    Auto-removed after first user message.
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
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M")
        text = (
            f"[b primary]╔══════════════════════════════════════╗[/b primary]\n"
            f"[b primary]║[/b primary]  [b]NexusAgent[/b] — AI Coding Agent    [b primary]║[/b primary]\n"
            f"[b primary]║[/b primary]  Session: [warning]{session_id}[/warning]  {ts}        [b primary]║[/b primary]\n"
            f"[b primary]╚══════════════════════════════════════╝[/b primary]\n"
            f"\n"
            f"[text-muted]Type a message or /help for commands. Ctrl+C to interrupt.[/text-muted]"
        )
        super().__init__(text, **kwargs)
