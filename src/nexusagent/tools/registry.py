"""Compat shim — imports from registry/ subpackage.

All existing ``from nexusagent.tools.registry import ...`` usage continues
to work. New code should import from the subpackage directly.
"""

from nexusagent.tools.registry import *
from nexusagent.tools.registry import (
    ROLE_MANIFESTS,
    ToolInfo,
    auto_correct,
    check_tool_access,
    clear_policy_context,
    get_manifest,
    get_policy_context,
    get_tool_info,
    list_all_tools,
    register_tool,
    require_policy,
    set_policy_context,
    tool_search,
)

__all__ = [
    "ToolInfo",
    "register_tool",
    "get_tool_info",
    "list_all_tools",
    "set_policy_context",
    "get_policy_context",
    "clear_policy_context",
    "ROLE_MANIFESTS",
    "get_manifest",
    "require_policy",
    "check_tool_access",
    "tool_search",
    "auto_correct",
]
