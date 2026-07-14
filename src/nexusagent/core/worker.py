"""NATS-backed task execution worker and worker pool  compat shim.

Re-exports from the worker/ subpackage for backward compatibility.
"""

from __future__ import annotations

from nexusagent.core.worker import (  # noqa: F401
    NexusWorker,
    WorkerPool,
    _run_agent_task,
    _run_research_workflow,
    asyncio,
    get_worker,
    get_worker_pool,
    set_worker,
    set_worker_pool,
    worker,
    worker_pool,
)
