"""Policy-aware tool search with fuzzy matching and use-case discovery."""

from __future__ import annotations

import difflib
from typing import Any

from .types import ToolInfo


def tool_search(
    query: str = "",
    exact: bool = False,
    category: str | None = None,
    max_results: int = 5,
) -> str:
    """Search for tools available to the current agent.

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
    # Delayed imports to avoid circular dependency
    from .policy import _get_ctx, get_manifest
    from .core import _REGISTRY

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
    from .policy import _get_ctx

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
    from .core import _REGISTRY

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
