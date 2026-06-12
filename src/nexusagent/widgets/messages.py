"""Compat shim — imports from messages/ subpackage.

All existing ``from nexusagent.widgets.messages import ...`` usage continues
to work. New code should import from ``nexusagent.widgets.messages`` (the
subpackage) directly.
"""

from nexusagent.widgets.messages import *  # noqa: F401,F403
from nexusagent.widgets.messages import (  # noqa: E401
    AppMessage,
    AssistantMessage,
    ErrorMessage,
    ToolCallMessage,
    UserMessage,
    WelcomeBanner,
)

__all__ = [
    "UserMessage",
    "AssistantMessage",
    "ToolCallMessage",
    "AppMessage",
    "ErrorMessage",
    "WelcomeBanner",
]
