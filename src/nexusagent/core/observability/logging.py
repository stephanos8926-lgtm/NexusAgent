# src/nexusagent/core/observability/logging.py
"""Structured machine-readable logging according to specification."""

from __future__ import annotations

import json
import logging
from datetime import datetime, UTC

from nexusagent.core.observability.context import (
    component_var,
    event_type_var,
    task_id_var,
    trace_id_var,
    worker_id_var,
)


class StructuredLoggingFormatter(logging.Formatter):
    """Custom log formatter to output logs in structured machine-readable JSON format.

    Required fields:
    - timestamp (ISO-8601)
    - trace_id (Correlation ID)
    - task_id (Task reference)
    - worker_id (Worker identity)
    - component (Source subsystem)
    - event_type (Schema-qualified event)
    - severity (INFO / WARN / ERROR / FATAL)
    - message (Human-readable description)
    - metadata (Structured payload)
    """

    def format(self, record: logging.LogRecord) -> str:
        # Resolve values from log record or fallback to active contextvars
        trace_id = getattr(record, "trace_id", None) or trace_id_var.get() or ""
        task_id = getattr(record, "task_id", None) or task_id_var.get() or ""
        worker_id = getattr(record, "worker_id", None) or worker_id_var.get() or ""
        component = getattr(record, "component", None) or component_var.get() or record.name
        event_type = getattr(record, "event_type", None) or event_type_var.get() or f"log.{record.levelname.lower()}"

        # Standard severity mapping
        severity = record.levelname
        if severity == "CRITICAL":
            severity = "FATAL"

        # Build metadata payload
        metadata: dict[str, any] = {}
        if isinstance(record.args, dict):
            metadata.update(record.args)
        elif record.args:
            metadata["args"] = list(record.args)

        # Collect any extra kwargs passed to standard logging
        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "trace_id",
            "task_id",
            "worker_id",
            "component",
            "event_type",
            "message",
        }
        for key, val in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                metadata[key] = val

        # Handle exception info if present
        if record.exc_info:
            metadata["exception"] = self.formatException(record.exc_info)

        log_payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "trace_id": trace_id,
            "task_id": task_id,
            "worker_id": worker_id,
            "component": component,
            "event_type": event_type,
            "severity": severity,
            "message": record.getMessage(),
            "metadata": metadata,
        }

        return json.dumps(log_payload)


def setup_structured_logging(level: str = "INFO") -> None:
    """Configures structured machine-readable logging on the root logger."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredLoggingFormatter())
    root_logger.addHandler(handler)
