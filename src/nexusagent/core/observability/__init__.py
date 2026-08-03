# src/nexusagent/core/observability/__init__.py
"""Phase 10 Observability & Reliability package."""

from __future__ import annotations

from .chaos import ChaosTestFramework
from .context import (
    component_var,
    event_type_var,
    graph_id_var,
    node_id_var,
    request_id_var,
    task_id_var,
    trace_context,
    trace_id_var,
    worker_id_var,
)
from .failures import FailureClassifier, FailureType
from .health import get_system_health
from .logging import StructuredLoggingFormatter, setup_structured_logging
from .metrics import MetricsCollector, get_metrics

__all__ = [
    "ChaosTestFramework",
    "FailureClassifier",
    "FailureType",
    "MetricsCollector",
    "StructuredLoggingFormatter",
    "component_var",
    "event_type_var",
    "get_metrics",
    "get_system_health",
    "graph_id_var",
    "node_id_var",
    "request_id_var",
    "setup_structured_logging",
    "task_id_var",
    "trace_context",
    "trace_id_var",
    "worker_id_var",
]
