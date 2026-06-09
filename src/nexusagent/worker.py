# src/nexusagent/worker.py
import asyncio
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from nexusagent.agent import run_agent_task
from nexusagent.bus import AgentBus, get_bus
from nexusagent.db import TaskModel, task_repo
from nexusagent.models import ResultSchema, TaskContract, TaskSchema, TaskStatus
from nexusagent.subagent import SubAgentHandle
from nexusagent.utils import CircuitBreaker, retry_with_backoff

logger = logging.getLogger(__name__)

# Circuit breakers for external dependencies
_nats_breaker = CircuitBreaker("nats", failure_threshold=3, recovery_timeout=15.0)
_agent_breaker = CircuitBreaker("agent", failure_threshold=5, recovery_timeout=30.0)


async def _run_agent_task(task: TaskSchema) -> str:
    """
    Shared agent execution entry point.

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
    from nexusagent.graph import create_research_graph

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
    def __init__(self, bus: AgentBus | None = None) -> None:
        self.bus = bus or get_bus()

    async def start(self) -> None:
        """
        Start the NATS worker loop.
        """
        await self.bus.connect()
        logger.info("Nexus Worker starting... listening for tasks.")

        # Subscribe to the task submission subject
        await self.bus.subscribe("tasks.submit", self.handle_task)

        # Allow subscription to propagate before processing
        await asyncio.sleep(0.1)

    @retry_with_backoff(max_attempts=2, base_delay=0.5, max_delay=5.0)
    async def _execute_agent_logic(self, task: TaskSchema) -> Any:
        """
        Wraps the agent call with circuit breaker protection.
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
                pass  # Heartbeat must never crash the worker

    async def handle_task(self, msg: Any) -> None:
        """
        NATS callback to process an incoming task.
        """
        try:
            # msg.data is bytes
            data = json.loads(msg.data.decode())
            task = TaskSchema(**data)

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

            # Store in JetStream KV for SDK retrieval
            await self.bus.put_result(task.id, result.model_dump())

            logger.info(f"Worker successfully completed task {task.id} in {duration:.2f}s")

        except Exception as e:
            logger.error(f"Worker error processing task: {e}", exc_info=True)
            try:
                # Using safe extraction of task_id from msg.data
                raw_data = json.loads(msg.data.decode())
                task_id = raw_data.get("id", "unknown")

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
                # Store failure in JetStream KV
                await self.bus.put_result(task_id, failure_result.model_dump())

            except Exception as inner_e:
                logger.error(f"Critical failure reporting task error: {inner_e}")


# Global instance
worker = NexusWorker()


class WorkerPool:
    """Manages a pool of isolated worker executions."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._active: dict[str, SubAgentHandle] = {}
        self._tasks: set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(max_workers)

    async def spawn(self, contract: TaskContract) -> SubAgentHandle:
        """Spawn an isolated worker. Returns a handle to monitor/control it."""
        worker_id = f"worker-{str(uuid.uuid4())[:8]}"
        handle = SubAgentHandle(worker_id=worker_id, contract=contract)
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
                task = TaskSchema(
                    id=handle.contract.task_id,
                    description=handle.contract.description,
                    priority=handle.contract.priority,
                    metadata=handle.contract.metadata,
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
            state = {
                "task": task.description,
                "id": task.id,
                "turn": turn,
                "max_turns": contract.max_turns,
                "acceptance_criteria": contract.acceptance_criteria,
                "last_result": last_result,
            }
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
                if result.get("status") == "complete":
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
        return list(self._active.values())


worker_pool = WorkerPool()
