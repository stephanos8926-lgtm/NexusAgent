"""Task handler — shared agent execution and research workflow.

Provides the shared execution entry point used by both NexusWorker and WorkerPool,
plus circuit breaker protection and the research/code routing logic.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from nexusagent.core.agent import run_agent_task
from nexusagent.core.subagent import SubAgentHandle
from nexusagent.infrastructure.bus import AgentBus, get_bus, _NATS_HARD_RECONNECT_CAP
from nexusagent.infrastructure.db import TaskModel, get_task_repo
from nexusagent.infrastructure.utils.circuit import CircuitBreaker
from nexusagent.infrastructure.utils.retry import retry_with_backoff
from nexusagent.llm.models import ResultSchema, TaskContract, TaskSchema, TaskStatus

task_repo = get_task_repo()  # singleton instance for module-level use

logger = logging.getLogger(__name__)

# Circuit breakers for external dependencies
_nats_breaker = CircuitBreaker("nats", failure_threshold=3, recovery_timeout=15.0)
_agent_breaker = CircuitBreaker("agent", failure_threshold=5, recovery_timeout=30.0)


async def _run_agent_task(task: TaskSchema) -> str:
    """Shared agent execution entry point.

    Routes research tasks to the LangGraph workflow and coding tasks to the
    deepagents Agent, protected by the module-level agent circuit breaker.

    Sets up workspace context (path jail, memory, NEXUS.md, environment)
    for all worker-based agents. Uses SessionLite for memory recall and
    auto-extraction when parent_memory_dir is provided in task metadata.
    """
    task_desc = task.description.lower()
    metadata = task.metadata if hasattr(task, "metadata") else {}

    # Extract working_dir from task metadata or task.working_dir field
    working_dir = metadata.get("working_dir") or getattr(task, "working_dir", None) or "."

    # Route: research tasks → LangGraph workflow, everything else → Agent
    is_research = metadata.get("mode") == "research" or any(
        kw in task_desc
        for kw in ["research", "investigate", "analyze", "deep dive", "report on"]
    )

    async with _agent_breaker:
        if is_research:
            return await _run_research_workflow(task, working_dir)
        else:
            loop = asyncio.get_running_loop()
            state = {
                "task": task.description,
                "id": task.id,
                "working_dir": working_dir,
                **metadata,
            }

            # Set up SessionLite for memory recall and extraction
            parent_memory_dir = metadata.get("parent_memory_dir")
            if parent_memory_dir or working_dir:
                try:
                    from nexusagent.core.session.session_lite import SessionLite

                    lite = SessionLite(
                        session_id=f"worker-{task.id}",
                        working_dir=working_dir,
                        parent_memory_dir=parent_memory_dir,
                    )
                    # Inject memory context into the task description
                    memory_ctx = await lite.get_memory_context(
                        task.description, max_results=5
                    )
                    if memory_ctx:
                        # Prepend memory context to task description
                        state["task"] = f"{memory_ctx}\n\n---\n\nTask: {task.description}"
                    # Store lite for post-turn extraction
                    state["_session_lite"] = lite
                except Exception as exc:
                    logger.debug("SessionLite setup failed (non-fatal): %s", exc)

            result = await loop.run_in_executor(None, run_agent_task, state)

            # Post-turn: run auto-extraction if SessionLite was set up
            session_lite = state.get("_session_lite")
            if session_lite is not None:
                try:
                    agent_result = result.get("result", "")
                    if agent_result:
                        await session_lite.extract_and_store(
                            task.description, str(agent_result)
                        )
                    await session_lite.maybe_dream()
                    await session_lite.close()
                except Exception as exc:
                    logger.debug("SessionLite post-turn failed (non-fatal): %s", exc)

            return result.get("result", "No result returned from agent.")


async def _run_research_workflow(task: TaskSchema, working_dir: str = ".") -> str:
    """Execute a research task through the LangGraph state machine."""
    from nexusagent.core.graph import create_research_graph

    # Set up workspace path jail for research agents too
    from nexusagent.tools.fs_base import set_workspace_root
    if working_dir and working_dir != ".":
        set_workspace_root(working_dir)

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
