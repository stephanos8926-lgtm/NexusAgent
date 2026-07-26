"""Policy context (context-local) and enforcement for tool access control.

Modified in Phase 8 to route all checks through the Capability Security Model.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable

# Context-local policy context (async-safe, unlike threading.local)
_policy_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "policy_context", default=None
)


def _get_ctx() -> dict:
    """Get or create the current context's policy context."""
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


# Standard role manifests (preserved for compatibility with existing tests and search)
ROLE_MANIFESTS = {
    "minimal": {
        "tool_search",
    },
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
    "writer": {
        "tool_search",
        "read_file",
        "write_file",
        "edit_file",
        "list_directory",
    },
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
    "full": frozenset(),
}


def get_manifest(role: str) -> set[str]:
    """Get the set of tool names available to a role."""
    from .core import _REGISTRY

    if role == "full":
        return set(_REGISTRY.keys())
    return set(ROLE_MANIFESTS.get(role, ROLE_MANIFESTS["minimal"]))


def _is_tool_allowed(tool_name: str) -> tuple[bool, str]:
    """Check if a tool call is allowed under the current policy."""
    # Route through the capability security router!
    from nexusagent.security.router import router

    return router.check_access(tool_name, context=_get_ctx())


def require_policy(tool_name: str) -> Callable:
    """Decorator helper: enforce policy before executing a tool."""

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
    """Check if the current policy allows a tool call."""
    allowed, reason = _is_tool_allowed(tool_name)
    if not allowed:
        return f"ACCESS DENIED: {reason}"
    return None
