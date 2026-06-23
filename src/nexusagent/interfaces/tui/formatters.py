"""TUI formatting helpers.

Re-exports from tui_formatters for backward compatibility within the tui package.
"""

from __future__ import annotations

from nexusagent.interfaces.tui_formatters import (
    format_arg_value,
    render_markdown,
    truncate,
)

__all__ = ["format_arg_value", "render_markdown", "truncate"]
