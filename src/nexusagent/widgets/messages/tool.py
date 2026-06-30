"""Tool call message widget — collapsible output, syntax hints, status indicators."""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from rich.console import Group
from rich.syntax import Syntax
from rich.text import Text
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

    _STATUS_ICONS: ClassVar[dict[str, str]] = {
        STATUS_RUNNING: "⚙",
        STATUS_SUCCESS: "✔",
        STATUS_FAILED: "✘",
    }

    _STATUS_STYLES: ClassVar[dict[str, str]] = {
        STATUS_RUNNING: "bold warning",
        STATUS_SUCCESS: "bold success",
        STATUS_FAILED: "bold error",
    }

    # Plain Rich color names (not Textual $theme-variables). Required when a
    # Content object is nested inside a rich.console.Group alongside a
    # Syntax renderable — Content's CSS-variable style names ("text-muted",
    # "bold warning", etc.) only resolve when Content is itself the
    # top-level value returned from a widget's render(); nested inside a
    # plain Rich renderable they raise AttributeError at paint time.
    _STATUS_RICH_STYLES: ClassVar[dict[str, str]] = {
        STATUS_RUNNING: "bold yellow",
        STATUS_SUCCESS: "bold green",
        STATUS_FAILED: "bold red",
    }

    _BORDER_COLORS: ClassVar[dict[str, str]] = {
        STATUS_RUNNING: "yellow",
        STATUS_SUCCESS: "green",
        STATUS_FAILED: "red",
    }

    def __init__(
        self,
        tool: str,
        args: str | dict,
        output: str = "",
        status: str = "running",
        **kwargs: Any,
    ) -> None:
        """Initialize the tool call message widget."""
        super().__init__(**kwargs)
        self._tool = tool
        self._args_raw = args
        self._output = output
        self._status = status
        self._collapsed = self._should_collapse(output)
        self.styles.border_left = ("wide", self._BORDER_COLORS.get(status, "yellow"))

    def _should_collapse(self, output: str) -> bool:
        """Determine if output should be collapsed by default."""
        if not output:
            return False
        line_count = len(_NEWLINE_RE.findall(output))
        return line_count >= _COLLAPSE_LINE_THRESHOLD or len(output) >= _COLLAPSE_CHAR_THRESHOLD

    def _format_args(self) -> str:
        """Pretty-print args for display — human-readable, not raw JSON."""
        # Special formatting for memory tools — show description
        if self._tool.startswith("memory_") and isinstance(self._args_raw, dict):
            desc = self._args_raw.get("description") or self._args_raw.get("content", "")
            if desc:
                return desc[:60] + ("..." if len(desc) > 60 else "")
            return self._tool
        # Handle dict args — show as key=value pairs
        if isinstance(self._args_raw, dict):
            parts = []
            for k, v in self._args_raw.items():
                v_str = str(v)
                if len(v_str) > 80:
                    v_str = v_str[:77] + "..."
                parts.append(f"{k}={v_str}")
            return ", ".join(parts)
        # Handle string args — try to parse as JSON for pretty-printing
        stripped = str(self._args_raw).strip()
        if not stripped:
            return ""
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    parts = []
                    for k, v in parsed.items():
                        v_str = str(v)
                        if len(v_str) > 80:
                            v_str = v_str[:77] + "..."
                        parts.append(f"{k}={v_str}")
                    return ", ".join(parts)
            except (json.JSONDecodeError, ValueError):
                pass
        # Plain string — return as-is
        if len(stripped) > 120:
            return stripped[:117] + "..."
        return stripped

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
        self.styles.border_left = ("wide", self._BORDER_COLORS.get(status, "yellow"))
        self.refresh()

    def update_output(self, output: str) -> None:
        """Update the output and refresh the display."""
        self._output = output
        self._collapsed = self._should_collapse(output)
        self.refresh()

    def toggle_collapse(self) -> None:
        """Toggle the collapsed state of the output."""
        self._collapsed = not self._collapsed
        # Force layout recalculation by clearing cached height
        self.styles.height = None
        self.refresh()
        # Schedule a layout refresh on the parent to reflow
        if self.parent is not None:
            self.parent.refresh()

    def on_click(self) -> None:
        """Click anywhere on the widget to toggle output collapse."""
        if self._output:
            self.toggle_collapse()

    def _build_output_renderable(self, output: str):
        """Build a real renderable for tool output instead of a raw text dump.

        Tries, in order: pretty-printed + highlighted JSON, the first fenced
        code block syntax-highlighted (with any surrounding text kept plain),
        then falls back to plain text.
        """
        stripped = output.strip()

        # JSON output: pretty-print and syntax-highlight rather than dumping
        # the raw (often single-line, escaped) string.
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                parsed = None
            if parsed is not None:
                pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
                return Syntax(pretty, "json", theme="ansi_dark", word_wrap=True, background_color="default")

        # Fenced code block: highlight just the code, keep surrounding text plain.
        match = _CODE_BLOCK_LANG_RE.search(output)
        if match:
            lang = match.group(1) or "text"
            code_match = re.search(r"```\w*\n([\s\S]*?)```", output)
            code = code_match.group(1) if code_match else output
            return Syntax(
                code.rstrip("\n"), lang, theme="ansi_dark", word_wrap=True, background_color="default"
            )

        return Text(output)

    def render(self):
        """Render the tool call with status icon, args, and collapsible output.

        Returns:
            Rich renderable (Group for expanded, Content for collapsed/header-only).
        """
        icon = self._STATUS_ICONS.get(self._status, "⚙")
        style = self._STATUS_STYLES.get(self._status, "bold warning")

        formatted_args = self._format_args()
        header = f"{icon} {self._tool}({formatted_args})"

        if not self._output:
            return Content.assemble((header, style))

        # Build output display
        syntax_hint = self._detect_syntax_hint()
        line_count = self._count_lines(self._output)

        header_parts = [(header, style)]

        # Add syntax hint if detected
        if syntax_hint:
            header_parts.append((f"  [{syntax_hint}]", "text-muted"))

        # Handle collapsed state — show hint so user knows it's clickable
        if self._collapsed:
            header_parts.append(
                (
                    f"  ▸ {line_count} line{'s' if line_count != 1 else ''} · click to expand",
                    "text-muted",
                )
            )
            return Content.assemble(*header_parts)

        # Expanded: truncate only very large outputs (10k chars)
        output = (
            self._output
            if len(self._output) <= 10000
            else (
                self._output[:10000] + f"\n[truncated — {len(self._output) - 10000:,} more chars]"
            )
        )

        header_text = Text()
        header_text.append(f"{icon} {self._tool}({formatted_args})", style=self._STATUS_RICH_STYLES.get(self._status, "bold yellow"))
        if syntax_hint:
            header_text.append(f"  [{syntax_hint}]", style="dim")

        body = self._build_output_renderable(output)
        footer = Text("  ▾ click to collapse", style="dim italic")
        return Group(header_text, body, footer)
