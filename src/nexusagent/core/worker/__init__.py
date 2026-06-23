"""NATS-backed task execution worker and worker pool.

Provides:
- NexusWorker: NATS subscriber that executes agent tasks with circuit-breaker
  protection, health monitoring, and degraded-mode operation
- WorkerPool: concurrency-limited pool that spawns isolated sub-agent workers
  with turn counting and wall-time bounds
- handle_task: shared task handler used by both worker and pool
"""

from __future__ import annotations

import asyncio  # Re-exported for test patching (test_worker_pool patches worker.asyncio.sleep)

from nexusagent.core.worker.handler import (
    _agent_breaker,
    _nats_breaker,
    _run_agent_task,
    _run_research_workflow,
)
from nexusagent.core.worker.pool import WorkerPool, get_worker_pool, set_worker_pool, worker_pool
from nexusagent.core.worker.worker import NexusWorker, get_worker, set_worker, worker

__all__ = [
    "NexusWorker",
    "WorkerPool",
    "_run_agent_task",
    "_run_research_workflow",
    "asyncio",
    "get_worker",
    "get_worker_pool",
    "set_worker",
    "set_worker_pool",
    "worker",
    "worker_pool",
]
