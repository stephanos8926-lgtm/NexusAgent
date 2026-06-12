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

from .types import ToolInfo
from .core import _REGISTRY, register_tool, get_tool_info, list_all_tools, auto_correct
from .policy import (
    set_policy_context,
    get_policy_context,
    clear_policy_context,
    get_manifest,
    require_policy,
    check_tool_access,
    ROLE_MANIFESTS,
)
from .search import tool_search

__all__ = [
    # Types
    "ToolInfo",
    # Registration
    "register_tool",
    "get_tool_info",
    "list_all_tools",
    "_REGISTRY",
    # Policy context
    "set_policy_context",
    "get_policy_context",
    "clear_policy_context",
    # Roles
    "ROLE_MANIFESTS",
    "get_manifest",
    # Policy enforcement
    "require_policy",
    "check_tool_access",
    # Search & correction
    "tool_search",
    "auto_correct",
]
