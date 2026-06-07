"""
Tool discovery helpers for NexusAgent.

This module provides validation and auto-correction utilities.
The main discovery function is tool_search() in registry.py.
"""

from typing import Any
from nexusagent.tools.registry import _REGISTRY, _is_tool_allowed


def validate_tool_call(tool_name: str, kwargs: dict[str, Any] = None) -> str:
    """
    Validate a tool call and return corrections if needed.
    
    Checks:
    1. Tool exists in registry
    2. Tool is available under current policy
    3. Parameters are correct
    
    Returns:
        Empty string if valid, or correction message if invalid.
    """
    if tool_name not in _REGISTRY:
        return f"Tool '{tool_name}' does not exist. Use tool_search() to find tools."
    
    allowed, reason = _is_tool_allowed(tool_name)
    if not allowed:
        return f"ACCESS DENIED: {reason}"
    
    if kwargs:
        info = _REGISTRY[tool_name]
        valid_params = set(info.parameters.keys())
        unknown = set(kwargs.keys()) - valid_params
        
        if unknown:
            params_list = ", ".join(sorted(valid_params))
            return (
                f"Invalid parameter(s) for '{tool_name}': {', '.join(unknown)}\n"
                f"Valid parameters: {params_list}\n"
                f"Example: {info.example}"
            )
    
    return ""
