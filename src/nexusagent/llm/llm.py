# src/nexusagent/llm.py
"""Multi-provider LLM bridge with retry and circuit-breaker support.

Routes generation requests between Gemini (google-genai Interactions API) and
OpenRouter (openai-compatible) providers based on the active configuration.
All public calls are wrapped with :func:`retry_with_backoff` so transient
failures are handled gracefully.

Gemini path uses the 2026 Interactions API with native tool support:
- Google Search (grounding)
- Code Execution (Python sandbox)
- URL Context (fetch + summarize)
- Function Calling (custom tools)
"""

import logging
import os
from typing import Any

from google import genai
from openai import AsyncOpenAI
from pydantic import BaseModel

from nexusagent.infrastructure.config import settings
from nexusagent.infrastructure.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class LLMResponse(BaseModel):
    """Structured response from an LLM provider call."""

    content: str
    model_used: str
    provider: str
    tool_calls: list[dict[str, Any]] | None = None
    interaction_id: str | None = None  # For multi-turn with tools


class LLMProvider:
    """Bridge for multiple LLM providers.

    Handles routing between Gemini (Interactions API) and OpenRouter
    (OpenAI-compatible) providers.
    """

    def __init__(self) -> None:
        """Initialize the LLM provider with configured API keys and model settings."""
        # Reload settings to get the latest config (avoids stale singleton)
        import importlib

        import nexusagent.infrastructure.config as _cfg

        importlib.reload(_cfg)
        _settings = _cfg.settings

        # Gemini Setup (Interactions API - requires google-genai>=2.3.0)
        self.gemini_key = _settings.agent.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if self.gemini_key:
            self.gemini_client = genai.Client(api_key=self.gemini_key)
        else:
            self.gemini_client = None
            logger.warning("GEMINI_API_KEY not configured - Gemini provider disabled")

        # OpenRouter Setup (OpenAI compatible)
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        self.openrouter_client = AsyncOpenAI(
            api_key=self.openrouter_key,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        ) if self.openrouter_key else None

    def get_active_model(self) -> tuple[str, str]:
        """Returns (provider, model_id) based on current settings."""
        provider = settings.agent.primary_provider
        if provider == "gemini":
            return "gemini", settings.agent.gemini_model
        elif provider == "openrouter":
            model = (
                settings.agent.openrouter_override_model
                if settings.agent.openrouter_override_model
                else settings.agent.openrouter_default_model
            )
            return "openrouter", model
        return "gemini", settings.agent.default_model

    def _get_gemini_tools(self) -> list[dict[str, Any]]:
        """Get native Gemini tools configuration.

        Returns a list of built-in tools to enable:
        - google_search: Ground responses in real-time web data
        - code_execution: Execute Python code in sandbox
        - url_context: Fetch and summarize URLs
        """
        tools = []

        # Enable Google Search for grounding
        tools.append({"type": "google_search"})

        # Enable Code Execution for math/data tasks
        tools.append({"type": "code_execution"})

        # Enable URL Context for webpage summarization
        tools.append({"type": "url_context"})

        return tools

    @retry_with_backoff(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
        exceptions=(Exception,),
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        timeout: float = 120.0,
        previous_interaction_id: str | None = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from the active LLM provider.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system-level instructions.
            timeout: Maximum seconds to wait for a response.
            previous_interaction_id: For multi-turn conversations with tool context.
            **kwargs: Additional provider-specific parameters.

        Returns:
            A structured ``LLMResponse`` with the generated content.

        Raises:
            ValueError: If the active provider is not supported.
        """
        provider, model_id = self.get_active_model()
        logger.info(f"Generating response using {provider} ({model_id})")

        if provider == "gemini":
            return await self._call_gemini(
                prompt, system_prompt, model_id,
                timeout=timeout,
                previous_interaction_id=previous_interaction_id,
                **kwargs
            )
        elif provider == "openrouter":
            return await self._call_openrouter(
                prompt, system_prompt, model_id,
                timeout=timeout,
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @retry_with_backoff(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
        exceptions=(Exception,),
    )
    async def _call_gemini(
        self,
        prompt: str,
        system_prompt: str | None,
        model_id: str,
        timeout: float = 120.0,
        previous_interaction_id: str | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Call Gemini using the Interactions API with native tool support.

        The Interactions API automatically handles:
        - Tool selection and execution (server-side tools)
        - Multi-turn conversation state
        - Tool context circulation

        Args:
            prompt: User input
            system_prompt: System instructions (prepended to prompt)
            model_id: Gemini model name (e.g., "gemini-2.5-flash")
            timeout: Request timeout in seconds
            previous_interaction_id: Continue from previous interaction
            **kwargs: Additional parameters

        Returns:
            LLMResponse with content and interaction metadata
        """
        if not self.gemini_client:
            raise ValueError("Gemini client not initialized (missing API key)")

        try:
            # Build input with system prompt
            full_input = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

            # Configure native tools
            tools_config = self._get_gemini_tools()

            logger.info(f"Calling Gemini with native tools: {[t['type'] for t in tools_config]}")

            # Create interaction with native tool support
            interaction = self.gemini_client.interactions.create(
                model=model_id,
                input=full_input,
                tools=tools_config,
                previous_interaction_id=previous_interaction_id,
            )

            # Extract final output
            content = interaction.output_text or ""

            # Collect tool call metadata for logging/debugging
            tool_calls = []
            if hasattr(interaction, 'steps') and interaction.steps:
                for step in interaction.steps:
                    if hasattr(step, 'type') and step.type == 'function_call':
                        tool_calls.append({
                            'name': step.name,
                            'arguments': step.arguments if hasattr(step, 'arguments') else {},
                            'id': step.id if hasattr(step, 'id') else '',
                        })

            logger.info(f"Gemini response: {len(content)} chars, {len(tool_calls)} tool calls")

            return LLMResponse(
                content=content,
                model_used=model_id,
                provider="gemini",
                tool_calls=tool_calls if tool_calls else None,
                interaction_id=interaction.id if hasattr(interaction, 'id') else None,
            )

        except TimeoutError:
            raise TimeoutError(f"LLM request timed out after {timeout}s") from None
        except Exception as e:
            logger.error(f"Gemini Interactions API error: {e}")
            raise

    @retry_with_backoff(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
        exceptions=(Exception,),
    )
    async def _call_openrouter(
        self,
        prompt: str,
        system_prompt: str | None,
        model_id: str,
        timeout: float = 120.0,
        **kwargs,
    ) -> LLMResponse:
        """Call OpenRouter using OpenAI-compatible API."""
        if not self.openrouter_client:
            raise ValueError("OpenRouter client not initialized (missing API key)")

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self.openrouter_client.chat.completions.create(
                model=model_id,
                messages=messages,
                timeout=timeout,
                **kwargs
            )
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model_used=model_id,
                provider="openrouter",
            )
        except TimeoutError:
            raise TimeoutError(f"LLM request timed out after {timeout}s") from None
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            raise


# Singleton provider instance — stateless, safe to keep as global
# For testability, wrap in a function: get_llm() -> LLMProvider
llm = LLMProvider()
