# src/nexusagent/graph.py
"""LangGraph Research Workflow — durable state machine for deep research.

Architecture:
    ┌──────────────────────────────────────────────────────────────────┐
    │  LangGraph State Machine (checkpointed, resumable)              │
    │                                                                  │
    │  START → plan → refine → [execute_loop] → synthesize → END      │
    │                            ↑          │                          │
    │                            └──────────┘ (until steps exhausted) │
    │                                                                  │
    │  Each node checkpoint after execution via SqliteSaver.           │
    │  On crash, resume from last checkpoint.                         │
    └──────────────────────────────────────────────────────────────────┘

    plan:      LLM generates a ResearchPlan (thesis, steps, outcomes)
    refine:    LLM reviews plan for blind spots, refines steps
    execute:   Runs one research step (search → fetch), increments counter
    synthesize: LLM writes final report from gathered evidence

Roles:
    This module provides the WORKFLOW (loop, branching, checkpointing).
    orchestration.py provides the RESEARCH LOGIC (LLM prompts, plan parsing).
    agent.py / deepagents provides the TOOL EXECUTION (file ops, shell, etc).
"""

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)


class ResearchGraphState(TypedDict, total=False):
    """State that flows through the graph nodes."""

    # Input
    query: str  # Original user query
    template_type: str  # Report template ("professional", "academic", etc.)

    # Planning
    plan: dict | None  # ResearchPlan as dict (thesis, steps, expected_outcomes)
    plan_approved: bool  # Whether plan passed refinement

    # Execution
    current_step_index: int  # Which plan step we're on
    step_results: list[dict]  # Accumulated search results per step
    gathered_data: list[dict]  # All gathered evidence

    # Output
    synthesis: str | None  # Final report text

    # Control
    error: str | None  # Error message if a node fails


async def plan_node(state: dict) -> dict:
    """Async node: Generate a research plan using the LLM."""
    from nexusagent.core.orchestration import DeepResearchOrchestrator

    query = state.get("query", "")
    orchestrator = DeepResearchOrchestrator()

    try:
        plan = await orchestrator._generate_plan(query)
        return {
            "plan": plan.model_dump(),
            "current_step_index": 0,
            "gathered_data": [],
            "step_results": [],
            "error": None,
        }
    except Exception as e:
        logger.error(f"Plan node failed: {e}", exc_info=True)
        return {"error": str(e)}


async def refine_node(state: dict) -> dict:
    """Async node: Refine the research plan for blind spots."""
    from nexusagent.core.orchestration import DeepResearchOrchestrator, ResearchPlan

    plan_dict = state.get("plan")
    if not plan_dict:
        return {"plan_approved": False, "error": "No plan to refine"}

    orchestrator = DeepResearchOrchestrator()

    try:
        plan = ResearchPlan(**plan_dict)
        refined = await orchestrator._refine_plan(plan)
        return {
            "plan": refined.model_dump(),
            "plan_approved": True,
            "error": None,
        }
    except Exception as e:
        logger.error(f"Refine node failed: {e}", exc_info=True)
        # If refine fails, do NOT approve the plan — return error for graph to handle
        return {"plan_approved": False, "error": str(e)}


async def execute_node(state: dict) -> dict:
    """Async node: Execute one research step (search + fetch)."""
    from nexusagent.core.orchestration import DeepResearchOrchestrator

    plan_dict = state.get("plan", {})
    steps = plan_dict.get("steps", [])
    current_index = state.get("current_step_index", 0)
    gathered = list(state.get("gathered_data", []))

    if current_index >= len(steps):
        # All steps done, move to synthesize
        return {"current_step_index": current_index}

    step = steps[current_index]
    logger.info(f"Executing research step {current_index + 1}/{len(steps)}: {step}")

    orchestrator = DeepResearchOrchestrator()

    try:
        results = await orchestrator._search(step)

        # Fetch content for top results
        for res in results[:2]:
            content = await orchestrator._fetch(res.url)
            if content:
                res.content = content

        # Accumulate
        gathered.extend([r.model_dump() for r in results])
        step_results = list(state.get("step_results", []))
        step_results.append(
            {
                "step": step,
                "index": current_index,
                "num_results": len(results),
            }
        )

        return {
            "current_step_index": current_index + 1,
            "gathered_data": gathered,
            "step_results": step_results,
            "error": None,
        }
    except Exception as e:
        logger.error(f"Execute node failed on step {current_index}: {e}", exc_info=True)
        # Skip this step and continue
        return {
            "current_step_index": current_index + 1,
            "gathered_data": gathered,
            "error": f"Step {current_index} failed: {e}",
        }


async def synthesize_node(state: dict) -> dict:
    """Async node: Synthesize all gathered evidence into a final report."""
    from nexusagent.core.orchestration import (
        DeepResearchOrchestrator,
        ResearchPlan,
        ResearchState,
        SearchResult,
    )

    query = state.get("query", "")
    template_type = state.get("template_type", "professional")
    plan_dict = state.get("plan", {})
    gathered = state.get("gathered_data", [])

    orchestrator = DeepResearchOrchestrator()

    try:
        # Reconstruct a ResearchState for the orchestrator
        plan = ResearchPlan(**plan_dict) if plan_dict else None
        results = [SearchResult(**r) for r in gathered]
        research_state = ResearchState(
            query=query,
            plan=plan,
            gathered_data=results,
        )

        synthesis = await orchestrator._synthesize_report(research_state, template_type)
        return {"synthesis": synthesis, "error": None}
    except Exception as e:
        logger.error(f"Synthesize node failed: {e}", exc_info=True)
        return {"synthesis": None, "error": str(e)}


def route_after_execute(state: dict) -> str:
    """Conditional edge: after executing a step, loop or move to synthesize."""
    plan_dict = state.get("plan", {})
    steps = plan_dict.get("steps", [])
    current_index = state.get("current_step_index", 0)

    # If plan has no steps or we've exhausted them, synthesize
    if not steps or current_index >= len(steps):
        return "synthesize"

    # If there was an error, still try next step (resilience)
    # Continue executing
    return "execute"


async def create_research_graph(db_path: str | None = None) -> Any:
    """Build and compile the research state machine.

    Args:
        db_path: Path for checkpoint SQLite DB. If None, uses in-memory.

    Returns:
        Compiled LangGraph graph ready for invocation.
    """
    # SECURITY: Validate db_path is within allowed workspace
    if db_path is not None:
        from pathlib import Path

        db_path_resolved = Path(db_path).resolve()
        workspace_root = Path.cwd().resolve()
        try:
            db_path_resolved.relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError(
                f"SECURITY: db_path '{db_path}' resolves outside workspace root"
            ) from exc

    workflow = StateGraph(dict)

    # Add nodes
    workflow.add_node("plan", plan_node)
    workflow.add_node("refine", refine_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("synthesize", synthesize_node)

    # Linear path: START → plan → refine → execute
    workflow.add_edge(START, "plan")
    workflow.add_edge("plan", "refine")
    workflow.add_edge("refine", "execute")

    # Conditional edge: execute → execute (loop) or synthesize
    workflow.add_conditional_edges(
        "execute",
        route_after_execute,
        {"execute": "execute", "synthesize": "synthesize"},
    )

    # Synthesize → END
    workflow.add_edge("synthesize", END)

    # Set up async checkpointing for durable research workflows
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with AsyncSqliteSaver.from_conn_string(db_path or ":memory:") as memory:
            await memory.setup()
            graph = workflow.compile(checkpointer=memory)
    except (ImportError, AttributeError):
        logger.info("aiosqlite not available — running without checkpointing")
        graph = workflow.compile()

    return graph
