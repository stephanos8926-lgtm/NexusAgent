# SPDX-License-Identifier: MIT

# src/nexusagent/core/observability/metrics.py
"""Metrics collection for Runtime, Agent, LLM, and Tool categories."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricValue:
    """A recorded metric value snapshot."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """Thread-safe and async-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._history: list[MetricValue] = []

    def increment(
        self, name: str, value: float = 1.0, labels: dict[str, str] | None = None
    ) -> None:
        """Increment a counter metric."""
        with self._lock:
            key = self._label_key(name, labels)
            self._counters[key] = self._counters.get(key, 0.0) + value
            self._history.append(MetricValue(name, value, labels or {}))

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge metric."""
        with self._lock:
            key = self._label_key(name, labels)
            self._gauges[key] = value
            self._history.append(MetricValue(name, value, labels or {}))

    def record_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Record a histogram / duration metric."""
        with self._lock:
            key = self._label_key(name, labels)
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)
            self._history.append(MetricValue(name, value, labels or {}))

    def get_snapshot(self) -> dict[str, Any]:
        """Return a snapshot of all recorded metrics with aggregated histograms."""
        with self._lock:
            histogram_summaries = {}
            for key, vals in self._histograms.items():
                if vals:
                    histogram_summaries[key] = {
                        "count": len(vals),
                        "sum": sum(vals),
                        "avg": sum(vals) / len(vals),
                        "min": min(vals),
                        "max": max(vals),
                    }
                else:
                    histogram_summaries[key] = {
                        "count": 0,
                        "sum": 0.0,
                        "avg": 0.0,
                        "min": 0.0,
                        "max": 0.0,
                    }

            return {
                "counters": self._counters.copy(),
                "gauges": self._gauges.copy(),
                "histograms": histogram_summaries,
            }

    def clear(self) -> None:
        """Clear all metric records."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._history.clear()

    def _label_key(self, name: str, labels: dict[str, str] | None) -> str:
        """Construct a unique labeled metric string."""
        if not labels:
            return name
        labels_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{labels_str}}}"


# Singleton instance
_metrics_instance = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global MetricsCollector instance."""
    return _metrics_instance
