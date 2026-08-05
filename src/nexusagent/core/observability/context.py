# SPDX-License-Identifier: MIT

# src/nexusagent/core/observability/context.py
"""Tracing context and context variables for request, task, and execution correlation."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

# Context variables for distributed tracing correlation identifiers
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
task_id_var: ContextVar[str] = ContextVar("task_id", default="")
graph_id_var: ContextVar[str] = ContextVar("graph_id", default="")
node_id_var: ContextVar[str] = ContextVar("node_id", default="")
worker_id_var: ContextVar[str] = ContextVar("worker_id", default="")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
component_var: ContextVar[str] = ContextVar("component", default="")
event_type_var: ContextVar[str] = ContextVar("event_type", default="")


@contextmanager
def trace_context(
    trace_id: str | None = None,
    request_id: str | None = None,
    task_id: str | None = None,
    graph_id: str | None = None,
    node_id: str | None = None,
    worker_id: str | None = None,
    component: str | None = None,
    event_type: str | None = None,
) -> Generator[dict[str, str]]:
    """Context manager to propagate tracing identifiers down the call stack.

    Generates a unique trace_id if none exists in the current context or arguments.
    Automatically resets context variables on exit to prevent leakage.
    """
    tokens = []

    # Get active trace_id or generate a new one
    active_trace_id = trace_id or trace_id_var.get() or f"tr-{uuid.uuid4().hex[:8]}"
    tokens.append(trace_id_var.set(active_trace_id))

    if request_id is not None:
        tokens.append(request_id_var.set(request_id))
    if task_id is not None:
        tokens.append(task_id_var.set(task_id))
    if graph_id is not None:
        tokens.append(graph_id_var.set(graph_id))
    if node_id is not None:
        tokens.append(node_id_var.set(node_id))
    if worker_id is not None:
        tokens.append(worker_id_var.set(worker_id))
    if component is not None:
        tokens.append(component_var.set(component))
    if event_type is not None:
        tokens.append(event_type_var.set(event_type))

    try:
        yield {
            "trace_id": active_trace_id,
            "request_id": request_id_var.get(),
            "task_id": task_id_var.get(),
            "graph_id": graph_id_var.get(),
            "node_id": node_id_var.get(),
            "worker_id": worker_id_var.get(),
            "component": component_var.get(),
            "event_type": event_type_var.get(),
        }
    finally:
        for token in reversed(tokens):
            token.var.reset(token)
