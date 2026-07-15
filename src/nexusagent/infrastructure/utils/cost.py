"""LLM cost estimation and tracking utilities.

Provides token-to-cost conversion for major providers and cost tracking hooks.
"""

# Provider pricing per 1M tokens (USD) - approximate as of 2026
# Sources: provider documentation
PRICING = {
    # Google Gemini
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro": {"input": 0.50, "output": 2.00},
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    # OpenRouter (aggregated)
    "openrouter": {"input": 0.50, "output": 1.50},  # Average
    # NVIDIA
    "nvidia/nemotron-3-ultra-550b-a55b": {"input": 0.50, "output": 1.50},
    "nvidia/nemotron-3-super-120b-a12b": {"input": 0.25, "output": 0.75},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 7.50},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # Fallback
    "default": {"input": 0.50, "output": 1.50},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for an LLM call.

    Args:
        model: Model name (e.g., "gemini-2.5-flash").
        input_tokens: Input token count.
        output_tokens: Output token count.

    Returns:
        Estimated cost in USD.
    """
    # Find matching pricing
    pricing = PRICING.get(model)
    if pricing is None:
        # Try partial match
        for key in PRICING:
            if key in model.lower():
                pricing = PRICING[key]
                break

    if pricing is None:
        pricing = PRICING["default"]

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def get_model_context_window(model: str) -> int:
    """Return approximate context window for a model.

    Args:
        model: Model name.

    Returns:
        Context window size in tokens.
    """
    CONTEXT_WINDOWS = {
        "gemini-2.5-flash": 1_048_576,
        "gemini-2.5-pro": 2_097_152,
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "claude-sonnet-4": 200_000,
        "claude-opus-4": 200_000,
    }
    return CONTEXT_WINDOWS.get(model, 128_000)
