"""
Tool registry, policy enforcement, and discovery for NexusAgent.

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

    Usage:
        # User-spawned agent (permissive — auto-unlock on use)
        agent = Agent(role="coder", policy="permissive")

        # Sub-agent (restricted — enforced boundaries, can unlock within role)
        sub = Agent(role="tester", policy="restricted")

        # Sandboxed sub-agent (strict — locked to role manifest)
        sandbox = Agent(role="reviewer", policy="strict")
"""

import difflib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# ─── Tool Info ──────────────────────────────────────────────────────────


@dataclass
class ToolInfo:
    """Metadata for a registered tool."""

    name: str
    func: Callable
    description: str
    parameters: dict[str, str]
    example: str
    category: str
    returns: str = ""
    requires: str = ""  # Optional: tools this tool depends on

    def to_prompt_format(self) -> str:
        params_str = "\n".join(f"    - {k}: {v}" for k, v in self.parameters.items())
        return (
            f"Tool: {self.name}\n"
            f"Category: {self.category}\n"
            f"Description: {self.description}\n"
            f"Parameters:\n{params_str}\n"
            f"Returns: {self.returns}\n"
            f"Example:\n{self.example}"
        )

    def to_compact(self) -> str:
        params = ", ".join(self.parameters.keys())
        return f"- {self.name}({params}): {self.description}"


# ─── Global Tool Registry ───────────────────────────────────────────────

_REGISTRY: dict[str, ToolInfo] = {}


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, str],
    example: str,
    category: str = "general",
    returns: str = "",
    requires: str = "",
) -> Callable:
    """Decorator to register a tool in the global registry."""

    def decorator(func: Callable) -> Callable:
        _REGISTRY[name] = ToolInfo(
            name=name,
            func=func,
            description=description,
            parameters=parameters,
            example=example,
            category=category,
            returns=returns,
            requires=requires,
        )
        return func

    return decorator


def get_tool_info(name: str) -> ToolInfo | None:
    return _REGISTRY.get(name)


def list_all_tools() -> list[ToolInfo]:
    return list(_REGISTRY.values())


# ─── Policy Context (Thread-Local) ──────────────────────────────────────

# Each agent session gets its own policy context stored here.
# This allows concurrent agents (parent + sub-agents) to each
# enforce their own policy independently.
_policy_context = threading.local()


def _get_ctx():
    """Get or create the current thread's policy context."""
    if not hasattr(_policy_context, "role"):
        _policy_context.role = "full"
    if not hasattr(_policy_context, "policy"):
        _policy_context.policy = "permissive"
    if not hasattr(_policy_context, "unlocked"):
        _policy_context.unlocked = set()
    return _policy_context


def set_policy_context(role: str, policy: str):
    """Set the policy context for the current agent session."""
    ctx = _get_ctx()
    ctx.role = role
    ctx.policy = policy
    ctx.unlocked = set()


def get_policy_context() -> dict:
    """Get the current policy context."""
    ctx = _get_ctx()
    return {
        "role": ctx.role,
        "policy": ctx.policy,
        "unlocked": set(ctx.unlocked),
    }


def clear_policy_context():
    """Clear the current policy context."""
    _policy_context.role = "full"
    _policy_context.policy = "permissive"
    _policy_context.unlocked = set()


# ─── Role Manifests ─────────────────────────────────────────────────────

# These define which tools each role can potentially access.
# Policy enforcement determines whether unlock is automatic or restricted.

ROLE_MANIFESTS = {
    # Discovery-only — agent must search and unlock everything
    "minimal": {
        "tool_search",
    },
    # Reader: can read and search, but not modify
    "reader": {
        "tool_search",
        "read_file",
        "read_multiple_files",
        "list_directory",
        "search_code",
        "find_symbol",
        "find_references",
        "search_web",
        "search_local_docs",
    },
    # Writer: can read and write, but no git/test
    "writer": {
        "tool_search",
        "read_file",
        "write_file",
        "edit_file",
        "list_directory",
    },
    # Coder: full dev tooling
    "coder": {
        "tool_search",
        "read_file",
        "read_multiple_files",
        "write_file",
        "write_multiple_files",
        "edit_file",
        "list_directory",
        "run_shell",
        "run_shell_streaming",
        "git_status",
        "git_diff",
        "git_log",
        "git_branch",
        "git_show",
        "git_stash_push",
        "git_stash_pop",
        "git_stash_list",
        "git_commit",
        "git_checkout_branch",
        "search_code",
        "find_symbol",
        "find_references",
        "run_tests",
        "run_single_test",
        "apply_patch",
    },
    # Tester: focused on test execution and test-related edits
    "tester": {
        "tool_search",
        "read_file",
        "list_directory",
        "run_shell",
        "run_tests",
        "run_single_test",
        "search_code",
        "find_symbol",
        "find_references",
        "git_status",
        "git_diff",
        "edit_file",
        "write_file",
    },
    # Reviewer: read, search, git history — no mutations
    "reviewer": {
        "tool_search",
        "read_file",
        "read_multiple_files",
        "list_directory",
        "search_code",
        "find_symbol",
        "find_references",
        "git_status",
        "git_diff",
        "git_log",
        "git_show",
        "run_tests",
    },
    # Debugger: read, edit, test, shell — focused on fixing
    "debugger": {
        "tool_search",
        "read_file",
        "list_directory",
        "run_shell",
        "run_shell_streaming",
        "edit_file",
        "write_file",
        "run_tests",
        "run_single_test",
        "search_code",
        "find_symbol",
        "find_references",
        "git_status",
        "git_diff",
        "git_stash_push",
    },
    # Researcher: search and read, no mutations
    "researcher": {
        "tool_search",
        "read_file",
        "list_directory",
        "search_code",
        "search_web",
        "search_local_docs",
        "find_symbol",
        "find_references",
        "run_shell",
    },
    # Full access
    "full": frozenset(),  # Sentinel — resolved to all registered tools
}


def get_manifest(role: str) -> set[str]:
    """Get the set of tool names available to a role."""
    if role == "full":
        return set(_REGISTRY.keys())
    return set(ROLE_MANIFESTS.get(role, ROLE_MANIFESTS["minimal"]))


# ─── Policy Enforcement ────────────────────────────────────────────────


def _is_tool_allowed(tool_name: str) -> tuple[bool, str]:
    """
    Check if a tool call is allowed under the current policy.

    Returns:
        (allowed: bool, reason: str)
    """
    ctx = _get_ctx()
    role = ctx.role
    policy = ctx.policy
    unlocked = ctx.unlocked

    manifest = get_manifest(role)

    # Tool not in registry at all
    if tool_name not in _REGISTRY:
        return False, f"Tool '{tool_name}' does not exist."

    # Tool not in this role's manifest
    if tool_name not in manifest:
        # In strict/restricted mode, this is a hard deny
        if policy in ("restricted", "strict"):
            return False, (
                f"Tool '{tool_name}' is not available for role '{role}' "
                f"(policy: {policy}). Use tool_search() to see available tools."
            )
        # In permissive mode, the role manifest is just a starting point
        # Allow unlock

    # In permissive mode: auto-unlock on first call
    if policy == "permissive":
        unlocked.add(tool_name)
        return True, ""

    # In restricted mode: allow if in manifest, deny otherwise
    if policy == "restricted":
        if tool_name in manifest or tool_name in unlocked:
            return True, ""
        return False, (
            f"Tool '{tool_name}' is not in your role manifest for '{role}'. "
            f"Use tool_search() to find appropriate tools."
        )

    # In strict mode: only exact manifest, no unlocking
    if policy == "strict":
        if tool_name in manifest:
            return True, ""
        return False, (
            f"Tool '{tool_name}' is not available in strict mode for role '{role}'. "
            f"You are locked to your initial tool set."
        )

    return True, ""


def require_policy(tool_name: str) -> None:
    """
    Decorator helper: enforce policy before executing a tool.

    Usage in tool implementation:
        @require_policy("read_file")
        def read_file(path, offset=1, limit=None):
            ...

    Or call at the top of a tool function:
        def some_tool(...):
            require_policy("some_tool")
            ...
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            allowed, reason = _is_tool_allowed(tool_name)
            if not allowed:
                return f"ACCESS DENIED: {reason}"
            return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


def check_tool_access(tool_name: str) -> str | None:
    """
    Check if the current policy allows a tool call.

    Returns:
        None if allowed, or an error string if denied.

    Usage at the top of tool functions:
        error = check_tool_access("read_file")
        if error:
            return error
    """
    allowed, reason = _is_tool_allowed(tool_name)
    if not allowed:
        return f"ACCESS DENIED: {reason}"
    return None


# ─── Tool Search (Policy-Aware) ─────────────────────────────────────────


def tool_search(
    query: str = "",
    exact: bool = False,
    category: str | None = None,
    max_results: int = 5,
) -> str:
    """
    Search for tools available to the current agent.

    IMPORTANT: Only returns tools that the current policy allows.
    The agent never sees tools outside its scope.

    Args:
        query: Tool name or use case. Empty string lists all available tools.
        exact: If True, match exact tool name only.
        category: Filter by category (fs, git, test, search, shell, web, core).
        max_results: Maximum results to return.

    Returns:
        Formatted search results with descriptions, params, and examples.

    Examples:
        tool_search()                                    # List all available tools
        tool_search("run tests")                         # Search by use case
        tool_search("read_file", exact=True)             # Get specific tool details
        tool_search(category="git")                      # List git tools
    """
    ctx = _get_ctx()
    manifest = get_manifest(ctx.role)

    # In strict mode, also filter out anything not in the original manifest
    if ctx.policy == "strict":
        allowed_names = manifest
    elif ctx.policy == "restricted":
        allowed_names = manifest | ctx.unlocked
    else:  # permissive
        allowed_names = manifest | ctx.unlocked

    # Filter registry to only allowed tools
    available = {name: info for name, info in _REGISTRY.items() if name in allowed_names}

    # No query — list all available tools
    if not query:
        return _format_tool_list(available)

    # Exact name search
    if exact:
        return _exact_search(query, available)

    # If query looks like a tool name (has underscores, no spaces), try name search first
    if "_" in query and " " not in query:
        result = _exact_search(query, available)
        if "Did you mean" in result or "Tool:" in result.split("\n")[0]:
            return result

    # Use case search
    return _use_case_search(query, available, category, max_results)


def _format_tool_list(available: dict[str, ToolInfo]) -> str:
    """Format a tool list grouped by category."""
    if not available:
        return "No tools available."

    by_cat: dict[str, list[ToolInfo]] = {}
    for info in available.values():
        by_cat.setdefault(info.category, []).append(info)

    output = [f"# Available Tools ({len(available)} total)\n"]
    for cat in sorted(by_cat.keys()):
        output.append(f"\n## {cat.upper()}")
        for t in sorted(by_cat[cat], key=lambda x: x.name):
            output.append(t.to_compact())

    return "\n".join(output)


def _exact_search(query: str, available: dict[str, ToolInfo]) -> str:
    """Search by exact tool name within available tools."""
    # Direct match
    if query in available:
        return available[query].to_prompt_format()

    # Hyphen-to-underscore normalization
    normalized = query.replace("-", "_")
    if normalized in available:
        return available[normalized].to_prompt_format()

    # Fuzzy match within available tools
    for cutoff in [0.5, 0.4, 0.3, 0.2]:
        close = difflib.get_close_matches(query, available.keys(), n=3, cutoff=cutoff)
        if close:
            suggestions = []
            for name in close:
                t = available[name]
                suggestions.append(f"  - {name}: {t.description}")
            return (
                f"Tool '{query}' not found. Did you mean:\n"
                + "\n".join(suggestions)
                + f'\n\nUse tool_search("{close[0]}", exact=True) for full details.'
            )

    # Not found in available tools — check if it exists but is out of scope
    if query in _REGISTRY:
        ctx = _get_ctx()
        return (
            f"Tool '{query}' exists but is not available for your role '{ctx.role}' "
            f"(policy: {ctx.policy}). Use tool_search() to see your available tools."
        )

    return f"Tool '{query}' not found. Use tool_search() to list available tools."


def _use_case_search(
    query: str,
    available: dict[str, ToolInfo],
    category: str | None,
    max_results: int,
) -> str:
    """Search by use case within available tools."""
    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored = []
    for name, info in available.items():
        if category and category != info.category:
            continue

        score = 0
        desc_lower = info.description.lower()
        name_lower = name.lower()
        cat_lower = info.category.lower()

        for word in query_words:
            if word in desc_lower:
                score += 3
            if word in name_lower:
                score += 2
            if word in cat_lower:
                score += 1

        if query_lower in desc_lower:
            score += 5
        if query_lower in name_lower:
            score += 4

        if score > 0:
            scored.append((score, info))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [info for _, info in scored[:max_results]]

    if not results:
        return f"No tools found for: '{query}'. Use tool_search() to list available tools."

    if len(results) == 1:
        return results[0].to_prompt_format()

    output = [f"Found {len(results)} tools for '{query}':\n"]
    for info in results:
        output.append(info.to_prompt_format())
        output.append("")

    return "\n".join(output)


# ─── Auto-Correction ────────────────────────────────────────────────────


def auto_correct(tool_name: str, kwargs: dict[str, Any] = None) -> str:
    """
    Validate a tool call and return corrections if needed.

    Checks:
    1. Tool exists in registry
    2. Tool is available under current policy
    3. Parameters are correct

    Returns:
        Correction message or validation confirmation.
    """
    # Check policy first
    allowed, reason = _is_tool_allowed(tool_name)
    if not allowed:
        return f"ACCESS DENIED: {reason}"

    if tool_name not in _REGISTRY:
        # Fuzzy match within available tools
        ctx = _get_ctx()
        manifest = get_manifest(ctx.role)
        if ctx.policy == "strict":
            available = {n: _REGISTRY[n] for n in manifest if n in _REGISTRY}
        else:
            available = {n: _REGISTRY[n] for n in (manifest | ctx.unlocked) if n in _REGISTRY}

        for cutoff in [0.5, 0.4, 0.3]:
            close = difflib.get_close_matches(tool_name, available.keys(), n=3, cutoff=cutoff)
            if close:
                suggestions = [f"  - {n}: {available[n].description}" for n in close]
                return f"Tool '{tool_name}' not found. Did you mean:\n" + "\n".join(suggestions)
        return f"Tool '{tool_name}' not found. Use tool_search() to list available tools."

    info = _REGISTRY[tool_name]

    # Validate parameters
    if kwargs:
        valid_params = set(info.parameters.keys())
        provided_params = set(kwargs.keys())
        unknown = provided_params - valid_params

        if unknown:
            corrections = []
            for bad in unknown:
                close = difflib.get_close_matches(bad, valid_params, n=1, cutoff=0.5)
                if close:
                    corrections.append(f"  - '{bad}' → did you mean '{close[0]}'?")
                else:
                    corrections.append(f"  - '{bad}' is not a valid parameter")
            params_list = ", ".join(sorted(valid_params))
            return (
                f"Invalid parameter(s) for '{tool_name}':\n"
                + "".join(corrections)
                + f"\n\nValid parameters: {params_list}\n"
                f"Example: {info.example}"
            )

    return f"Tool '{tool_name}' is valid. {info.description}\nExample: {info.example}"
