"""NexusAgent TUI — public re-exports for backward compatibility.

This compat shim ensures all existing imports from tui.py continue to work:
    from nexusagent.interfaces.tui import NexusApp
    from nexusagent.interfaces.tui import SpinnerLabel, ApprovalModal, ...
    from nexusagent.interfaces.tui import main
"""

from __future__ import annotations

# App class and entry point
from nexusagent.interfaces.tui.app import NexusApp, main  # noqa: F401

# Widgets re-exported for backward compat (tests import from tui.py)
from nexusagent.interfaces.tui_widgets import (  # noqa: F401
    ApprovalModal,
    Breakpoint,
    ErrorModal,
    SpinnerLabel,
    _sigwinch_handler,
    classify_breakpoint,
    debounce_resize,
    is_no_color,
    NO_COLOR,
)

# Message widgets (tests import from tui.py)
from nexusagent.widgets.chat_input import ChatInput  # noqa: F401
from nexusagent.widgets.messages import (  # noqa: F401
    AppMessage,
    AssistantMessage,
    ErrorMessage,
    ToolCallMessage,
    UserMessage,
    WelcomeBanner,
)

# Status bar
from nexusagent.widgets.status import StatusBar  # noqa: F401

# Formatters
from nexusagent.interfaces.tui_formatters import (  # noqa: F401
    format_arg_value,
    render_markdown,
    truncate,
)
