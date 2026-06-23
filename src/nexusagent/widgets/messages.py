"""Compat shim — imports from messages/ subpackage.

All existing ``from nexusagent.widgets.messages import ...`` usage continues
to work. New code should import from ``nexusagent.widgets.messages`` (the
subpackage) directly.
"""

from nexusagent.widgets.messages import *
from nexusagent.widgets.messages import (
    AppMessage,
    AssistantMessage,
    ErrorMessage,
    ToolCallMessage,
    UserMessage,
    WelcomeBanner,
)

__all__ = [
    "AppMessage",
    "AssistantMessage",
    "ErrorMessage",
    "ToolCallMessage",
    "UserMessage",
    "WelcomeBanner",
]
