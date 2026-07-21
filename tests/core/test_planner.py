# tests/core/test_planner.py
"""Unit and integration tests for the Phase 5 Planner system."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from nexusagent.core.planner import Plan, Planner, PlanValidationError, TaskNode, validate_plan


def test_valid_dag_passes() -> None:
    """Verify that a correct DAG plan is successfully validated."""
    t1 = TaskNode(id="t1", objective="Research and draft outline")
    t2 = TaskNode(id="t2", objective="Implement codebase changes")
    t3 = TaskNode(id="t3", objective="Run test cases and verify")
    t4 = TaskNode(id="t4", objective="Submit the review report")

    plan = Plan(
        goal="Complete feature deployment",
        tasks=[t1, t2, t3, t4],
        dependencies=[
            ("t2", "t1"),  # t2 depends on t1
            ("t3", "t2"),  # t3 depends on t2
            ("t4", "t3"),  # t4 depends on t3
        ],
    )
    # This should not raise any exceptions
    validate_plan(plan)


def test_empty_plan_fails() -> None:
    """Verify that empty plans fail validation."""
    plan = Plan(goal="Goal", tasks=[], dependencies=[])
    with pytest.raises(PlanValidationError, match="at least one task"):
        validate_plan(plan)


def test_missing_referenced_task_fails() -> None:
    """Verify that dependencies referencing non-existent tasks raise validation errors."""
    t1 = TaskNode(id="t1", objective="Research")
    plan = Plan(
        goal="Goal",
        tasks=[t1],
        dependencies=[("t2", "t1")],  # t2 does not exist
    )
    with pytest.raises(PlanValidationError, match="non-existent child task"):
        validate_plan(plan)

    plan2 = Plan(
        goal="Goal",
        tasks=[t1],
        dependencies=[("t1", "t3")],  # t3 does not exist
    )
    with pytest.raises(PlanValidationError, match="non-existent parent task"):
        validate_plan(plan2)


def test_self_dependency_fails() -> None:
    """Verify that self-dependencies raise validation errors."""
    t1 = TaskNode(id="t1", objective="Research")
    plan = Plan(
        goal="Goal",
        tasks=[t1],
        dependencies=[("t1", "t1")],
    )
    with pytest.raises(PlanValidationError, match="Self-dependency is not allowed"):
        validate_plan(plan)


def test_circular_dependency_fails() -> None:
    """Verify that circular dependencies are successfully detected and failed."""
    t1 = TaskNode(id="t1", objective="Research")
    t2 = TaskNode(id="t2", objective="Implement")
    t3 = TaskNode(id="t3", objective="Verify")

    plan = Plan(
        goal="Goal",
        tasks=[t1, t2, t3],
        dependencies=[
            ("t2", "t1"),
            ("t3", "t2"),
            ("t1", "t3"),  # Cycle: t1 -> t2 -> t3 -> t1
        ],
    )
    with pytest.raises(PlanValidationError, match="Circular dependency detected"):
        validate_plan(plan)


def test_orphaned_tasks_fails() -> None:
    """Verify that disconnected/orphaned tasks raise validation errors."""
    t1 = TaskNode(id="t1", objective="Research")
    t2 = TaskNode(id="t2", objective="Implement")
    t3 = TaskNode(id="t3", objective="Verify")
    # Orphaned node
    t4 = TaskNode(id="t4", objective="Write unrelated documentation")

    plan = Plan(
        goal="Goal",
        tasks=[t1, t2, t3, t4],
        dependencies=[
            ("t2", "t1"),
            ("t3", "t2"),
        ],
    )
    with pytest.raises(PlanValidationError, match="Orphaned tasks detected"):
        validate_plan(plan)


@pytest.mark.asyncio
async def test_planner_generate_plan_success() -> None:
    """Verify successful structured DAG generation and validation via Mock LLM."""
    mock_response = AsyncMock()
    mock_response.content = """
    {
        "goal": "Build prime calculator app",
        "tasks": [
            {
                "id": "t1",
                "objective": "Design UI mockup",
                "acceptance_criteria": ["Mockup images saved"]
            },
            {
                "id": "t2",
                "objective": "Write core primality check math function",
                "acceptance_criteria": ["is_prime tests pass"]
            },
            {
                "id": "t3",
                "objective": "Connect UI to prime calculation logic",
                "acceptance_criteria": ["App runs and calculates correctly"]
            }
        ],
        "dependencies": [
            ["t3", "t1"],
            ["t3", "t2"]
        ],
        "global_context": {"language": "python"}
    }
    """

    planner = Planner()
    with patch("nexusagent.core.planner.llm.generate", return_value=mock_response):
        plan = await planner.generate_plan("Build prime calculator app")

        assert plan.goal == "Build prime calculator app"
        assert len(plan.tasks) == 3
        assert plan.dependencies == [("t3", "t1"), ("t3", "t2")]
        assert plan.global_context == {"language": "python"}


@pytest.mark.asyncio
async def test_planner_fallback_on_llm_failure() -> None:
    """Verify planner reverts to standard fallback plan when LLM errors or is invalid."""
    mock_response = AsyncMock()
    mock_response.content = "Not a valid JSON response"

    planner = Planner()
    with patch("nexusagent.core.planner.llm.generate", return_value=mock_response):
        plan = await planner.generate_plan("Do something complex")

        # Reverts to fallback plan
        assert plan.goal == "Do something complex"
        assert len(plan.tasks) == 3
        assert plan.dependencies == [("t2", "t1"), ("t3", "t2")]
