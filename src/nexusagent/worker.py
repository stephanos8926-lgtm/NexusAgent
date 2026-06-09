# src/nexusagent/worker.py
import asyncio
import json
import logging
import time
from typing import Any

from nexusagent.agent import run_agent_task
from nexusagent.bus import bus
from nexusagent.db import task_repo
from nexusagent.models import ResultSchema, TaskSchema, TaskStatus
from nexusagent.utils import CircuitBreaker, retry_with_backoff

logger = logging.getLogger(__name__)

# Circuit breakers for external dependencies
_nats_breaker = CircuitBreaker("nats", failure_threshold=3, recovery_timeout=15.0)
_agent_breaker = CircuitBreaker("agent", failure_threshold=5, recovery_timeout=30.0)


class NexusWorker:
    def __init__(self) -> None:
        self.bus = bus

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
        task_desc = task.description.lower()
        metadata = task.metadata if hasattr(task, "metadata") else {}

        # Route: research tasks → LangGraph workflow, everything else → Agent
        is_research = metadata.get("mode") == "research" or any(
            kw in task_desc
            for kw in ["research", "investigate", "analyze", "deep dive", "report on"]
        )

        async with _agent_breaker:
            if is_research:
                result = await self._run_research_workflow(task)
            else:
                loop = asyncio.get_running_loop()
                state = {"task": task.description, "id": task.id}
                result = await loop.run_in_executor(None, run_agent_task, state)
                result = result.get("result", "No result returned from agent.")
            return result

    async def _run_research_workflow(self, task: TaskSchema) -> str:
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

            # 2. Execute the agent task (with retry + circuit breaker)
            result_data = await self._execute_agent_logic(task)

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
