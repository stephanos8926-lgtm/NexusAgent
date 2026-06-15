"""NexusAgent Terminal User Interface (TUI) — compat shim.

This file is a backward-compatible re-export of the tui/ subpackage.
New code should import directly from nexusagent.interfaces.tui app.
"""

# Re-export everything from the tui subpackage
from nexusagent.interfaces.tui import *  # noqa: F401, F402

# ── Message widgets (needed by tests and external imports) ──
from nexusagent.widgets.chat_input import ChatInput  # noqa: F401
from nexusagent.widgets.messages import (  # noqa: F401
    AppMessage,
    AssistantMessage,
    ErrorMessage,
    ToolCallMessage,
    UserMessage,
    WelcomeBanner,
)
from nexusagent.widgets.status import StatusBar  # noqa: F401

# ── Formatters ──
from nexusagent.interfaces.tui_formatters import (  # noqa: F401
    format_arg_value,
    render_markdown,
    truncate,
)
