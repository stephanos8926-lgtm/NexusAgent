"""LLM provider implementations — OpenAI-compatible, Gemini, OpenRouter, etc."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import httpx

from nexusagent.infrastructure.errors import UpstreamError, UpstreamErrorCode

from .base import LLMProvider, ProviderMetadata, ProviderResult, get_provider_registry

logger = logging.getLogger(__name__)


# ── OpenAI-compatible LLM Provider ─────────────────────────────────────────────

class OpenAICompatibleLLMProvider(LLMProvider):
    """OpenAI-compatible LLM provider (works with any OpenAI-compatible endpoint)."""

    @property
    def name(self) -> str:
        """Backward compat: provider identifier."""
        return "openai_compatible"

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="openai_compatible",
            display_name="OpenAI-compatible",
            description="OpenAI-compatible chat completion endpoint",
            provider_type="llm",
            base_url=self._base_url,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers=headers,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ProviderResult[dict[str, Any]]:
        client = await self._get_client()
        try:
            payload = {
                "model": model or self._model,
                "messages": messages,
            }
            if temperature is not None:
                payload["temperature"] = temperature
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            for k, v in kwargs.items():
                if k not in payload:
                    payload[k] = v

            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return ProviderResult(
                provider="openai_compatible",
                model=model or self._model,
                response=data,
            )
        except Exception as e:
            return ProviderResult(
                provider="openai_compatible",
                model=model or self._model,
                response=None,
                error=UpstreamError(
                    code=UpstreamErrorCode.UNKNOWN,
                    message=str(e),
                    provider="openai_compatible",
                    model=model or self._model,
                    raw_error=e,
                ),
            )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── Gemini LLM ─────────────────────────────────────────────────────────────────

class GeminiLLMProvider(LLMProvider):
    """Gemini LLM provider (chat completion)."""

    @property
    def name(self) -> str:
        """Backward compat: provider identifier."""
        return "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash-preview",
        timeout: int = 60,
    ):
        self._api_key = api_key or self._resolve_key()
        self._model = model
        self._timeout = timeout

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="gemini",
            display_name="Google Gemini",
            description="Google Gemini chat completion API",
            provider_type="llm",
            env_vars=("GEMINI_API_KEY",),
            default_model="gemini-2.5-flash-preview",
        )

    def _resolve_key(self) -> str:
        key = os.environ.get("GEMINI_API_KEY")
        if key:
            return key
        from nexusagent.infrastructure.config import settings
        key = getattr(settings, "gemini_api_key", None)
        if key:
            return key
        for env_path in [Path.home() / ".nexusagent" / ".env"]:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        raise UpstreamError(
            code=UpstreamErrorCode.INVALID_API_KEY,
            message="No Gemini API key configured",
            provider="gemini", model=self._model,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ProviderResult[dict[str, Any]]:
        # Lazy import to avoid circular dependency
        import google.generativeai as genai

        try:
            genai.configure(api_key=self._api_key)

            # Convert messages to Gemini format
            parts = []
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    parts.append({"role": "user", "parts": [content]})
                elif role == "assistant":
                    parts.append({"role": "model", "parts": [content]})
                elif role == "system":
                    parts.append({"role": "user", "parts": [f"[SYSTEM]: {content}"]})

            # Create chat model
            chat_model = genai.GenerativeModel(model_name=model or self._model)
            chat = chat_model.start_chat(history=parts[:-1] if len(parts) > 1 else [])

            last_msg = parts[-1]["parts"][0] if parts else ""
            response = await chat.send_message_async(last_msg)

            return ProviderResult(
                provider="gemini",
                model=model or self._model,
                response={"text": response.text, "candidates": [{}]},
            )
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                code = UpstreamErrorCode.QUOTA_EXCEEDED
            elif "401" in err_str or "unauthorized" in err_str or "apikey" in err_str:
                code = UpstreamErrorCode.INVALID_API_KEY
            else:
                code = UpstreamErrorCode.UNKNOWN
            return ProviderResult(
                provider="gemini", model=model or self._model, response=None,
                error=UpstreamError(code=code, message=str(e), provider="gemini",
                                    model=model or self._model, raw_error=e),
            )


# ── OpenRouter LLM ─────────────────────────────────────────────────────────────

class OpenRouterLLMProvider(LLMProvider):
    """OpenRouter LLM provider (OpenAI-compatible gateway to many models)."""

    @property
    def name(self) -> str:
        """Backward compat: provider identifier."""
        return "openrouter"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "google/gemini-2.5-flash-preview",
        timeout: int = 60,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self._model = model
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="openrouter",
            display_name="OpenRouter",
            description="OpenRouter API (gateway to many models)",
            provider_type="llm",
            env_vars=("OPENROUTER_API_KEY",),
            base_url=self._base_url,
            default_model="google/gemini-2.5-flash-preview",
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers=headers,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ProviderResult[dict[str, Any]]:
        client = await self._get_client()
        try:
            payload = {
                "model": model or self._model,
                "messages": messages,
            }
            if temperature is not None:
                payload["temperature"] = temperature
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            for k, v in kwargs.items():
                if k not in payload:
                    payload[k] = v

            resp = await client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return ProviderResult(
                provider="openrouter",
                model=model or self._model,
                response=data,
            )
        except Exception as e:
            return ProviderResult(
                provider="openrouter",
                model=model or self._model,
                response=None,
                error=UpstreamError(
                    code=UpstreamErrorCode.UNKNOWN,
                    message=str(e),
                    provider="openrouter",
                    model=model or self._model,
                    raw_error=e,
                ),
            )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ═══════════════════════════════════════════════════════════════════════════════
# Registration
# ═══════════════════════════════════════════════════════════════════════════════

def register_llm_providers():
    """Register all built-in LLM providers with the global registry."""
    registry = get_provider_registry()
    registry.register_llm("openai_compatible", OpenAICompatibleLLMProvider)
    registry.register_llm("gemini", GeminiLLMProvider)
    registry.register_llm("openrouter", OpenRouterLLMProvider)
    logger.info("Registered %d LLM providers", 3)
