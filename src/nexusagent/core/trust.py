"""Trust infrastructure — trust levels, content wrapping, and anomaly scoring.

Provides the building blocks for typed trust boundaries across the agent
system: trust levels that classify content provenance, a trusted content
wrapper that survives serialization, and a multi-signal anomaly scorer
for prompt injection detection.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import IntEnum
from threading import Lock
from typing import Any


# ─── TrustLevel ──────────────────────────────────────────────────────────


class TrustLevel(IntEnum):
    """Provenance-based trust classification for content entering the agent.

    Higher values = more trusted:

    ================= ====================================================
    Value             Semantics
    ================= ====================================================
    ``TRUSTED``       Verified system-internal content (e.g., system prompt
                      fragments assembled by the framework).
    ``USER_FILE``     Content loaded from a user-accessible file via
                      ``@file`` injection. Not system-generated, but user-
                      authored so not adversarial by default.
    ``TOOL_INTERNAL`` Content produced by a first-party tool registered
                      in the codebase.
    ``TOOL_EXTERNAL`` Content produced by a dynamically loaded MCP tool or
                      third-party plugin.
    ``UNTRUSTED``     Content from an unverified source — no provenance
                      available. Scored aggressively.
    ================= ====================================================
    """

    TRUSTED = 50
    USER_FILE = 40
    TOOL_INTERNAL = 30
    TOOL_EXTERNAL = 20
    UNTRUSTED = 10


# ─── TrustedContent ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class TrustedContent:
    """Immutable wrapper around tool output annotated with trust metadata.

    Survives serialization via ``to_dict()`` / ``from_dict()`` — used
    in ``additional_kwargs["trust"]`` for cross-turn persistence.
    """

    content: str
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    anomaly_score: float = 0.0  # 0.0 = normal, 1.0 = definitely anomalous
    provenance: str = ""  # e.g. "tool:memory_search", "mcp:weather-server"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict (for ``additional_kwargs``)."""
        return {
            "content": self.content,
            "trust_level": self.trust_level.value,
            "anomaly_score": self.anomaly_score,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrustedContent:
        """Deserialize from a dict produced by ``to_dict()``."""
        return cls(
            content=data.get("content", ""),
            trust_level=TrustLevel(data.get("trust_level", TrustLevel.UNTRUSTED.value)),
            anomaly_score=data.get("anomaly_score", 0.0),
            provenance=data.get("provenance", ""),
        )


# ─── AnomalyScorer ───────────────────────────────────────────────────────


# Common prompt-injection instruction patterns
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(previous|all|above)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"override\s+(system|prompt|instructions)", re.IGNORECASE),
    re.compile(r"\[\s*system\s*\]", re.IGNORECASE),
    re.compile(r"<system>", re.IGNORECASE),
    re.compile(r"you\s+must\s+now", re.IGNORECASE),
    re.compile(r"forget\s+(previous|all|everything)", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|all|above)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if|though)", re.IGNORECASE),
    re.compile(r"from\s+now\s+on\s*,?\s*you\s+are", re.IGNORECASE),
]

# Imperative verbs that indicate instruction-heavy content
_IMPERATIVE_VERBS: list[re.Pattern] = [
    re.compile(r"\bignore\b", re.IGNORECASE),
    re.compile(r"\boverride\b", re.IGNORECASE),
    re.compile(r"\bforget\b", re.IGNORECASE),
    re.compile(r"\bdisregard\b", re.IGNORECASE),
    re.compile(r"\bpretend\b", re.IGNORECASE),
    re.compile(r"\boutput\b", re.IGNORECASE),
    re.compile(r"\bprint\b", re.IGNORECASE),
    re.compile(r"\breturn\b", re.IGNORECASE),
]


class AnomalyScorer:
    """Multi-signal anomaly detector for prompt injection.

    Combines four signals into a single [0.0, 1.0] score:

    1. **Pattern match** — regex hits against known injection templates.
    2. **Shannon entropy** — unusually high character randomness.
    3. **Length outlier** — content length far from historical mean.
    4. **Instruction density** — ratio of imperative verbs to total words.

    A **single-signal boost trigger** prevents bypass attacks that keep
    each individual signal below threshold while still being malicious.
    If any single signal exceeds ``single_signal_boost_threshold``,
    the final score is multiplied by ``single_signal_boost_multiplier``.

    Thread-safe: ``_length_history`` is guarded by a ``Lock``.
    """

    # Signal weights — sum to 1.0
    _PATTERN_WEIGHT = 0.40
    _ENTROPY_WEIGHT = 0.25
    _LENGTH_WEIGHT = 0.20
    _DENSITY_WEIGHT = 0.15

    # Boost trigger
    _SINGLE_SIGNAL_BOOST_THRESHOLD = 0.70
    _SINGLE_SIGNAL_BOOST_MULTIPLIER = 1.5

    # Entropy thresholds
    _ENTROPY_LOW = 3.0  # Normal text
    _ENTROPY_HIGH = 5.5  # Random-looking

    # Length history (rolling window, thread-safe)
    _MAX_HISTORY = 100

    def __init__(self) -> None:
        self._lock = Lock()
        self._length_history: list[int] = []

    def score(self, text: str) -> float:
        """Compute a combined anomaly score for *text*.

        Returns a float in [0.0, 1.0]:
        - 0.0: completely normal
        - 1.0: almost certainly anomalous
        """
        if not text:
            return 0.0

        signals = {
            "pattern": self._pattern_score(text),
            "entropy": self._entropy_score(text),
            "length": self._length_score(text),
            "density": self._instruction_density(text),
        }

        raw_score = sum(
            signals[k] * w
            for k, w in [
                ("pattern", self._PATTERN_WEIGHT),
                ("entropy", self._ENTROPY_WEIGHT),
                ("length", self._LENGTH_WEIGHT),
                ("density", self._DENSITY_WEIGHT),
            ]
        )

        # Single-signal boost trigger
        if any(v >= self._SINGLE_SIGNAL_BOOST_THRESHOLD for v in signals.values()):
            raw_score = min(raw_score * self._SINGLE_SIGNAL_BOOST_MULTIPLIER, 1.0)

        return round(raw_score, 4)

    def _pattern_score(self, text: str) -> float:
        """Fraction of known injection patterns that match."""
        hits = sum(1 for p in _INJECTION_PATTERNS if p.search(text))
        if not hits:
            return 0.0
        return min(hits / 4.0, 1.0)  # 4+ patterns → max score

    def _entropy_score(self, text: str) -> float:
        """Shannon entropy scaled to [0, 1]."""
        entropy = self._shannon_entropy(text)
        if entropy <= self._ENTROPY_LOW:
            return 0.0
        if entropy >= self._ENTROPY_HIGH:
            return 1.0
        return (entropy - self._ENTROPY_LOW) / (self._ENTROPY_HIGH - self._ENTROPY_LOW)

    @staticmethod
    def _shannon_entropy(text: str) -> float:
        """Compute Shannon entropy of a string."""
        if not text:
            return 0.0
        length = len(text)
        freq: dict[str, int] = {}
        for ch in text:
            freq[ch] = freq.get(ch, 0) + 1
        entropy = -sum((count / length) * math.log2(count / length) for count in freq.values())
        return entropy

    def _length_score(self, text: str) -> float:
        """Z-score based on historical length distribution."""
        length = len(text)
        with self._lock:
            self._length_history.append(length)
            if len(self._length_history) > self._MAX_HISTORY:
                self._length_history.pop(0)
            if len(self._length_history) < 3:
                return 0.0  # Not enough data yet
            mean = sum(self._length_history) / len(self._length_history)
            variance = sum((x - mean) ** 2 for x in self._length_history) / len(self._length_history)
            std = math.sqrt(variance) if variance > 0 else 1.0

        z = abs(length - mean) / std
        # Z-score > 3 is 3σ outlier
        return min(z / 6.0, 1.0)

    def _instruction_density(self, text: str) -> float:
        """Ratio of lines containing imperative verbs."""
        words = text.split()
        if not words:
            return 0.0
        imperative_count = sum(1 for w in words for p in _IMPERATIVE_VERBS if p.search(w))
        ratio = imperative_count / len(words)
        # > 15% imperative verbs → suspicious
        return min(ratio / 0.30, 1.0)


# Module-level singleton
_anomaly_scorer = AnomalyScorer()


def get_anomaly_scorer() -> AnomalyScorer:
    """Return the module-level AnomalyScorer singleton."""
    return _anomaly_scorer


# ─── TrustConfig ─────────────────────────────────────────────────────────


@dataclass
class TrustConfig:
    """Configuration for the trust subsystem.

    Fields mirror the ``trust:`` section of the YAML config, with
    defaults that are safe for production.
    """

    enabled: bool = True
    anomaly_threshold: float = 0.60  # Flag content above this score
    min_score: float = 0.0  # Minimum score to report (0 = all)
    single_signal_boost_threshold: float = 0.70
    single_signal_boost_multiplier: float = 1.5
    pattern_weight: float = 0.40
    entropy_weight: float = 0.25
    length_weight: float = 0.20
    density_weight: float = 0.15