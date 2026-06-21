"""LLM-powered memory extraction (v2 — replaces regex-based extraction).

Uses LLM to extract structured facts from conversation context.
Falls back to regex-based MemoryExtractor when LLM is unavailable.

Output format: JSON array of facts, each with:
    content, type, description, confidence, entities

Designed for fire-and-forget async execution via asyncio.create_task().
"""

from __future__ import annotations

import json
import logging
from typing import Any

from nexusagent.memory.extraction import ExtractionResult, MemoryExtractor

logger = logging.getLogger(__name__)

# System prompt for LLM extraction
SYSTEM_PROMPT = """You are a memory extraction agent. Given a conversation turn
(user message + assistant response), extract memorable facts as a JSON array.

Rules:
1. Extract ONLY factual observations, decisions, preferences, and errors
2. Each fact should be a single, self-contained statement
3. Include a confidence score (0.0-1.0) for each fact
4. List relevant entities (file paths, project names, technologies)
5. Skip trivial or redundant information
6. If nothing memorable, return an empty array []

Output format (JSON array):
[
  {
    "content": "The factual statement",
    "type": "observation|decision|preference|error",
    "description": "Short title/description",
    "confidence": 0.85,
    "entities": ["entity1", "entity2"]
  }
]

Respond with ONLY the JSON array, no other text."""


class LLMExtractor:
    """Extracts memorable facts from conversation text using LLM.

    Wraps an LLM call to extract structured facts from conversation context.
    Falls back to regex-based MemoryExtractor when LLM is unavailable.

    Args:
        llm_call: Async callable for LLM invocations.
                  Signature: async (system: str, user: str, **kwargs) -> str
        fallback_extractor: Optional fallback extractor when LLM fails.
                             Defaults to regex-based MemoryExtractor.
        min_confidence: Minimum confidence threshold for extracted facts (default: 0.5).
    """

    def __init__(
        self,
        llm_call: Any = None,
        fallback_extractor: MemoryExtractor | None = None,
        min_confidence: float = 0.5,
    ):
        self._llm_call = llm_call
        self._fallback = fallback_extractor or MemoryExtractor()
        self._min_confidence = min_confidence

    async def extract(self, text: str) -> list[ExtractionResult]:
        """Extract memorable facts from conversation text.

        Uses LLM if available, otherwise falls back to regex extraction.

        Args:
            text: The conversation text to extract facts from.

        Returns:
            List of ExtractionResult objects (may be empty).
        """
        if self._llm_call is not None:
            try:
                return await self._extract_with_llm(text)
            except Exception as exc:
                logger.warning("LLM extraction failed, falling back to regex: %s", exc)

        # Fallback to regex
        return self._fallback.extract(text)

    async def _extract_with_llm(self, text: str) -> list[ExtractionResult]:
        """Call LLM to extract facts from text."""
        response = await self._llm_call(
            system=SYSTEM_PROMPT,
            user=f"Extract memorable facts from this conversation:\n\n{text}",
            max_tokens=2000,
            temperature=0.3,
        )
        return self._parse_response(response)

    def _parse_response(self, response: str) -> list[ExtractionResult]:
        """Parse LLM JSON response into ExtractionResult objects."""
        text = response.strip()

        # Extract JSON from response (may be wrapped in markdown)
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        text = text.strip()

        # Handle empty response
        if not text or text == "[]":
            return []

        try:
            data = json.loads(text)
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM extraction response as JSON: %s", text[:200])
            return []

        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            content = item.get("content", item.get("fact", ""))
            if not content:
                continue
            confidence = float(item.get("confidence", 0.5))
            if confidence < self._min_confidence:
                continue
            results.append(
                ExtractionResult(
                    content=content[:500],  # Cap length
                    type=item.get("type", "observation"),
                    description=item.get("description", "")[:100],
                    confidence=min(max(confidence, 0.0), 1.0),
                    entities=item.get("entities", []) if isinstance(item.get("entities"), list) else [],
                )
            )
        return results
