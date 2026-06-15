"""Core tool registry — registration, lookup, auto-correction."""

from __future__ import annotations

import difflib
from collections.abc import Callable
from typing import Any

from .types import ToolInfo

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
    """Look up a tool by name in the global registry.

    Args:
        name: The registered tool name.

    Returns:
        The ToolInfo if found, or None.
    """
    return _REGISTRY.get(name)


def list_all_tools() -> list[ToolInfo]:
    """Return all registered tools.

    Returns:
        List of all ToolInfo entries in the registry.
    """
    return list(_REGISTRY.values())


# ─── Auto-Correction ────────────────────────────────────────────────────


def auto_correct(tool_name: str, kwargs: dict[str, Any] | None = None) -> str:
    """Validate a tool call and return corrections if needed.

    Checks:
    1. Tool exists in registry
    2. Tool is available under current policy
    3. Parameters are correct

    Returns:
        Correction message or validation confirmation.
    """
    # Delayed import to avoid circular dependency with policy module
    from .policy import _is_tool_allowed, get_manifest, _get_ctx

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
