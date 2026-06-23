"""LLM-based memory refinement layer.

Periodically synthesizes raw observations into higher-level insights using LLM.
Integrates into DreamCycle Phase 2 (Patterns) to enhance regex-based extraction
with genuine language understanding.

Flow:
1. DreamCycle.scan() finds raw observations
2. LLMRefinement.synthesize() calls LLM to merge related observations
3. Synthesized insights stored as type="insight" memories with derived_from links
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RefinementResult:
    """A single synthesized insight from LLM refinement."""

    content: str
    confidence: float = 0.8
    source_count: int = 0  # Number of source observations merged
    entities: list[str] = field(default_factory=list)


class LLMRefinement:
    """Synthesizes raw observations into higher-level insights using LLM.

    Uses the configured LLM provider (via agentgateway) to:
    - Merge related observations into coherent narratives
    - Detect patterns across multiple observations
    - Extract higher-level insights from raw facts
    """

    # System prompt for the refinement task
    SYSTEM_PROMPT = """You are a memory refinement agent. Your job is to synthesize raw observations
into higher-level insights.

Given a list of observations from an AI agent's memory, produce a JSON array of synthesized insights.

Rules:
1. Merge related observations into single coherent insights
2. Detect patterns (e.g., "User prefers X in 80% of cases")
3. Resolve contradictions by preferring higher-confidence or more recent observations
4. Each insight should be a single, self-contained fact or pattern
5. Include a confidence score (0.0-1.0) for each insight
6. List relevant entities (file paths, project names, technologies)
7. Keep insights concise — one sentence each
8. If observations are already distinct with no patterns, return them as-is

Output format (JSON array):
[
  {
    "content": "The synthesized insight text",
    "confidence": 0.9,
    "entities": ["entity1", "entity2"]
  }
]

Respond with ONLY the JSON array, no other text."""

    def __init__(
        self,
        llm_call: Any = None,
        min_observations: int = 3,
        max_observations_per_batch: int = 20,
    ):
        """Initialize the refinement layer.

        Args:
            llm_call: Async callable for LLM invocations. If None, uses heuristic fallback.
            min_observations: Minimum observations before refinement triggers.
            max_observations_per_batch: Max observations to send to LLM at once.
        """
        self._llm_call = llm_call
        self._min_observations = min_observations
        self._max_observations_per_batch = max_observations_per_batch

    async def synthesize(
        self,
        observations: list[str],
        existing_insights: list[str] | None = None,
    ) -> list[RefinementResult]:
        """Synthesize observations into higher-level insights.

        Args:
            observations: List of raw observation strings to synthesize.
            existing_insights: Existing insights to avoid duplicating.

        Returns:
            List of RefinementResult objects (may be empty if no LLM available).
        """
        if len(observations) < self._min_observations:
            logger.debug(
                "Skipping refinement: only %d observations (min=%d)",
                len(observations),
                self._min_observations,
            )
            return []

        if self._llm_call is None:
            logger.debug("No LLM call configured, using heuristic refinement")
            return self._heuristic_synthesize(observations)

        # Build the user prompt
        user_prompt = self._build_prompt(observations, existing_insights or [])

        try:
            response = await self._llm_call(
                system=self.SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=2000,
                temperature=0.3,
            )
            return self._parse_response(response)
        except Exception as exc:
            logger.warning("LLM refinement failed, falling back to heuristic: %s", exc)
            return self._heuristic_synthesize(observations)

    def _build_prompt(
        self,
        observations: list[str],
        existing_insights: list[str],
    ) -> str:
        """Build the user prompt for LLM refinement."""
        parts = ["## Raw Observations\n"]
        for i, obs in enumerate(observations[: self._max_observations_per_batch], 1):
            parts.append(f"{i}. {obs}")

        if existing_insights:
            parts.append("\n## Existing Insights (do not duplicate)\n")
            for i, insight in enumerate(existing_insights, 1):
                parts.append(f"{i}. {insight}")

        parts.append("\n\nSynthesize these observations into higher-level insights.")
        return "\n".join(parts)

    def _parse_response(self, response: str) -> list[RefinementResult]:
        """Parse the LLM JSON response into RefinementResult objects."""
        # Extract JSON from response (may be wrapped in markdown)
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM refinement response as JSON: %s", text[:200])
            # Try to extract insights from plain text
            return [
                RefinementResult(
                    content=line.strip(),
                    confidence=0.5,
                    source_count=1,
                )
                for line in text.split("\n")
                if line.strip() and not line.startswith("#")
            ]

        results = []
        for item in data:
            if isinstance(item, str):
                results.append(RefinementResult(content=item, confidence=0.7))
            elif isinstance(item, dict):
                results.append(
                    RefinementResult(
                        content=item.get("content", item.get("insight", "")),
                        confidence=float(item.get("confidence", 0.7)),
                        source_count=int(item.get("source_count", 1)),
                        entities=item.get("entities", []) or [],
                    )
                )
        return [r for r in results if r.content]

    def _heuristic_synthesize(self, observations: list[str]) -> list[RefinementResult]:
        """Heuristic fallback when LLM is not available.

        Groups observations by similarity (shared words) and creates
        simple merged insights.
        """
        if not observations:
            return []

        # Simple grouping: observations sharing 3+ significant words
        groups: list[list[str]] = []
        used = set()

        for i, obs in enumerate(observations):
            if i in used:
                continue
            group = [obs]
            used.add(i)
            words_i = set(obs.lower().split()) - {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or", "but", "with", "by", "from", "as", "it", "this", "that", "i", "we", "you", "he", "she", "they", "my", "our", "your", "his", "her", "their"}

            for j, other in enumerate(observations):
                if j in used or i == j:
                    continue
                words_j = set(other.lower().split()) - {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or", "but", "with", "by", "from", "as", "it", "this", "that", "i", "we", "you", "he", "she", "they", "my", "our", "your", "his", "her", "their"}
                if len(words_i & words_j) >= 3:
                    group.append(other)
                    used.add(j)

            groups.append(group)

        results = []
        for group in groups:
            if len(group) == 1:
                results.append(
                    RefinementResult(
                        content=group[0],
                        confidence=0.5,
                        source_count=1,
                    )
                )
            else:
                # Merge group into a single insight
                merged = " | ".join(group[:5])  # Cap at 5 observations per insight
                if len(group) > 5:
                    merged += f" (and {len(group) - 5} more)"
                results.append(
                    RefinementResult(
                        content=merged,
                        confidence=0.6,
                        source_count=len(group),
                    )
                )

        return results

    async def detect_contradictions(
        self,
        memories: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Detect contradictions in memories about the same entity.

        Groups memories by entity and uses LLM to detect conflicting facts.

        Args:
            memories: List of memory dicts with 'content', 'entities', 'confidence' keys.

        Returns:
            List of contradiction dicts with:
                - entity: The entity name
                - memories: List of conflicting memory contents
                - resolution: LLM's suggested resolution
                - keep: Index of the memory to keep
                - remove: List of indices of memories to mark as superseded
        """
        if len(memories) < 2:
            return []

        # Group memories by entity
        entity_memories: dict[str, list[tuple[int, dict]]] = {}
        for i, mem in enumerate(memories):
            for entity in mem.get("entities", []):
                entity_memories.setdefault(entity, []).append((i, mem))

        # Only check entities with multiple memories
        contradictions = []
        for entity, mems in entity_memories.items():
            if len(mems) < 2:
                continue

            # Check for contradictions using LLM
            if self._llm_call is not None:
                try:
                    contradiction = await self._check_contradiction_llm(entity, mems)
                    if contradiction:
                        contradictions.append(contradiction)
                except Exception as exc:
                    logger.warning("LLM contradiction check failed for %s: %s", entity, exc)
            else:
                # Heuristic: check for obvious conflicts (same entity, different values)
                contradiction = self._check_contradiction_heuristic(entity, mems)
                if contradiction:
                    contradictions.append(contradiction)

        return contradictions

    async def _check_contradiction_llm(
        self,
        entity: str,
        memories: list[tuple[int, dict[str, Any]]],
    ) -> dict[str, Any] | None:
        """Use LLM to check if memories about an entity contradict each other."""
        system_prompt = """You are a contradiction detection agent. Given multiple memories about the same entity, determine if any contradict each other.

A contradiction occurs when two memories make conflicting claims about the same thing (e.g., "User prefers pytest" vs "User prefers unittest").

Output format (JSON):
{
  "has_contradiction": true/false,
  "resolution": "Brief explanation of which memory is correct and why",
  "keep": <index of memory to keep>,
  "remove": [<indices of memories to mark as superseded>]
}

If no contradiction, output: {"has_contradiction": false}
Respond with ONLY the JSON, no other text."""

        user_prompt = f"Entity: {entity}\n\nMemories:\n"
        for idx, (_i, mem) in enumerate(memories):
            content = mem.get("content", "")
            confidence = mem.get("confidence", 0.5)
            user_prompt += f"[{idx}] (confidence: {confidence}) {content}\n"

        try:
            response = await self._llm_call(
                system=system_prompt,
                user=user_prompt,
                max_tokens=500,
                temperature=0.1,
            )
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            if not data.get("has_contradiction", False):
                return None

            return {
                "entity": entity,
                "memories": [mem.get("content", "") for _, mem in memories],
                "resolution": data.get("resolution", ""),
                "keep": data.get("keep", 0),
                "remove": data.get("remove", []),
            }
        except Exception as exc:
            logger.warning("Failed to parse LLM contradiction response: %s", exc)
            return None

    def _check_contradiction_heuristic(
        self,
        entity: str,
        memories: list[tuple[int, dict[str, Any]]],
    ) -> dict[str, Any] | None:
        """Heuristic contradiction detection (no LLM).

        Simple approach: if two memories have very different confidence scores
        for the same entity, flag the lower-confidence one.
        """
        if len(memories) < 2:
            return None

        # Sort by confidence (highest first)
        sorted_mems = sorted(memories, key=lambda x: x[1].get("confidence", 0.5), reverse=True)
        highest = sorted_mems[0]
        lowest = sorted_mems[-1]

        # If there's a significant confidence gap, flag as potential contradiction
        if highest[1].get("confidence", 0.5) - lowest[1].get("confidence", 0.5) > 0.3:
            return {
                "entity": entity,
                "memories": [mem.get("content", "") for _, mem in memories],
                "resolution": f"Heuristic: keeping higher-confidence memory ({highest[1].get('confidence', 0.5):.2f} vs {lowest[1].get('confidence', 0.5):.2f})",
                "keep": 0,
                "remove": [i for i, _ in sorted_mems[1:]],
            }
        return None
