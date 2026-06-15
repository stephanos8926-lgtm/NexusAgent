"""NexusAgent TUI widgets package.

Contains reusable UI components:
- messages.py — UserMessage, AssistantMessage, ToolCallMessage, AppMessage, ErrorMessage, WelcomeBanner
- status.py — StatusBar, ModelLabel
- chat_input.py — ChatInput
- theme.py — Semantic color definitions

Usage:
    from nexusagent.widgets.messages import UserMessage, AssistantMessage
    from nexusagent.widgets.status import StatusBar
    from nexusagent.widgets.chat_input import ChatInput
    from nexusagent.widgets.theme import ThemeColors, get_css_variable_defaults
"""

__all__ = [
    "AppMessage",
    "AssistantMessage",
    # Input
    "ChatInput",
    "ErrorMessage",
    "ModelLabel",
    # Status
    "StatusBar",
    # Theme
    "ThemeColors",
    "ToolCallMessage",
    # Messages
    "UserMessage",
    "WelcomeBanner",
    "get_css_variable_defaults",
]
