"""Tool call message widget — collapsible output, syntax hints, status indicators."""

from __future__ import annotations

import json
import re
from typing import Any

from textual.content import Content
from textual.widgets import Static

# Regex patterns for code detection (only used by this module)
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_CODE_BLOCK_LANG_RE = re.compile(r"```(\w*)\n[\s\S]*?```")
_NEWLINE_RE = re.compile(r"\n")

# Collapse threshold: outputs with more lines than this are collapsed by default
_COLLAPSE_LINE_THRESHOLD = 4
_COLLAPSE_CHAR_THRESHOLD = 300


class ToolCallMessage(Static):
    """Widget displaying a tool call with output.

    Shows tool name + args in a compact header.
    Output is collapsible for long results, with syntax hints for code.
    Border uses $warning color to distinguish from user/assistant messages.

    Status indicators:
    - ⚙ running (default)
    - ✔ success
    - ✘ failed

    Features:
    - update_status() / update_output() for live updates
    - toggle_collapse() for expandable output
    - _detect_syntax_hint() for language detection
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
        # Determine if output should be collapsed by default
        self._collapsed = self._should_collapse(output)

    def _should_collapse(self, output: str) -> bool:
        """Determine if output should be collapsed by default."""
        if not output:
            return False
        line_count = len(_NEWLINE_RE.findall(output))
        return line_count >= _COLLAPSE_LINE_THRESHOLD or len(output) >= _COLLAPSE_CHAR_THRESHOLD

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

    def _detect_syntax_hint(self) -> str | None:
        """Detect the syntax/language hint from fenced code blocks.

        Returns the language identifier from the first fenced code block,
        or None if no code blocks are found.
        """
        match = _CODE_BLOCK_LANG_RE.search(self._output)
        if match:
            lang = match.group(1)
            return lang if lang else None
        return None

    def _truncate_output(self, text: str, max_chars: int = 300) -> str:
        """Truncate output with a clear indicator of remaining characters."""
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars].rstrip()
        remaining = len(text) - max_chars
        return f"{truncated} ... ({remaining} more chars)"

    def _count_lines(self, text: str) -> int:
        """Count the number of lines in text."""
        if not text:
            return 0
        return text.count("\n") + 1

    def update_status(self, status: str) -> None:
        """Update the status and refresh the display."""
        self._status = status
        self.refresh()

    def update_output(self, output: str) -> None:
        """Update the output and refresh the display."""
        self._output = output
        self._collapsed = self._should_collapse(output)
        self.refresh()

    def toggle_collapse(self) -> None:
        """Toggle the collapsed state of the output."""
        self._collapsed = not self._collapsed
        self.refresh()

    def render(self) -> Content:
        icon = self._STATUS_ICONS.get(self._status, "⚙")
        style = self._STATUS_STYLES.get(self._status, "bold warning")

        formatted_args = self._format_args(self._args)
        header = f"{icon} {self._tool}({formatted_args})"

        if not self._output:
            return Content.assemble((header, style))

        # Build output display
        has_code = self._detect_code(self._output)
        syntax_hint = self._detect_syntax_hint()
        line_count = self._count_lines(self._output)

        output_parts = [(header, style)]

        # Add syntax hint if detected
        if syntax_hint:
            output_parts.append((f"  [{syntax_hint}]", "text-muted"))

        # Handle collapsed state
        if self._collapsed:
            output_parts.append((f"  ▸ {line_count} lines (collapsed)", "text-muted"))
            return Content.assemble(*output_parts)

        # Truncate long output
        output = self._truncate_output(self._output)

        if has_code:
            output_parts.append(("\n", ""))
            output_parts.append((output, "text-muted"))
        else:
            output_parts.append(("\n", ""))
            output_parts.append((output, "text-muted"))

        return Content.assemble(*output_parts)
