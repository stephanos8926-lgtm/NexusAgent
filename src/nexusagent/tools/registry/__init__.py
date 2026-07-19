"""Tool registry, policy enforcement, and discovery for NexusAgent.

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │                    POLICY LEVELS                         │
    │                                                         │
    │  permissive (default for user-spawned agents)           │
    │    - tool_search shows ONLY tools in policy scope        │
    │    - Any tool in scope auto-unlocks on first call        │
    │    - No explicit unlock needed                          │
    │                                                         │
    │  restricted (sub-agents spawned by other agents)        │
    │    - tool_search shows ONLY tools in policy scope        │
    │    - Tools enforce scope at call time                   │
    │    - Calls outside scope are denied with explanation    │
    │                                                         │
    │  strict (sandboxed sub-agents)                          │
    │    - Same as restricted, but NO unlock possible         │
    │    - Agent is locked to its initial manifest forever    │
    └─────────────────────────────────────────────────────────┘

    Defense in depth:
        1. Discovery: tool_search() only shows in-scope tools
        2. Execution: each tool checks policy before running
        3. Auto-correction: wrong name/params get helpful hints
"""

from .core import ToolRegistry, auto_correct, get_tool_info, list_all_tools, register_tool, registry
from .policy import (
    ROLE_MANIFESTS,
    check_tool_access,
    clear_policy_context,
    get_manifest,
    get_policy_context,
    require_policy,
    set_policy_context,
)
from .search import tool_search
from .types import ToolInfo

__all__ = [
    "ROLE_MANIFESTS",
    "ToolInfo",
    "ToolRegistry",
    "auto_correct",
    "check_tool_access",
    "clear_policy_context",
    "get_manifest",
    "get_policy_context",
    "get_tool_info",
    "list_all_tools",
    "register_tool",
    "registry",
    "require_policy",
    "set_policy_context",
    "tool_search",
]
