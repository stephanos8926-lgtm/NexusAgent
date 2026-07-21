# src/nexusagent/core/planner.py
"""Phase 5 — Planner for NexusAgent.

Decomposes complex objectives into structured, validated task DAGs.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from nexusagent.llm.llm import llm

logger = logging.getLogger(__name__)


class TaskNode(BaseModel):
    """A single task node in a plan DAG."""

    id: str = Field(description="Unique string identifier for the task node")
    objective: str = Field(description="The primary objective of this task")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="List of criteria required for the task to be completed successfully",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata for execution overrides (e.g. tools, model, dir)",
    )


class Plan(BaseModel):
    """The structured output of the planner containing a validated DAG of tasks."""

    goal: str = Field(description="The primary high-level objective/goal")
    tasks: list[TaskNode] = Field(description="List of tasks that form the DAG")
    dependencies: list[tuple[str, str]] = Field(
        description="Dependency edges represented as pairs (child_id, parent_id). "
        "This means child_id depends on parent_id."
    )
    global_context: dict[str, Any] = Field(
        default_factory=dict, description="Global context shared across all tasks in this plan"
    )


class PlanValidationError(ValueError):
    """Raised when a plan fails DAG validation."""


def validate_plan(plan: Plan) -> None:
    """Validates the DAG in the plan:
    - No circular dependencies
    - All dependencies reference existing tasks
    - No orphaned tasks (every task is reachable from the goal/terminal tasks)
    """
    task_ids = {t.id for t in plan.tasks}
    if not task_ids:
        raise PlanValidationError("The plan must contain at least one task.")

    # 1. All dependencies reference existing tasks
    for child, parent in plan.dependencies:
        if child not in task_ids:
            raise PlanValidationError(f"Dependency references non-existent child task: {child}")
        if parent not in task_ids:
            raise PlanValidationError(f"Dependency references non-existent parent task: {parent}")
        if child == parent:
            raise PlanValidationError(f"Self-dependency is not allowed: {child} -> {parent}")

    # Build adjacency lists
    # graph[u] = [v, ...] represents edges u -> v where u is parent and v is child (u must finish before v)
    graph: dict[str, list[str]] = {tid: [] for tid in task_ids}
    # reverse_graph[v] = [u, ...] represents incoming edges to v (v depends on u)
    reverse_graph: dict[str, list[str]] = {tid: [] for tid in task_ids}

    for child, parent in plan.dependencies:
        graph[parent].append(child)
        reverse_graph[child].append(parent)

    # 2. No circular dependencies (Cycle detection using DFS)
    visited: dict[str, int] = {tid: 0 for tid in task_ids}  # 0=unvisited, 1=visiting, 2=visited

    def has_cycle(node: str) -> bool:
        visited[node] = 1
        for child in graph[node]:
            if visited[child] == 1:
                return True
            if visited[child] == 0:
                if has_cycle(child):
                    return True
        visited[node] = 2
        return False

    for tid in task_ids:
        if visited[tid] == 0:
            if has_cycle(tid):
                raise PlanValidationError("Circular dependency detected in the task plan.")

    # 3. No orphaned tasks (Ensure the graph is fully connected when treated as undirected)
    # Disconnected nodes or components are considered orphaned/isolated.
    start_node = next(iter(task_ids))
    visited_undirected: set[str] = {start_node}
    queue_undirected = [start_node]

    # build undirected adjacency list
    undirected_graph: dict[str, set[str]] = {tid: set() for tid in task_ids}
    for child, parent in plan.dependencies:
        undirected_graph[parent].add(child)
        undirected_graph[child].add(parent)

    while queue_undirected:
        curr = queue_undirected.pop(0)
        for neighbor in undirected_graph[curr]:
            if neighbor not in visited_undirected:
                visited_undirected.add(neighbor)
                queue_undirected.append(neighbor)

    unreachable = task_ids - visited_undirected
    if unreachable:
        raise PlanValidationError(
            f"Orphaned tasks detected. These tasks are disconnected from the plan: {unreachable}"
        )


class Planner:
    """Generates and validates structured task execution DAGs from objectives."""

    async def generate_plan(self, objective: str) -> Plan:
        """Receive a high-level objective and produce a validated Plan DAG."""
        prompt = f"""Decompose this high-level objective into a structured execution plan (DAG):
        Objective: {objective}

        Each task in the plan must be independently executable with clear acceptance criteria.
        Edges represent dependencies: (child_id, parent_id). A child task cannot execute until its parent completes.

        Respond ONLY in JSON format matching this schema:
        {{
            "goal": "string",
            "tasks": [
                {{
                    "id": "task_1",
                    "objective": "task objective description",
                    "acceptance_criteria": ["criteria 1", "criteria 2"],
                    "metadata": {{}}
                }}
            ],
            "dependencies": [
                ["child_id", "parent_id"]
            ],
            "global_context": {{}}
        }}"""

        try:
            response = await llm.generate(
                prompt,
                system_prompt="You are a master system architect and planner. You only output valid JSON.",
            )
            plan = self._parse_plan_response(response.content)
            validate_plan(plan)
            return plan
        except Exception as e:
            logger.error(f"Failed to generate or validate plan for objective '{objective}': {e}")
            fallback = self._default_plan(objective)
            logger.info(f"Using fallback plan: {fallback}")
            return fallback

    def _parse_plan_response(self, content: str) -> Plan:
        """Parse LLM JSON response into a Plan model."""
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        plan_data = json.loads(json_match.group()) if json_match else json.loads(content)

        # Convert dependencies to tuples of strings
        if "dependencies" in plan_data:
            plan_data["dependencies"] = [
                (str(child), str(parent)) for child, parent in plan_data["dependencies"]
            ]

        return Plan(**plan_data)

    def _default_plan(self, objective: str) -> Plan:
        """Generate a fallback plan when LLM planning fails."""
        t1 = TaskNode(
            id="t1",
            objective=f"Analyze and research objective: {objective}",
            acceptance_criteria=["Analysis report generated"],
        )
        t2 = TaskNode(
            id="t2",
            objective=f"Execute tasks to accomplish: {objective}",
            acceptance_criteria=["Core objective features implemented"],
        )
        t3 = TaskNode(
            id="t3",
            objective=f"Verify completion of: {objective}",
            acceptance_criteria=["All tests pass successfully"],
        )
        return Plan(
            goal=objective,
            tasks=[t1, t2, t3],
            dependencies=[
                ("t2", "t1"),
                ("t3", "t2"),
            ],
            global_context={},
        )
