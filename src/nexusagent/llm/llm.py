# src/nexusagent/llm.py
"""Multi-provider LLM bridge with retry and circuit-breaker support.

Routes generation requests between Gemini (google-genai) and OpenRouter
(openai-compatible) providers based on the active configuration.  All
public calls are wrapped with :func:`retry_with_backoff` so transient
failures are handled gracefully.
"""

import logging
import os

import google.generativeai as genai
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


class LLMProvider:
    """Bridge for multiple LLM providers.
    Handles routing between Gemini and OpenRouter using official SDKs.
    """

    def __init__(self) -> None:
        """Initialize the LLM provider with configured API keys and model settings."""
        # Reload settings to get the latest config (avoids stale singleton)
        import importlib

        import nexusagent.infrastructure.config as _cfg

        importlib.reload(_cfg)
        _settings = _cfg.settings

        # Prefer project settings over environment variables (Hermes loads
        # its own .env which may contain a different GEMINI_API_KEY for Gemma)
        self.gemini_key = _settings.agent.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)

        # OpenRouter Setup (OpenAI compatible)
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        self.openrouter_client = AsyncOpenAI(
            api_key=self.openrouter_key,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )

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

    @retry_with_backoff(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
        exceptions=(Exception,),
    )
    async def generate(
        self, prompt: str, system_prompt: str | None = None, timeout: float = 120.0, **kwargs
    ) -> LLMResponse:
        """Generate a response from the active LLM provider.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system-level instructions.
            timeout: Maximum seconds to wait for a response.
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
                prompt, system_prompt, model_id, timeout=timeout, **kwargs
            )
        elif provider == "openrouter":
            return await self._call_openrouter(
                prompt, system_prompt, model_id, timeout=timeout, **kwargs
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
        **kwargs,
    ) -> LLMResponse:
        try:
            model = genai.GenerativeModel(model_name=model_id, system_instruction=system_prompt)
            # google-genai's generate_content_async does not accept timeout kwarg
            response = await model.generate_content_async(prompt)
            return LLMResponse(content=response.text, model_used=model_id, provider="gemini")
        except TimeoutError:
            raise TimeoutError(f"LLM request timed out after {timeout}s") from None
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
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
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self.openrouter_client.chat.completions.create(
                model=model_id, messages=messages, timeout=timeout, **kwargs
            )
            return LLMResponse(
                content=response.choices[0].message.content,
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
