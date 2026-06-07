"""
Tool discovery and auto-correction middleware for NexusAgent.

This module provides:
1. tool_search() — search the registry by name or use case
2. unlock_tool() — unlock a tool for the current session
3. ToolCallMiddleware — auto-corrects wrong tool names and parameters

The middleware intercepts tool calls before execution and:
- If tool name is wrong → returns "Did you mean X?" instead of failing
- If params are wrong → returns "X takes params Y, Z. Example: ..."
- If tool is not in manifest → returns "Tool not available. Use tool_search() to find alternatives."
"""

import difflib
from typing import Any, Optional

from nexusagent.tools.registry import (
    _REGISTRY,
    _unlocked_tools,
    get_effective_manifest,
    ToolInfo,
)


def tool_search(
    query: str = "",
    exact: bool = False,
    category: Optional[str] = None,
    max_results: int = 5,
) -> str:
    """
    Search the tool registry by name or use case.
    
    Args:
        query: Tool name or use case description. Empty string lists all tools.
        exact: If True, match exact tool name only
        category: Optional category filter (fs, git, test, search, shell, web)
        max_results: Maximum results to return
    
    Returns:
        Formatted search results with tool descriptions, parameters, and examples
    
    Examples:
        tool_search("read file")           # Search by use case
        tool_search("read_file", exact=True)  # Get specific tool info
        tool_search(category="git")        # List all git tools
        tool_search()                      # List all tools
    """
    if not query and not category:
        # List all tools
        return _list_all_tools()
    
    if exact:
        return _exact_search(query)
    
    # If query looks like a tool name (single word, has underscores, no spaces),
    # try exact/fuzzy name search first before use case search
    if "_" in query and " " not in query:
        result = _exact_search(query)
        # _exact_search returns a "Did you mean" suggestion if fuzzy match found
        if "Did you mean" in result:
            return result
    
    return _fuzzy_search(query, category, max_results)


def _exact_search(query: str) -> str:
    """Search by exact tool name."""
    # Try direct match
    if query in _REGISTRY:
        return _REGISTRY[query].to_prompt_format()
    
    # Try with hyphen-to-underscore conversion
    normalized = query.replace("-", "_")
    if normalized in _REGISTRY:
        return _REGISTRY[normalized].to_prompt_format()
    
    # Fuzzy match for typos — try progressively lower cutoffs
    for cutoff in [0.4, 0.3, 0.2]:
        close = difflib.get_close_matches(query, _REGISTRY.keys(), n=3, cutoff=cutoff)
        if close:
            suggestions = []
            for name in close:
                t = _REGISTRY[name]
                suggestions.append(f"  - {name}: {t.description}")
            return (
                f"Tool '{query}' not found. Did you mean:\n"
                + "\n".join(suggestions)
                + f"\n\nUse tool_search(\"{close[0]}\", exact=True) for full details."
            )
    
    return f"Tool '{query}' not found. Use tool_search() to list all available tools."


def _fuzzy_search(query: str, category: Optional[str], max_results: int) -> str:
    """Search by use case / description."""
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    scored = []
    for name, info in _REGISTRY.items():
        if category and category != info.category:
            continue
        
        score = 0
        desc_lower = info.description.lower()
        name_lower = name.lower()
        cat_lower = info.category.lower()
        
        # Word matches
        for word in query_words:
            if word in desc_lower:
                score += 3
            if word in name_lower:
                score += 2
            if word in cat_lower:
                score += 1
        
        # Substring match
        if query_lower in desc_lower:
            score += 5
        if query_lower in name_lower:
            score += 4
        
        if score > 0:
            scored.append((score, info))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [info for _, info in scored[:max_results]]
    
    if not results:
        return f"No tools found for: '{query}'. Use tool_search() to list all tools."
    
    if len(results) == 1:
        return results[0].to_prompt_format()
    
    output = [f"Found {len(results)} tools for '{query}':\n"]
    for info in results:
        output.append(info.to_prompt_format())
        output.append("")
    
    return "\n".join(output)


def _list_all_tools() -> str:
    """List all registered tools grouped by category."""
    by_cat: dict[str, list[ToolInfo]] = {}
    for info in _REGISTRY.values():
        by_cat.setdefault(info.category, []).append(info)
    
    output = ["# All Registered Tools\n"]
    for cat in sorted(by_cat.keys()):
        output.append(f"\n## {cat.upper()}")
        for t in sorted(by_cat[cat], key=lambda x: x.name):
            params = ", ".join(t.parameters.keys())
            output.append(f"  - {t.name}({params}): {t.description}")
    
    return "\n".join(output)


def unlock_tool(tool_name: str) -> str:
    """
    Unlock a tool for the current agent session.
    
    When an agent running with a minimal manifest needs a new tool,
    it calls tool_search() to find it, then unlock_tool() to add it
    to its active manifest.
    
    Args:
        tool_name: Name of the tool to unlock
    
    Returns:
        Success message with tool info, or error if tool doesn't exist
    
    Example:
        unlock_tool("git_commit")
    """
    if tool_name not in _REGISTRY:
        close = difflib.get_close_matches(tool_name, _REGISTRY.keys(), n=3, cutoff=0.4)
        if close:
            return f"Tool '{tool_name}' not found. Did you mean: {', '.join(close)}?"
        return f"Tool '{tool_name}' not found. Use tool_search() to list all tools."
    
    _unlocked_tools.add(tool_name)
    info = _REGISTRY[tool_name]
    return f"Unlocked '{tool_name}': {info.description}\nExample: {info.example}"


def validate_tool_call(tool_name: str, kwargs: dict[str, Any] = None) -> Optional[str]:
    """
    Validate a tool call and return correction instructions if invalid.
    
    Args:
        tool_name: Name of the tool being called
        kwargs: Keyword arguments being passed
    
    Returns:
        None if valid, or a correction string if invalid.
    """
    if tool_name not in _REGISTRY:
        close = difflib.get_close_matches(tool_name, _REGISTRY.keys(), n=3, cutoff=0.4)
        if close:
            best = close[0]
            info = _REGISTRY[best]
            return (
                f"Tool '{tool_name}' does not exist. Did you mean '{best}'?\n"
                f"{best}: {info.description}\n"
                f"Example: {info.example}"
            )
        return f"Tool '{tool_name}' does not exist. Use tool_search() to see available tools."
    
    if kwargs:
        info = _REGISTRY[tool_name]
        valid_params = set(info.parameters.keys())
        provided_params = set(kwargs.keys())
        unknown = provided_params - valid_params
        
        if unknown:
            corrections = []
            for bad_param in unknown:
                close_params = difflib.get_close_matches(bad_param, valid_params, n=1, cutoff=0.5)
                if close_params:
                    corrections.append(f"  - '{bad_param}' → did you mean '{close_params[0]}'?")
                else:
                    corrections.append(f"  - '{bad_param}' is not a valid parameter")
            
            params_list = ", ".join(sorted(valid_params))
            return (
                f"Invalid parameter(s) for '{tool_name}':\n"
                + "\n".join(corrections)
                + f"\n\nValid parameters: {params_list}\n"
                f"Example: {info.example}"
            )
    
    return None  # Valid


def auto_correct(tool_name: str, kwargs: dict[str, Any] = None) -> str:
    """
    Auto-correct a tool call. Main entry point for the auto-correction layer.
    
    Called automatically when a tool call fails, or proactively by the agent.
    
    Args:
        tool_name: Name of the tool
        kwargs: Optional keyword arguments to validate
    
    Returns:
        Correction message or confirmation.
    """
    if kwargs:
        result = validate_tool_call(tool_name, kwargs)
        if result:
            return result
    
    if tool_name not in _REGISTRY:
        for cutoff in [0.4, 0.3, 0.2]:
            close = difflib.get_close_matches(tool_name, _REGISTRY.keys(), n=3, cutoff=cutoff)
            if close:
                suggestions = []
                for name in close:
                    t = _REGISTRY[name]
                    suggestions.append(f"  - {name}: {t.description}")
                return f"Tool '{tool_name}' not found. Did you mean:\n" + "\n".join(suggestions)
        return f"Tool '{tool_name}' not found. Use tool_search() to list all tools."
    
    info = _REGISTRY[tool_name]
    return f"Tool '{tool_name}' is valid. {info.description}\nExample: {info.example}"


def get_available_tools(base_scope: str = "minimal") -> str:
    """
    Get a formatted list of tools available to the current agent.
    Includes base manifest + unlocked tools.
    
    Args:
        base_scope: Base manifest scope (minimal, coder, tester, etc.)
    
    Returns:
        Formatted tool listing
    """
    manifest = get_effective_manifest(base_scope)
    
    output = [f"# Available Tools ({len(manifest)} total)\n"]
    
    # Group by category
    by_cat: dict[str, list[str]] = {}
    for name, info in sorted(manifest.items()):
        by_cat.setdefault(info.category, []).append(name)
    
    for cat in sorted(by_cat.keys()):
        output.append(f"## {cat.upper()}")
        for name in by_cat[cat]:
            info = manifest[name]
            params = ", ".join(info.parameters.keys())
            output.append(f"  - {name}({params}): {info.description}")
        output.append("")
    
    if base_scope == "minimal":
        output.append(
            "\nNOTE: Running with minimal tool set. "
            "Use tool_search(\"what you want to do\") to discover and unlock more tools."
        )
    
    return "\n".join(output)
