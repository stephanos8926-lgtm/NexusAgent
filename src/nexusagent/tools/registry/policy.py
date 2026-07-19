"""Policy context (context-local) and enforcement for tool access control.

Each agent session gets its own policy context stored in context-local storage.
This allows concurrent agents (parent + sub-agents) to each enforce their own
policy independently, even across async/coroutine boundaries.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable

# Context-local policy context (async-safe, unlike threading.local)
# NOTE: No mutable default — ContextVar doesn't support default_factory.
# The default is None; _get_ctx() creates a fresh dict per context.
_policy_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "policy_context", default=None
)


def _get_ctx() -> dict:
    """Get or create the current context's policy context."""
    # Check RuntimeContext first (if active)
    from nexusagent.runtime.context import current_context

    ctx = current_context()
    if ctx is not None and ctx.policy_context is not None:
        return ctx.policy_context

    local_ctx = _policy_context.get()
    if not isinstance(local_ctx, dict):
        local_ctx = {"role": "full", "policy": "permissive", "unlocked": set()}
        _policy_context.set(local_ctx)
    return local_ctx


def set_policy_context(role: str, policy: str):
    """Set the policy context for the current agent session."""
    ctx = {"role": role, "policy": policy, "unlocked": set()}
    _policy_context.set(ctx)
    # Sync to RuntimeContext if active
    from nexusagent.runtime.context import current_context

    rctx = current_context()
    if rctx is not None:
        rctx.policy_context = ctx


def get_policy_context() -> dict:
    """Get the current policy context."""
    ctx = _get_ctx()
    return {
        "role": ctx.get("role", "full"),
        "policy": ctx.get("policy", "permissive"),
        "unlocked": set(ctx.get("unlocked", set())),
    }


def clear_policy_context():
    """Clear the current policy context."""
    _policy_context.set(None)


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
    from .core import _REGISTRY

    if role == "full":
        return set(_REGISTRY.keys())
    return set(ROLE_MANIFESTS.get(role, ROLE_MANIFESTS["minimal"]))


# ─── Policy Enforcement ────────────────────────────────────────────────


def _is_tool_allowed(tool_name: str) -> tuple[bool, str]:
    """Check if a tool call is allowed under the current policy.

    Returns:
        (allowed: bool, reason: str)
    """
    from .core import _REGISTRY

    ctx = _get_ctx()
    role = ctx["role"]
    policy = ctx["policy"]
    unlocked = ctx["unlocked"]

    manifest = get_manifest(role)

    # Tool not in registry at all
    if tool_name not in _REGISTRY:
        return False, f"Tool '{tool_name}' does not exist."

    # Tool not in this role's manifest
    if tool_name not in manifest and policy in ("restricted", "strict"):
        return False, (
            f"Tool '{tool_name}' is not available for role '{role}' "
            f"(policy: {policy}). Use tool_search() to see available tools."
        )

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


def require_policy(tool_name: str) -> Callable:
    """Decorator helper: enforce policy before executing a tool.

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
    """Check if the current policy allows a tool call.

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
