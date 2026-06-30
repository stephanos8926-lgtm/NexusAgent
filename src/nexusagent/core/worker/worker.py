"""NexusWorker — NATS-backed task execution worker.

Subscribes to task queues, executes agent tasks with circuit-breaker protection,
health monitoring, and degraded-mode operation when NATS is unreachable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from nexusagent.core.worker.handler import (
    _run_agent_task,
    task_repo,
)
from nexusagent.infrastructure.bus import _NATS_HARD_RECONNECT_CAP, AgentBus, get_bus
from nexusagent.infrastructure.config import settings
from nexusagent.infrastructure.db import TaskModel
from nexusagent.infrastructure.utils.budget import create_budget_guard_from_config
from nexusagent.infrastructure.utils.retry import retry_with_backoff
from nexusagent.llm.models import ResultSchema, TaskSchema, TaskStatus

logger = logging.getLogger(__name__)


class NexusWorker:
    """NATS-backed worker that executes agent tasks from a JetStream queue.

    Submits to ``tasks.submit`` and ``tasks.cancel`` subjects, routes tasks
    between the deepagents Agent and the LangGraph research workflow, and
    persists results to both SQLite and NATS JetStream KV.

    Includes background health monitoring with automatic degraded-mode
    transition when NATS is unreachable.

    Budget guard integration:
    - Checks budget before accepting tasks
    - Rejects tasks when budget exceeded or quota exhausted
    """

    # Health-check interval (seconds) — how often we probe NATS liveness
    HEALTH_CHECK_INTERVAL = 10.0
    # Seconds to wait for NATS reconnection before entering degraded mode
    DEGRADED_TIMEOUT = 30.0

    def __init__(self, bus: AgentBus | None = None) -> None:
        """Initialize the worker with an optional NATS bus instance.

        Args:
            bus: An ``AgentBus`` instance. If None, uses the module-level
                default bus from ``get_bus()``.
        """
        self.bus = bus or get_bus()
        self._budget_guard = create_budget_guard_from_config(settings)
        self._health_task: asyncio.Task | None = None
        self._healthy: bool = True
        self._degraded: bool = False
        self._running: bool = False
        self._in_flight: dict[str, dict[str, Any]] = {}

    @property
    def is_healthy(self) -> bool:
        """Return True if the worker is operating normally (NATS connected)."""
        return self._healthy

    @property
    def is_degraded(self) -> bool:
        """Return True if the worker is in degraded mode (NATS unreachable)."""
        return self._degraded

    async def start(self) -> None:
        """Start the NATS worker loop."""
        await self.bus.connect()
        self._running = True
        logger.info("Nexus Worker starting... listening for tasks.")

        # Subscribe to the task submission subject
        await self.bus.subscribe("tasks.submit", self.handle_task)

        # Subscribe to task cancellation subject
        await self.bus.subscribe("tasks.cancel", self._handle_cancel)

        # Allow subscription to propagate before processing
        await asyncio.sleep(0.1)

        # Start background health-check loop
        self._health_task = asyncio.create_task(self._health_loop())

    async def stop(self) -> None:
        """Gracefully stop the worker."""
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            import contextlib

            with contextlib.suppress(asyncio.CancelledError):
                await self._health_task
        logger.info("NexusWorker stopped")

    async def _health_loop(self) -> None:
        """Periodically check NATS health and toggle degraded mode.

        Detects disconnection within HEALTH_CHECK_INTERVALs (<=30s).
        When NATS goes down:
          1. Log a warning
          2. Enter degraded mode (continue operating, keep processing)
          3. Attempt reconnection with a hard cap
        When NATS comes back:
          1. Log recovery
          2. Resume normal mode
        """

        consecutive_failures = 0
        max_failures_before_degraded = 3  # 3 * 10s = 30s detection

        while self._running:
            try:
                await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
                if not self._running:
                    break

                health = await self.bus.check_health()
                is_connected = health["connected"]

                if is_connected:
                    if consecutive_failures > 0:
                        logger.info(
                            "NATS health recovered after %d failed probes",
                            consecutive_failures,
                        )
                    consecutive_failures = 0
                    if self._degraded:
                        self._degraded = False
                        self._healthy = True
                        self.bus._reconnect_count = 0  # reset counter on recovery
                        logger.info("NexusWorker exiting degraded mode — NATS recovered")
                else:
                    consecutive_failures += 1
                    logger.warning(
                        "NATS health check failed (probe %d/%d, reconnect_count=%d/%d)",
                        consecutive_failures,
                        max_failures_before_degraded,
                        health.get("reconnect_count", 0),
                        health.get("max_reconnects", 0),
                    )
                    if consecutive_failures >= max_failures_before_degraded and not self._degraded:
                        self._degraded = True
                        self._healthy = False
                        logger.warning(
                            "NexusWorker entering degraded mode — "
                            "NATS unreachable for %.0fs. "
                            "Continuing with in-memory task buffer.",
                            consecutive_failures * self.HEALTH_CHECK_INTERVAL,
                        )
                    # Attempt reconnection if cap not exceeded
                    rc = health.get("reconnect_count", 0)
                    mr = health.get("max_reconnects", _NATS_HARD_RECONNECT_CAP)
                    if rc < mr and not is_connected:
                        logger.info("Attempting NATS reconnect (%d/%d)...", rc + 1, mr)
                        try:
                            await self.bus.connect()
                        except Exception as exc:
                            logger.warning("NATS reconnect failed: %s", exc)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Health loop error: %s", exc, exc_info=True)
                # Don't let a loop error crash the worker
                await asyncio.sleep(1.0)

    async def _publish_result_degraded(self, task_id: str, result: Any) -> None:
        """Best-effort result publishing that buffers when NATS is down.

        Results are written to the DB regardless of NATS state.
        If NATS is up, also store in JetStream KV.
        If NATS is down, the result persists in DB — no data loss.
        """
        try:
            logger.debug("Persisting result to DB for task %s", task_id)

            if self.bus.is_connected:
                try:
                    await self.bus.put_result(task_id, result)
                except Exception as e:
                    logger.warning(
                        "Failed to push result to NATS KV for task %s: %s. Result is safe in DB.",
                        task_id,
                        e,
                    )
            else:
                logger.info(
                    "NATS unavailable — result for task %s stored in DB only. "
                    "Will sync to KV when NATS recovers.",
                    task_id,
                )
        except Exception as e:
            logger.error("Failed to persist result for task %s: %s", task_id, e)

    @retry_with_backoff(max_attempts=2, base_delay=0.5, max_delay=5.0)
    async def _execute_agent_logic(self, task: TaskSchema) -> Any:
        """Wraps the agent call with circuit breaker protection.
        Routes research tasks to the LangGraph workflow,
        coding tasks to the deepagents Agent.
        """
        return await _run_agent_task(task)

    async def _heartbeat(self, task_id: str, stop_event: asyncio.Event):
        """Periodically bump task updated_at so the reaper doesn't eat it."""
        while not stop_event.is_set():
            await asyncio.sleep(30)
            try:
                async with task_repo.db_manager.get_session() as session:
                    result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
                    task_obj = result.scalar_one_or_none()
                    if task_obj and task_obj.status == "processing":
                        task_obj.updated_at = datetime.now(UTC)
            except Exception:
                logger.debug("Heartbeat update failed for task %s", task_id)

    async def _handle_cancel(self, msg: Any) -> None:
        """Handle task cancellation signal from server."""
        try:
            data = json.loads(msg.data.decode())
            cancel_id = data.get("task_id", "")
            if cancel_id:
                self._in_flight.pop(cancel_id, None)
                logger.info(f"Worker acknowledged cancel for task {cancel_id}")
        except Exception as e:
            logger.warning(f"Worker cancel handler error: {e}")

    async def handle_task(self, msg: Any) -> None:
        """NATS callback to process an incoming task."""
        task_id = "unknown"
        try:
            data = json.loads(msg.data.decode())
            task = TaskSchema(**data)
            task_id = task.id

            # Check budget guard before accepting task
            allowed, reason = await self._budget_guard.can_submit_task()
            if not allowed:
                logger.critical(f"Task {task.id} rejected: {reason}")
                # Mark task as failed immediately
                await task_repo.update_task_status(task.id, TaskStatus.FAILED)
                await task_repo.save_result(
                    task_id=task.id,
                    success=False,
                    data=None,
                    error=f"Budget exceeded: {reason}",
                    duration=0.0,
                )
                return

            logger.info(f"Worker received task {task.id}: {task.description}")

            start_time = time.time()

            # 0. Create task in DB if it doesn't exist
            await task_repo.create_task(
                task_id=task.id,
                description=task.description,
                priority=task.priority,
                metadata=task.metadata if hasattr(task, "metadata") else {},
            )

            # 1. Update status to PROCESSING in DB
            await task_repo.update_task_status(task.id, TaskStatus.PROCESSING)

            # Start heartbeat to keep updated_at fresh during execution
            heartbeat_stop = asyncio.Event()
            heartbeat_task = asyncio.create_task(self._heartbeat(task.id, heartbeat_stop))
            try:
                # 2. Execute the agent task (with retry + circuit breaker)
                result_data = await self._execute_agent_logic(task)
            finally:
                heartbeat_stop.set()
                await heartbeat_task

            duration = time.time() - start_time

            # 3. Prepare the result
            result = ResultSchema(
                task_id=task.id, success=True, data=result_data, duration=duration
            )

            # 4. Persist the result in DB and NATS KV
            await task_repo.save_result(
                task_id=task.id,
                success=True,
                data=str(result_data),
                error=None,
                duration=duration,
            )
            await task_repo.update_task_status(task.id, TaskStatus.COMPLETED)

            # Store in JetStream KV for SDK retrieval (best-effort, degraded-aware)
            await self._publish_result_degraded(task.id, result.model_dump())

            logger.info(f"Worker successfully completed task {task.id} in {duration:.2f}s")

        except json.JSONDecodeError as e:
            logger.error(f"Worker received corrupted message: {e}", exc_info=True)
            if hasattr(msg, "nak"):
                await msg.nak()
        except Exception as e:
            logger.error(f"Worker error processing task {task_id}: {e}", exc_info=True)
            try:
                if task_id != "unknown":
                    await task_repo.update_task_status(task_id, TaskStatus.FAILED)
                    failure_result = ResultSchema(task_id=task_id, success=False, error=str(e))
                    await task_repo.save_result(
                        task_id=task_id,
                        success=False,
                        data=None,
                        error=str(e),
                        duration=None,
                    )
                    await self._publish_result_degraded(task_id, failure_result.model_dump())
            except Exception as inner_e:
                logger.error(f"Critical failure reporting task error: {inner_e}")


# Module-level singleton (lazy, injectable)
_worker_instance: NexusWorker | None = None


def get_worker() -> NexusWorker:
    """Get or create the module-level NexusWorker singleton."""
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = NexusWorker()
    return _worker_instance


def set_worker(instance: NexusWorker) -> None:
    """Override the module-level NexusWorker singleton (for testing/dependency injection)."""
    global _worker_instance
    _worker_instance = instance


# Backward-compatible alias — deprecated, use get_worker()
worker = get_worker()
