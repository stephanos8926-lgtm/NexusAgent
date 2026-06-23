"""NexusAgent TUI — public re-exports for backward compatibility.

This compat shim ensures all existing imports from tui.py continue to work:
    from nexusagent.interfaces.tui import NexusApp
    from nexusagent.interfaces.tui import SpinnerLabel, ApprovalModal, ...
    from nexusagent.interfaces.tui import main
"""

from __future__ import annotations

# App class and entry point
from nexusagent.interfaces.tui.app import NexusApp, main

# Formatters
from nexusagent.interfaces.tui.formatters import (
    format_arg_value,
    render_markdown,
    truncate,
)

# Widgets re-exported for backward compat (tests import from tui.py)
from nexusagent.interfaces.tui_widgets import (
    NO_COLOR,
    ApprovalModal,
    Breakpoint,
    ErrorModal,
    SpinnerLabel,
    _sigwinch_handler,
    classify_breakpoint,
    debounce_resize,
    is_no_color,
)

# Message widgets (tests import from tui.py)
from nexusagent.widgets.chat_input import ChatInput
from nexusagent.widgets.messages import (
    AppMessage,
    AssistantMessage,
    ErrorMessage,
    ToolCallMessage,
    UserMessage,
    WelcomeBanner,
)

# Status bar
from nexusagent.widgets.status import StatusBar

__all__ = [
    "NO_COLOR",
    "AppMessage",
    "ApprovalModal",
    "AssistantMessage",
    "Breakpoint",
    "ChatInput",
    "ErrorMessage",
    "ErrorModal",
    "NexusApp",
    "SpinnerLabel",
    "StatusBar",
    "ToolCallMessage",
    "UserMessage",
    "WelcomeBanner",
    "_sigwinch_handler",
    "classify_breakpoint",
    "debounce_resize",
    "format_arg_value",
    "is_no_color",
    "main",
    "render_markdown",
    "truncate",
]
