# src/nexusagent/memory/extraction.py
"""Regex-based auto memory extraction (v1 — no LLM call).

After each agent turn, extract memorable facts using regex patterns.
Store as observation-type memories. Designed for fire-and-forget async
execution via ``asyncio.create_task()``.

Each extraction returns a dict::
    {"content": str, "type": "observation", "description": str,
     "confidence": float, "entities": list[str]}
"""

import re
from dataclasses import dataclass, field


@dataclass
class ExtractionResult:
    """A single extracted memory candidate."""

    content: str
    type: str = "observation"
    description: str = ""
    confidence: float = 0.5
    entities: list[str] = field(default_factory=list)


# ── Regex patterns ──────────────────────────────────────────────────────

# Entity: proper nouns (capitalized words not at sentence start), project names, file paths
RE_ENTITY_PROPER_NOUN = re.compile(
    r"(?<![\.\!\?\n])\s([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"  # Multi-word proper nouns
)
RE_ENTITY_PROJECT_NAME = re.compile(
    r"\b([A-Z][a-zA-Z]*(?:[-_][A-Z][a-zA-Z]*)+)\b"  # CamelCase or kebab-case project names
)
RE_ENTITY_FILE_PATH = re.compile(
    r"(?:[\w./-]+\.(?:py|js|ts|tsx|jsx|rs|go|java|c|cpp|h|hpp|yaml|yml|toml|json|md|txt|cfg|ini|sh|bash|zsh|sql|html|css|scss|less|vue|svelte|rb|php|ex|exs|erl|hs|ml|fs|ps1|psm1|psd1|dockerfile|makefile|cmake|gradle|sbt|xml|xsl|svg))"
)

# Decision phrases
RE_DECISION = re.compile(
    r"(?:decided to|chose to|will use|going to|plan to|intend to|opted for|settled on|selected)\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)

# Preference phrases
RE_PREFERENCE = re.compile(
    r"(?:i\s+(?:prefer|like|love|enjoy|always|never|don\'t like|dislike|hate|avoid)|"
    r"we\s+(?:prefer|like|always|never|don\'t like)|"
    r"my\s+(?:preference|favorite|favourite))\s*[:\s]?\s*(.+?)(?:\.|$)",
    re.IGNORECASE,
)

# Error/problem phrases
RE_ERROR = re.compile(
    r"(?:error|failed|bug|fix|issue|broken|crash|exception|traceback|"
    r"doesn\'t work|won\'t work|not working|problem with)\s*[:\s]?\s*(.+?)(?:\.|$)",
    re.IGNORECASE,
)

# Minimum content length to bother extracting
MIN_CONTENT_LENGTH = 20


class MemoryExtractor:
    """Extract memorable facts from text using regex patterns.

    No LLM call in v1 — purely regex-based for speed, cost, and
    determinism. Each ``extract()`` call returns a list of
    ``ExtractionResult`` objects that can be fed to the memory system.
    """

    def extract(self, text: str) -> list[ExtractionResult]:
        """Extract memorable facts from *text*.

        Returns a list of ``ExtractionResult`` objects (may be empty).
        Only extracts if *text* is substantial (>20 chars).
        """
        if len(text) < MIN_CONTENT_LENGTH:
            return []

        results: list[ExtractionResult] = []
        seen_contents: set[str] = set()

        # Order matters: higher-signal extractions first
        self._extract_errors(text, results, seen_contents)
        self._extract_decisions(text, results, seen_contents)
        self._extract_preferences(text, results, seen_contents)
        self._extract_entities(text, results, seen_contents)

        return results

    # ── Private extractors ──────────────────────────────────────────────

    def _add_result(
        self,
        results: list[ExtractionResult],
        seen: set[str],
        content: str,
        description: str,
        confidence: float,
        entities: list[str] | None = None,
    ) -> None:
        """Dedup helper — skip if content already seen."""
        normalized = content.strip().lower()
        if normalized in seen:
            return
        seen.add(normalized)
        results.append(
            ExtractionResult(
                content=content.strip(),
                description=description,
                confidence=min(max(confidence, 0.0), 1.0),
                entities=entities or [],
            )
        )

    def _extract_entities(
        self,
        text: str,
        results: list[ExtractionResult],
        seen: set[str],
    ) -> None:
        """Extract file paths and project names as entity observations."""
        # File paths — high value, very specific
        file_paths = RE_ENTITY_FILE_PATH.findall(text)
        for fp in file_paths[:5]:  # Cap at 5 per turn
            self._add_result(
                results,
                seen,
                f"Referenced file: {fp}",
                "entity-file-path",
                confidence=0.7,
                entities=[fp],
            )

        # Proper nouns (multi-word capitalized phrases)
        proper_nouns = RE_ENTITY_PROPER_NOUN.findall(text)
        for pn in proper_nouns[:3]:
            pn = pn.strip()
            if len(pn) > 3:
                self._add_result(
                    results,
                    seen,
                    f"Mentioned entity: {pn}",
                    "entity-proper-noun",
                    confidence=0.5,
                    entities=[pn],
                )

    def _extract_decisions(
        self,
        text: str,
        results: list[ExtractionResult],
        seen: set[str],
    ) -> None:
        """Extract decision statements."""
        for match in RE_DECISION.finditer(text):
            decision_text = match.group(0).strip()
            self._add_result(
                results,
                seen,
                decision_text,
                "decision",
                confidence=0.8,
            )

    def _extract_preferences(
        self,
        text: str,
        results: list[ExtractionResult],
        seen: set[str],
    ) -> None:
        """Extract preference statements."""
        for match in RE_PREFERENCE.finditer(text):
            pref_text = match.group(0).strip()
            self._add_result(
                results,
                seen,
                pref_text,
                "preference",
                confidence=0.85,
            )

    def _extract_errors(
        self,
        text: str,
        results: list[ExtractionResult],
        seen: set[str],
    ) -> None:
        """Extract error/problem statements."""
        for match in RE_ERROR.finditer(text):
            error_text = match.group(0).strip()
            self._add_result(
                results,
                seen,
                error_text,
                "error",
                confidence=0.75,
            )
