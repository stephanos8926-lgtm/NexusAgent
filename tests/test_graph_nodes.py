"""Unit tests for the LangGraph research workflow node functions.

Covers: plan_node, refine_node, execute_node, synthesize_node
Each test patches the DeepResearchOrchestrator methods to isolate graph logic.
"""

import sys
import unittest.mock as mock
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nexusagent.graph import (
    execute_node,
    plan_node,
    refine_node,
    synthesize_node,
)
from nexusagent.orchestration import (
    DeepResearchOrchestrator,
    ResearchPlan,
    ResearchState,
    SearchResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockResponse:
    """Mimics LLMResponse with a .content attribute."""

    def __init__(self, content: str):
        self.content = content


SAMPLE_PLAN_DICT = {
    "thesis": "AI safety is critical",
    "objective": "Survey AI safety research",
    "steps": ["Search for benchmarks", "Find papers", "Look for governance"],
    "expected_outcomes": ["Benchmarks list", "Papers summary", "Governance overview"],
}

SAMPLE_PLAN = ResearchPlan(**SAMPLE_PLAN_DICT)


def _make_search_results(count: int = 2) -> list[SearchResult]:
    return [
        SearchResult(
            url=f"https://example.com/{i}",
            title=f"Result {i}",
            snippet=f"Snippet {i}",
        )
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# 1 & 2. plan_node
# ---------------------------------------------------------------------------

class TestPlanNode:
    @pytest.mark.asyncio
    @patch.object(DeepResearchOrchestrator, "_generate_plan", new_callable=AsyncMock)
    async def test_plan_node_success(self, mock_gen):
        mock_gen.return_value = SAMPLE_PLAN

        state = {"query": "AI safety research"}
        result = await plan_node(state)

        assert result["plan"] == SAMPLE_PLAN_DICT
        assert result["current_step_index"] == 0
        assert result["gathered_data"] == []
        assert result["step_results"] == []
        assert result["error"] is None
        mock_gen.assert_awaited_once_with("AI safety research")

    @pytest.mark.asyncio
    @patch.object(DeepResearchOrchestrator, "_generate_plan", new_callable=AsyncMock)
    async def test_plan_node_error(self, mock_gen):
        mock_gen.side_effect = RuntimeError("LLM unavailable")

        state = {"query": "AI safety research"}
        result = await plan_node(state)

        assert "error" in result
        assert "LLM unavailable" in result["error"]
        assert "plan" not in result


# ---------------------------------------------------------------------------
# 3, 4, 5. refine_node
# ---------------------------------------------------------------------------

class TestRefineNode:
    @pytest.mark.asyncio
    @patch.object(DeepResearchOrchestrator, "_refine_plan", new_callable=AsyncMock)
    async def test_refine_node_success(self, mock_refine):
        refined_plan = ResearchPlan(
            thesis="Refined thesis",
            objective="Refined objective",
            steps=["Refined step 1", "Refined step 2"],
            expected_outcomes=["Outcome A", "Outcome B"],
        )
        mock_refine.return_value = refined_plan

        state = {"plan": SAMPLE_PLAN_DICT}
        result = await refine_node(state)

        assert result["plan"] == refined_plan.model_dump()
        assert result["plan_approved"] is True
        assert result["error"] is None
        mock_refine.assert_awaited_once()

    @pytest.mark.asyncio
    @patch.object(DeepResearchOrchestrator, "_refine_plan", new_callable=AsyncMock)
    async def test_refine_node_error_resilience(self, mock_refine):
        """When refine fails, plan_approved should still be True (proceed with original)."""
        mock_refine.side_effect = RuntimeError("Refinement failed")

        state = {"plan": SAMPLE_PLAN_DICT}
        result = await refine_node(state)

        assert result["plan_approved"] is True
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_refine_node_no_plan(self):
        """When state has no plan, return plan_approved=False with error."""
        state = {}
        result = await refine_node(state)

        assert result["plan_approved"] is False
        assert result["error"] == "No plan to refine"


# ---------------------------------------------------------------------------
# 6, 7, 8. execute_node
# ---------------------------------------------------------------------------

class TestExecuteNode:
    @pytest.mark.asyncio
    @patch.object(DeepResearchOrchestrator, "_fetch", new_callable=AsyncMock)
    @patch.object(DeepResearchOrchestrator, "_search", new_callable=AsyncMock)
    async def test_execute_node_success(self, mock_search, mock_fetch):
        results = _make_search_results(2)
        mock_search.return_value = results
        mock_fetch.return_value = "Fetched content"

        state = {
            "plan": SAMPLE_PLAN_DICT,
            "current_step_index": 0,
            "gathered_data": [],
            "step_results": [],
        }
        result = await execute_node(state)

        assert result["current_step_index"] == 1
        assert len(result["gathered_data"]) == 2
        assert len(result["step_results"]) == 1
        assert result["step_results"][0]["step"] == "Search for benchmarks"
        assert result["step_results"][0]["index"] == 0
        assert result["step_results"][0]["num_results"] == 2
        assert result["error"] is None
        mock_search.assert_awaited_once_with("Search for benchmarks")
        assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    @patch.object(DeepResearchOrchestrator, "_search", new_callable=AsyncMock)
    async def test_execute_node_error(self, mock_search):
        """When search fails, step_index should still increment and error recorded."""
        mock_search.side_effect = RuntimeError("Search API down")

        state = {
            "plan": SAMPLE_PLAN_DICT,
            "current_step_index": 1,
            "gathered_data": [],
        }
        result = await execute_node(state)

        assert result["current_step_index"] == 2
        assert "error" in result
        assert "Step 1 failed" in result["error"]
        assert "Search API down" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_node_all_steps_done(self):
        """When current_step_index >= len(steps), return index unchanged."""
        state = {
            "plan": SAMPLE_PLAN_DICT,
            "current_step_index": 3,  # len(steps) == 3
        }
        result = await execute_node(state)

        assert result["current_step_index"] == 3


# ---------------------------------------------------------------------------
# 9, 10. synthesize_node
# ---------------------------------------------------------------------------

class TestSynthesizeNode:
    @pytest.mark.asyncio
    @patch.object(DeepResearchOrchestrator, "_synthesize_report", new_callable=AsyncMock)
    async def test_synthesize_node_success(self, mock_synth):
        mock_synth.return_value = "# Final Report\n\nThis is the synthesized report."

        state = {
            "query": "AI safety research",
            "template_type": "professional",
            "plan": SAMPLE_PLAN_DICT,
            "gathered_data": [
                {"url": "https://example.com/1", "title": "R1", "snippet": "S1"},
            ],
        }
        result = await synthesize_node(state)

        assert result["synthesis"] == "# Final Report\n\nThis is the synthesized report."
        assert result["error"] is None
        mock_synth.assert_awaited_once()

    @pytest.mark.asyncio
    @patch.object(DeepResearchOrchestrator, "_synthesize_report", new_callable=AsyncMock)
    async def test_synthesize_node_error(self, mock_synth):
        mock_synth.side_effect = RuntimeError("Synthesis failed")

        state = {
            "query": "AI safety research",
            "template_type": "professional",
            "plan": SAMPLE_PLAN_DICT,
            "gathered_data": [],
        }
        result = await synthesize_node(state)

        assert result["synthesis"] is None
        assert "error" in result
        assert "Synthesis failed" in result["error"]
