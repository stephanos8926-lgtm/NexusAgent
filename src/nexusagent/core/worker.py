"""NATS-backed task execution worker and worker pool.

Provides ``NexusWorker`` (a NATS subscriber that executes agent tasks with
circuit-breaker protection, health monitoring, and degraded-mode operation)
and ``WorkerPool`` (a concurrency-limited pool that spawns isolated sub-agent
workers with turn counting and wall-time bounds).
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from nexusagent.core.agent import run_agent_task
from nexusagent.infrastructure.bus import AgentBus, get_bus, _NATS_HARD_RECONNECT_CAP
from nexusagent.infrastructure.db import TaskModel, get_task_repo
from nexusagent.llm.models import ResultSchema, TaskContract, TaskSchema, TaskStatus
from nexusagent.core.subagent import SubAgentHandle
from nexusagent.infrastructure.utils.circuit import CircuitBreaker
from nexusagent.infrastructure.utils.retry import retry_with_backoff

task_repo = get_task_repo()  # singleton instance for module-level use

logger = logging.getLogger(__name__)

# Circuit breakers for external dependencies
_nats_breaker = CircuitBreaker("nats", failure_threshold=3, recovery_timeout=15.0)
_agent_breaker = CircuitBreaker("agent", failure_threshold=5, recovery_timeout=30.0)


async def _run_agent_task(task: TaskSchema) -> str:
    """Shared agent execution entry point.

    Routes research tasks to the LangGraph workflow and coding tasks to the
    deepagents Agent, protected by the module-level agent circuit breaker.

    Both NexusWorker and WorkerPool delegate to this function so that routing
    logic, circuit-breaker protection, and the research/code split live in one
    place.
    """
    task_desc = task.description.lower()
    metadata = task.metadata if hasattr(task, "metadata") else {}

    # Route: research tasks → LangGraph workflow, everything else → Agent
    is_research = metadata.get("mode") == "research" or any(
        kw in task_desc
        for kw in ["research", "investigate", "analyze", "deep dive", "report on"]
    )

    async with _agent_breaker:
        if is_research:
            return await _run_research_workflow(task)
        else:
            loop = asyncio.get_running_loop()
            state = {"task": task.description, "id": task.id, **metadata}
            result = await loop.run_in_executor(None, run_agent_task, state)
            return result.get("result", "No result returned from agent.")


async def _run_research_workflow(task: TaskSchema) -> str:
    """Execute a research task through the LangGraph state machine."""
    from nexusagent.core.graph import create_research_graph

    graph = create_research_graph()
    config = {"configurable": {"thread_id": task.id}}

    initial_state = {
        "query": task.description,
        "template_type": "professional",
    }

    result = await graph.ainvoke(initial_state, config)
    synthesis = result.get("synthesis")
    error = result.get("error")

    if synthesis:
        return synthesis
    if error:
        return f"Research workflow error: {error}"
    return "Research workflow completed but produced no output."


class NexusWorker:
    """NATS-backed worker that executes agent tasks from a JetStream queue.

    Submits to ``tasks.submit`` and ``tasks.cancel`` subjects, routes tasks
    between the deepagents Agent and the LangGraph research workflow, and
    persists results to both SQLite and NATS JetStream KV.

    Includes background health monitoring with automatic degraded-mode
    transition when NATS becomes unreachable.
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
        """Start the NATS worker loop.
        """
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
                        "NATS health check failed "
                        "(probe %d/%d, reconnect_count=%d/%d)",
                        consecutive_failures,
                        max_failures_before_degraded,
                        health.get("reconnect_count", 0),
                        health.get("max_reconnects", 0),
                    )
                    if (
                        consecutive_failures >= max_failures_before_degraded
                        and not self._degraded
                    ):
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
                        logger.info(
                            "Attempting NATS reconnect (%d/%d)...", rc + 1, mr
                        )
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
            # Always persist to DB first (this survives NATS outages)
            logger.debug("Persisting result to DB for task %s", task_id)

            # If NATS is healthy, also push to KV
            if self.bus.is_connected:
                try:
                    await self.bus.put_result(task_id, result)
                except Exception as e:
                    logger.warning(
                        "Failed to push result to NATS KV for task %s: %s. "
                        "Result is safe in DB.",
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
            logger.error(
                "Failed to persist result for task %s: %s", task_id, e
            )

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
                    result = await session.execute(
                        select(TaskModel).where(TaskModel.id == task_id)
                    )
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
        """NATS callback to process an incoming task.
        """
        task_id = "unknown"
        try:
            # msg.data is bytes
            data = json.loads(msg.data.decode())
            task = TaskSchema(**data)
            task_id = task.id

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
            heartbeat_task = asyncio.create_task(
                self._heartbeat(task.id, heartbeat_stop)
            )
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
            # Corrupted NATS message — can't parse task data
            logger.error(f"Worker received corrupted message: {e}", exc_info=True)
            # NACK the message so it's not redelivered infinitely
            if hasattr(msg, "nak"):
                await msg.nak()
        except Exception as e:
            logger.error(f"Worker error processing task {task_id}: {e}", exc_info=True)
            try:
                if task_id != "unknown":
                    # Mark as failed in DB
                    await task_repo.update_task_status(task_id, TaskStatus.FAILED)

                    failure_result = ResultSchema(task_id=task_id, success=False, error=str(e))
                    await task_repo.save_result(
                        task_id=task_id,
                        success=False,
                        data=None,
                        error=str(e),
                        duration=None,
                    )
                    # Store failure in JetStream KV (best-effort)
                    await self._publish_result_degraded(
                        task_id, failure_result.model_dump()
                    )
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


class WorkerPool:
    """Manages a pool of isolated worker executions."""

    def __init__(self, max_workers: int = 4):
        """Initialize the worker pool with a concurrency limit.

        Args:
            max_workers: Maximum number of concurrent worker executions.
        """
        self.max_workers = max_workers
        self._active: dict[str, SubAgentHandle] = {}
        self._tasks: set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(max_workers)

    async def spawn(self, contract: TaskContract, depth: int = 0) -> SubAgentHandle:
        """Spawn an isolated worker. Returns a handle to monitor/control it.

        Args:
            contract: Task configuration including model, max_depth, summary_only.
            depth: Current nesting depth (0 = top-level). Children get depth+1.
        """
        if depth >= contract.max_depth:
            raise RuntimeError(
                f"Max sub-agent depth ({contract.max_depth}) reached. "
                f"Cannot spawn worker for task: {contract.task_id}"
            )
        worker_id = f"worker-{str(uuid.uuid4())[:8]}"
        handle = SubAgentHandle(worker_id=worker_id, contract=contract, depth=depth)
        self._active[worker_id] = handle
        task = asyncio.create_task(self._run_worker(handle))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return handle

    async def _run_worker(self, handle: SubAgentHandle):
        """Run a worker to completion within its contract bounds."""
        async with self._semaphore:
            handle._mark_running()
            try:
                # Propagate resolved model+provider into task metadata so
                # run_agent_task can forward them to Agent() without touching
                # global env vars (which would bleed across concurrent workers).
                meta = dict(handle.contract.metadata)
                meta.setdefault("agent_model", handle.model)
                meta.setdefault("agent_provider", handle.provider)
                task = TaskSchema(
                    id=handle.contract.task_id,
                    description=handle.contract.description,
                    priority=handle.contract.priority,
                    metadata=meta,
                )
                result = await self._execute_bounded(task, handle)
                if handle.is_cancelled():
                    handle._mark_failed("Cancelled by user")
                else:
                    handle._mark_completed(result)
            except Exception as e:
                handle._mark_failed(str(e))
            finally:
                # Remove from active set immediately — don't hold the slot
                self._active.pop(handle.worker_id, None)

    async def _execute_bounded(self, task, handle) -> str:
        """Execute with turn counting, wall time, and cancellation checks."""
        start = time.time()
        turn = 0
        last_result = None
        contract = handle.contract

        while turn < contract.max_turns:
            if handle.is_cancelled():
                return "Cancelled"
            elapsed = time.time() - start
            if elapsed >= contract.max_wall_time:
                return f"Timed out after {elapsed:.1f}s"
            try:
                # Build a transient TaskSchema that carries the turn/contract
                # context so the shared function can route correctly.
                turn_task = TaskSchema(
                    id=task.id,
                    description=task.description,
                    priority=task.priority,
                    metadata={
                        **task.metadata,
                        "turn": turn,
                        "max_turns": contract.max_turns,
                        "acceptance_criteria": contract.acceptance_criteria,
                        "last_result": last_result,
                    },
                )
                result = await _run_agent_task(turn_task)
                last_result = result
                # If the agent reports success or explicit completion, stop early
                if result.get("success") is True or result.get("status") == "complete":
                    return last_result
            except Exception as e:
                if contract.on_failure == "abort":
                    return f"Aborted: {e}"
                elif contract.on_failure == "retry":
                    continue
                return f"Escalated: {e}"
            turn += 1
        return f"Max turns reached. Last: {last_result}"

    def list_active(self) -> list[SubAgentHandle]:
        """Return a snapshot of all currently active sub-agent handles."""
        return list(self._active.values())


# Module-level singleton (lazy, injectable)
_worker_pool_instance: WorkerPool | None = None


def get_worker_pool() -> WorkerPool:
    """Get or create the module-level WorkerPool singleton."""
    global _worker_pool_instance
    if _worker_pool_instance is None:
        _worker_pool_instance = WorkerPool()
    return _worker_pool_instance


def set_worker_pool(instance: WorkerPool) -> None:
    """Override the module-level WorkerPool singleton (for testing/dependency injection)."""
    global _worker_pool_instance
    _worker_pool_instance = instance


# Backward-compatible alias — deprecated, use get_worker_pool()
worker_pool = get_worker_pool()
