"""NexusAgent Terminal User Interface (TUI)  compat shim.

This file is a backward-compatible re-export of the tui/ subpackage.
New code should import directly from nexusagent.interfaces.tui app.
"""

# Re-export everything from the tui subpackage explicitly
from nexusagent.interfaces.tui import (  # noqa: F401
    NO_COLOR,
    AppMessage,
    ApprovalModal,
    AssistantMessage,
    Breakpoint,
    ChatInput,
    ErrorMessage,
    ErrorModal,
    NexusApp,
    SpinnerLabel,
    StatusBar,
    ToolCallMessage,
    UserMessage,
    WelcomeBanner,
    _sigwinch_handler,
    classify_breakpoint,
    debounce_resize,
    format_arg_value,
    is_no_color,
    main,
    render_markdown,
    truncate,
)

#  Formatters 
#  Message widgets (needed by tests and external imports) 
