"""
Tool registry and discovery system for NexusAgent.

Provides:
- Central registry of all tools with metadata (description, params, examples)
- tool_search: find tools by name or use case
- tool_manifest: per-agent tool access control (full, minimal, custom)
- Auto-correction layer: fuzzy name matching, param validation, example injection
- Progressive discovery: start lean, unlock tools on demand

Usage:
    # Minimal agent (default)
    manifest = get_tool_manifest("minimal")  # Returns tool_search + core tools only
    
    # Full access
    manifest = get_tool_manifest("full")  # All registered tools
    
    # Sub-agent with custom scope
    manifest = get_tool_manifest("coder")  # Only coding-related tools
    
    # Search for tools
    results = tool_search("run tests")  # By use case
    results = tool_search("git_commit", exact=True)  # By exact name
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import difflib
import fnmatch


@dataclass
class ToolInfo:
    """Metadata for a registered tool."""
    name: str
    func: Callable
    description: str
    parameters: dict[str, str]  # param_name -> description
    example: str
    category: str  # "core", "git", "test", "search", "shell", "fs", etc.
    returns: str = ""
    
    def to_prompt_format(self) -> str:
        """Format tool info for injection into system prompt or error messages."""
        params_str = "\n".join(f"  - {k}: {v}" for k, v in self.parameters.items())
        return (
            f"Tool: {self.name}\n"
            f"Category: {self.category}\n"
            f"Description: {self.description}\n"
            f"Parameters:\n{params_str}\n"
            f"Returns: {self.returns}\n"
            f"Example:\n{self.example}"
        )
    
    def to_compact(self) -> str:
        """Compact format for tool listing."""
        params = ", ".join(self.parameters.keys())
        return f"- {self.name}({params}): {self.description}"


# ─── Tool Registry ──────────────────────────────────────────────────────

_REGISTRY: dict[str, ToolInfo] = {}


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, str],
    example: str,
    category: str = "general",
    returns: str = "",
) -> Callable:
    """
    Decorator to register a tool in the registry.
    
    Usage:
        @register_tool(
            name="read_file",
            description="Read file contents with optional line-range selection",
            parameters={"path": "File path", "offset": "Start line (1-indexed)", "limit": "Max lines"},
            example='read_file("src/main.py", offset=10, limit=20)',
            category="fs",
            returns="File content as string",
        )
        def read_file(path, offset=1, limit=None):
            ...
    """
    def decorator(func: Callable) -> Callable:
        _REGISTRY[name] = ToolInfo(
            name=name,
            func=func,
            description=description,
            parameters=parameters,
            example=example,
            category=category,
            returns=returns,
        )
        return func
    return decorator


def get_tool_info(name: str) -> Optional[ToolInfo]:
    """Get tool info by exact name."""
    return _REGISTRY.get(name)


def list_all_tools() -> list[ToolInfo]:
    """List all registered tools."""
    return list(_REGISTRY.values())


# ─── Tool Discovery ─────────────────────────────────────────────────────

def tool_search(
    query: str,
    exact: bool = False,
    category: Optional[str] = None,
    max_results: int = 5,
) -> str:
    """
    Search the tool registry by name or use case.
    
    Args:
        query: Tool name or use case description
        exact: If True, match exact tool name only
        category: Optional category filter
        max_results: Maximum results to return
    
    Returns:
        Formatted search results with tool descriptions and examples
    """
    results = []
    
    if exact:
        # Exact name match
        if query in _REGISTRY:
            results.append(_REGISTRY[query])
        elif query.replace("-", "_") in _REGISTRY:
            results.append(_REGISTRY[query.replace("-", "_")])
        else:
            # Fuzzy match for "did you mean?"
            close = difflib.get_close_matches(query, _REGISTRY.keys(), n=3, cutoff=0.5)
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
            return f"Tool '{query}' not found. Use tool_search(\"\") to list all tools."
    else:
        # Use case search: match against description + name + category
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored = []
        for name, info in _REGISTRY.items():
            score = 0
            desc_lower = info.description.lower()
            name_lower = name.lower()
            cat_lower = info.category.lower()
            
            # Exact word matches in description
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
            
            # Category filter
            if category and category != info.category:
                continue
            
            if score > 0:
                scored.append((score, info))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [info for _, info in scored[:max_results]]
    
    if not results:
        return f"No tools found for: '{query}'. Use tool_search('') to list all tools."
    
    # Format results
    if len(results) == 1:
        return results[0].to_prompt_format()
    
    output = [f"Found {len(results)} tools for '{query}':\n"]
    for info in results:
        output.append(info.to_prompt_format())
        output.append("")
    
    return "\n".join(output)


def list_tools_by_category(category: Optional[str] = None) -> str:
    """
    List all tools, optionally filtered by category.
    
    Args:
        category: Filter by category (None = all)
    
    Returns:
        Formatted tool listing
    """
    tools = list_all_tools()
    if category:
        tools = [t for t in tools if t.category == category]
    
    if not tools:
        return f"No tools found for category: '{category}'"
    
    # Group by category
    by_cat: dict[str, list[ToolInfo]] = {}
    for t in tools:
        by_cat.setdefault(t.category, []).append(t)
    
    output = []
    for cat in sorted(by_cat.keys()):
        output.append(f"\n## {cat.upper()}")
        for t in sorted(by_cat[cat], key=lambda x: x.name):
            output.append(t.to_compact())
    
    return "\n".join(output).strip()


# ─── Tool Manifest (Per-Agent Access Control) ──────────────────────────

# Minimal tool set — available to all agents by default
MINIMAL_TOOL_SET = frozenset({
    "tool_search",
    "run_tests",
})


# Category-based tool groups for sub-agents
CATEGORY_ACCESS = {
    "minimal": set(),  # Only tool_search + run_tests
    "fs": {"fs"},
    "git": {"git"},
    "test": {"test"},
    "search": {"search"},
    "shell": {"shell"},
    "web": {"web"},
}

# Role-based tool manifests for common sub-agent types
ROLE_MANIFESTS = {
    "minimal": MINIMAL_TOOL_SET,
    "reader": MINIMAL_TOOL_SET | {"read_file", "read_multiple_files", "list_directory", "search_code", "find_symbol", "find_references"},
    "writer": MINIMAL_TOOL_SET | {"read_file", "write_file", "edit_file", "list_directory"},
    "coder": MINIMAL_TOOL_SET | {
        "read_file", "read_multiple_files", "write_file", "edit_file", "list_directory",
        "run_shell", "run_shell_streaming",
        "git_status", "git_diff", "git_log", "git_stash_push",
        "search_code", "find_symbol", "find_references",
        "run_tests",
    },
    "tester": MINIMAL_TOOL_SET | {
        "read_file", "list_directory", "run_shell",
        "run_tests", "run_single_test",
        "search_code", "find_symbol", "find_references",
        "git_status", "git_diff",
        "edit_file", "write_file",
    },
    "reviewer": MINIMAL_TOOL_SET | {
        "read_file", "read_multiple_files", "list_directory",
        "search_code", "find_symbol", "find_references",
        "git_status", "git_diff", "git_log", "git_show",
        "run_tests",
    },
    "debugger": MINIMAL_TOOL_SET | {
        "read_file", "list_directory", "run_shell", "run_shell_streaming",
        "edit_file", "write_file",
        "run_tests", "run_single_test",
        "search_code", "find_symbol", "find_references",
        "git_status", "git_diff", "git_stash_push",
    },
    "researcher": MINIMAL_TOOL_SET | {
        "read_file", "list_directory", "search_code",
        "search_web", "search_local_docs",
        "find_symbol", "find_references",
        "run_shell",
    },
    "full": frozenset(),  # All tools — populated by get_tool_manifest
}


def get_tool_manifest(scope: str | set[str] | frozenset[str] = "minimal") -> dict[str, ToolInfo]:
    """
    Get a filtered tool manifest for an agent.
    
    Args:
        scope: One of:
            - "minimal": Only tool_search + run_tests (must discover others)
            - Role name: "coder", "tester", "reviewer", "debugger", "researcher"
            - "full": All registered tools
            - set/frozenset: Custom set of tool names
            
    Returns:
        Dict mapping tool_name -> ToolInfo for accessible tools
    
    Examples:
        # Sub-agent with limited scope
        manifest = get_tool_manifest("coder")
        
        # Fully empowered agent
        manifest = get_tool_manifest("full")
        
        # Custom scope
        manifest = get_tool_manifest({"read_file", "write_file", "run_shell"})
        
        # Minimal — agent must use tool_search to discover and unlock others
        manifest = get_tool_manifest("minimal")
    """
    if isinstance(scope, (set, frozenset)):
        # Custom set
        return {name: _REGISTRY[name] for name in scope if name in _REGISTRY}
    
    if scope == "full":
        return dict(_REGISTRY)
    
    if scope in ROLE_MANIFESTS:
        if scope == "full":
            return dict(_REGISTRY)
        allowed = ROLE_MANIFESTS[scope]
        return {name: _REGISTRY[name] for name in allowed if name in _REGISTRY}
    
    # Unknown scope — return minimal + warn
    return {name: _REGISTRY[name] for name in MINIMAL_TOOL_SET if name in _REGISTRY}


def get_available_tool_names(scope: str | set[str] | frozenset[str] = "minimal") -> list[str]:
    """Get list of available tool names for a given scope."""
    manifest = get_tool_manifest(scope)
    return sorted(manifest.keys())


def build_tool_manifest_prompt(scope: str | set[str] | frozenset[str] = "minimal") -> str:
    """
    Build a system prompt section listing available tools for an agent.
    
    Returns formatted prompt with tool names, descriptions, and examples.
    """
    manifest = get_tool_manifest(scope)
    
    if not manifest:
        return "No tools available."
    
    output = ["# Available Tools\n"]
    output.append(f"You have access to {len(manifest)} tools:\n")
    
    for name in sorted(manifest.keys()):
        info = manifest[name]
        output.append(f"## {name}")
        output.append(f"Category: {info.category}")
        output.append(f"Description: {info.description}")
        if info.parameters:
            params = ", ".join(info.parameters.keys())
            output.append(f"Parameters: {params}")
        output.append(f"Example: `{info.example}`")
        output.append("")
    
    if scope == "minimal":
        output.append(
            "NOTE: You are running with a minimal tool set. "
            "Use tool_search(\"description of what you want to do\") "
            "to discover and unlock additional tools as needed."
        )
    
    return "\n".join(output)


# ─── Auto-Correction Layer ──────────────────────────────────────────────

def validate_tool_call(tool_name: str, kwargs: dict[str, Any]) -> Optional[str]:
    """
    Validate a tool call and return corrected instructions if invalid.
    
    Args:
        tool_name: Name of the tool being called
        kwargs: Keyword arguments being passed
    
    Returns:
        None if valid, or a "Did you mean..." correction string if invalid.
    """
    if tool_name not in _REGISTRY:
        # Wrong tool name — fuzzy match
        close = difflib.get_close_matches(tool_name, _REGISTRY.keys(), n=3, cutoff=0.4)
        if close:
            best = close[0]
            info = _REGISTRY[best]
            return (
                f"Tool '{tool_name}' does not exist. Did you mean '{best}'?\n"
                f"{best}: {info.description}\n"
                f"Example: {info.example}"
            )
        else:
            return f"Tool '{tool_name}' does not exist. Use tool_search('') to see available tools."
    
    info = _REGISTRY[tool_name]
    
    # Check for wrong parameters
    valid_params = set(info.parameters.keys())
    provided_params = set(kwargs.keys())
    
    # Check for unknown params
    unknown = provided_params - valid_params
    if unknown:
        # Try to fuzzy match unknown params
        corrections = []
        for bad_param in unknown:
            close_params = difflib.get_close_matches(bad_param, valid_params, n=1, cutoff=0.5)
            if close_params:
                corrections.append(f"  - '{bad_param}' → did you mean '{close_params[0]}'?\n")
            else:
                corrections.append(f"  - '{bad_param}' is not a valid parameter\n")
        
        params_list = ", ".join(sorted(valid_params))
        return (
            f"Invalid parameter(s) for '{tool_name}':\n"
            + "".join(corrections)
            + f"\nValid parameters: {params_list}\n"
            f"Example: {info.example}"
        )
    
    return None  # Valid


def auto_correct(tool_name: str, kwargs: dict[str, Any] = None) -> str:
    """
    Auto-correct a tool call. Returns either the correction or confirmation.
    
    This is the main entry point for the auto-correction layer.
    Called automatically when a tool call fails, or proactively by the agent.
    
    Args:
        tool_name: Name of the tool
        kwargs: Optional keyword arguments to validate
    
    Returns:
        Correction message or "Tool call looks valid."
    """
    if kwargs:
        result = validate_tool_call(tool_name, kwargs)
        if result:
            return result
    
    if tool_name not in _REGISTRY:
        close = difflib.get_close_matches(tool_name, _REGISTRY.keys(), n=3, cutoff=0.4)
        if close:
            suggestions = []
            for name in close:
                t = _REGISTRY[name]
                suggestions.append(f"  - {name}: {t.description}")
            return (
                f"Tool '{tool_name}' not found. Did you mean:\n"
                + "\n".join(suggestions)
            )
        return f"Tool '{tool_name}' not found. Use tool_search('') to list all tools."
    
    info = _REGISTRY[tool_name]
    return f"Tool '{tool_name}' is valid. {info.description}\nExample: {info.example}"


# ─── Tool Unlocking ─────────────────────────────────────────────────────

# Track which tools an agent has "unlocked" during a session
_unlocked_tools: set[str] = set()


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
    """
    if tool_name not in _REGISTRY:
        close = difflib.get_close_matches(tool_name, _REGISTRY.keys(), n=3, cutoff=0.4)
        if close:
            return f"Tool '{tool_name}' not found. Did you mean: {', '.join(close)}?"
        return f"Tool '{tool_name}' not found. Use tool_search('') to list all tools."
    
    _unlocked_tools.add(tool_name)
    info = _REGISTRY[tool_name]
    return f"Unlocked '{tool_name}': {info.description}\nExample: {info.example}"


def get_unlocked_tools() -> set[str]:
    """Get set of tools unlocked in this session."""
    return set(_unlocked_tools)


def reset_unlocked_tools() -> None:
    """Reset unlocked tools (for new session/sub-agent spawn)."""
    _unlocked_tools.clear()


def get_effective_manifest(base_scope: str = "minimal") -> dict[str, ToolInfo]:
    """
    Get the effective tool manifest including unlocked tools.
    
    Args:
        base_scope: Base manifest scope
    
    Returns:
        Dict of tool_name -> ToolInfo including base + unlocked
    """
    manifest = get_tool_manifest(base_scope)
    for name in _unlocked_tools:
        if name in _REGISTRY and name not in manifest:
            manifest[name] = _REGISTRY[name]
    return manifest
