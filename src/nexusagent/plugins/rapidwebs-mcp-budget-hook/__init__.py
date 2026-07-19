"""
MCP Budget Enforcement Hook Plugin.

Enforces token budget limits on MCP requests to prevent context window overflow.
Integrates with pre_llm_call hook in Hermes/NEAR ecosystem.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Budget thresholds (as fraction of max context)
WARNING_THRESHOLDS = [0.50, 0.80, 0.95]
HARD_LIMIT = 0.95
EMERGENCY_COMPRESSION_THRESHOLD = 0.95


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token."""
    return max(1, len(text) // 4)


def get_context_budget(model: str) -> int:
    """Get max context window for a model."""
    # Default models - extend as needed
    model_contexts = {
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-3.5-turbo": 16384,
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "gemini-1.5-pro": 2000000,
        "gemini-1.5-flash": 1000000,
        "mistral-large": 32768,
        "mistral-small": 32768,
        "nemotron-3-ultra": 4096,
    }
    return model_contexts.get(model, 8192)


async def pre_llm_call_budget_check(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    estimated_output: int = 1024,
) -> dict[str, Any]:
    """
    Pre-LLM call budget validation.
    
    Returns:
        {
            "allowed": bool,
            "reason": str,
            "warnings": list[str],
            "emergency_compression": bool,
            "current_usage": int,
            "max_context": int,
        }
    """
    max_context = get_context_budget(model)
    hard_limit = int(max_context * HARD_LIMIT)
    
    # Estimate input tokens
    input_text = " ".join(m.get("content", "") for m in messages if m.get("content"))
    input_tokens = estimate_tokens(input_text)
    
    # Estimate tool schema tokens if present
    tool_tokens = 0
    if tools:
        import json
        tool_tokens = estimate_tokens(json.dumps(tools))
    
    total_estimated = input_tokens + tool_tokens + estimated_output
    usage_pct = total_estimated / max_context
    
    warnings = []
    
    # Check thresholds
    for threshold in WARNING_THRESHOLDS:
        if usage_pct >= threshold:
            warnings.append(f"Context usage at {usage_pct:.1%} (threshold: {threshold:.0%})")
    
    # Hard limit check
    if total_estimated > hard_limit:
        return {
            "allowed": False,
            "reason": f"Exceeds hard limit ({hard_limit} tokens / {HARD_LIMIT:.0%})",
            "warnings": warnings,
            "emergency_compression": False,
            "current_usage": total_estimated,
            "max_context": max_context,
        }
    
    # Emergency compression flag
    emergency = total_estimated > int(max_context * EMERGENCY_COMPRESSION_THRESHOLD)
    
    return {
        "allowed": True,
        "reason": "Within budget",
        "warnings": warnings,
        "emergency_compression": emergency,
        "current_usage": total_estimated,
        "max_context": max_context,
    }


# Hermes hook integration
async def hook_pre_llm_call(hook_context: dict[str, Any]) -> dict[str, Any]:
    """
    Hermes pre_llm_call hook entry point.
    
    Expected hook_context:
    {
        "model": "gpt-4",
        "messages": [...],
        "tools": [...],
        "max_tokens": 4096,
    }
    """
    try:
        result = await pre_llm_call_budget_check(
            model=hook_context.get("model", "unknown"),
            messages=hook_context.get("messages", []),
            tools=hook_context.get("tools"),
            estimated_output=hook_context.get("max_tokens", 1024),
        )
        
        # Log warnings
        for warning in result.get("warnings", []):
            logger.warning(f"MCP Budget: {warning}")
        
        if result.get("emergency_compression"):
            logger.critical(f"MCP Budget: EMERGENCY COMPRESSION TRIGGERED at {result['current_usage']}/{result['max_context']} tokens")
        
        if not result["allowed"]:
            logger.error(f"MCP Budget: BLOCKED - {result['reason']}")
        
        return {
            "action": "allow" if result["allowed"] else "block",
            "reason": result["reason"],
            "warnings": result["warnings"],
            "emergency_compression": result["emergency_compression"],
        }
        
    except Exception as e:
        logger.exception(f"MCP Budget hook failed: {e}")
        # Fail open - don't block on hook errors
        return {"action": "allow", "reason": f"Hook error (fail-open): {e}"}


# Export for plugin registration
__all__ = ["hook_pre_llm_call", "pre_llm_call_budget_check"]