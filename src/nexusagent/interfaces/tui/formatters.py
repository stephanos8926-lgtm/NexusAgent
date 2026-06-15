"""TUI formatting helpers.

Re-exports from tui_formatters for backward compatibility within the tui package.
"""

from __future__ import annotations

from nexusagent.interfaces.tui_formatters import (  # noqa: F401
    format_arg_value,
    render_markdown,
    truncate,
)
