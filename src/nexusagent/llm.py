# src/nexusagent/llm.py
import logging
import os

import google.generativeai as genai
from openai import AsyncOpenAI
from pydantic import BaseModel

from nexusagent.config import settings
from nexusagent.utils import retry_with_backoff

logger = logging.getLogger(__name__)


class LLMResponse(BaseModel):
    content: str
    model_used: str
    provider: str


class LLMProvider:
    """
    Bridge for multiple LLM providers.
    Handles routing between Gemini and OpenRouter using official SDKs.
    """

    def __init__(self):
        # Gemini Setup
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
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
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> LLMResponse:
        provider, model_id = self.get_active_model()
        logger.info(f"Generating response using {provider} ({model_id})")

        if provider == "gemini":
            return await self._call_gemini(prompt, system_prompt, model_id, **kwargs)
        elif provider == "openrouter":
            return await self._call_openrouter(prompt, system_prompt, model_id, **kwargs)
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
        self, prompt: str, system_prompt: str | None, model_id: str, **kwargs
    ) -> LLMResponse:
        try:
            model = genai.GenerativeModel(model_name=model_id, system_instruction=system_prompt)
            response = await model.generate_content_async(prompt)
            return LLMResponse(content=response.text, model_used=model_id, provider="gemini")
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
        self, prompt: str, system_prompt: str | None, model_id: str, **kwargs
    ) -> LLMResponse:
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self.openrouter_client.chat.completions.create(
                model=model_id, messages=messages, **kwargs
            )
            return LLMResponse(
                content=response.choices[0].message.content,
                model_used=model_id,
                provider="openrouter",
            )
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            raise


# Singleton provider instance
llm = LLMProvider()
