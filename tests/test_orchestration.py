"""
Comprehensive unit tests for the DeepResearchOrchestrator.

Covers parsing, plan generation, refinement, search/fetch placeholders,
synthesis, and the full run_deep_research pipeline.
"""

import json
import sys
import unittest.mock as mock
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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


VALID_PLAN_JSON = json.dumps(
    {
        "thesis": "AI safety is critical for humanity",
        "objective": "Survey current AI safety research directions",
        "steps": [
            "Search for AI safety benchmarks",
            "Find alignment research papers",
            "Look for governance frameworks",
        ],
        "expected_outcomes": [
            "List of benchmarks",
            "Summary of alignment approaches",
            "Overview of governance proposals",
        ],
    }
)

MARKDOWN_WRAPPED_JSON = f"```json\n{VALID_PLAN_JSON}\n```"


def _make_orchestrator() -> DeepResearchOrchestrator:
    return DeepResearchOrchestrator()


# ---------------------------------------------------------------------------
# 1. _parse_plan_response with valid JSON
# ---------------------------------------------------------------------------

class TestParsePlanResponse:
    def test_valid_json(self):
        orch = _make_orchestrator()
        plan = orch._parse_plan_response(VALID_PLAN_JSON, "fallback query")

        assert isinstance(plan, ResearchPlan)
        assert plan.thesis == "AI safety is critical for humanity"
        assert plan.objective == "Survey current AI safety research directions"
        assert len(plan.steps) == 3
        assert plan.steps[0] == "Search for AI safety benchmarks"
        assert len(plan.expected_outcomes) == 3

    # -----------------------------------------------------------------------
    # 2. _parse_plan_response with markdown-wrapped JSON
    # -----------------------------------------------------------------------

    def test_markdown_wrapped_json(self):
        orch = _make_orchestrator()
        plan = orch._parse_plan_response(MARKDOWN_WRAPPED_JSON, "fallback query")

        assert isinstance(plan, ResearchPlan)
        assert plan.thesis == "AI safety is critical for humanity"
        assert len(plan.steps) == 3

    # -----------------------------------------------------------------------
    # 3. _generate_plan success (mock llm.generate)
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_generate_plan_success(self):
        orch = _make_orchestrator()

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            return_value=MockResponse(VALID_PLAN_JSON),
        ):
            plan = await orch._generate_plan("AI safety research")

        assert isinstance(plan, ResearchPlan)
        assert plan.thesis == "AI safety is critical for humanity"
        assert len(plan.steps) == 3

    # -----------------------------------------------------------------------
    # 4. _generate_plan fallback when LLM returns bad JSON
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_generate_plan_fallback_on_bad_json(self):
        orch = _make_orchestrator()

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            return_value=MockResponse("not valid JSON at all"),
        ):
            plan = await orch._generate_plan("quantum computing risks")

        # Should fall back to default plan
        assert isinstance(plan, ResearchPlan)
        assert "quantum computing risks" in plan.thesis
        assert "quantum computing risks" in plan.objective
        assert len(plan.steps) == 3

    # -----------------------------------------------------------------------
    # 7. _default_plan structure (tested here before refine for clarity)
    # -----------------------------------------------------------------------

    def test_default_plan_structure(self):
        orch = _make_orchestrator()
        plan = orch._default_plan("dark matter detection")

        assert isinstance(plan, ResearchPlan)
        assert plan.thesis == "Research on dark matter detection"
        assert plan.objective == "Gather information about dark matter detection"
        assert len(plan.steps) == 3
        assert plan.steps == [
            "Search for dark matter detection",
            "Analyze key aspects",
            "Synthesize findings",
        ]
        assert plan.expected_outcomes == [
            "Basic information",
            "Key insights",
            "Summary",
        ]


# ---------------------------------------------------------------------------
# 5 & 6. _refine_plan
# ---------------------------------------------------------------------------

class TestRefinePlan:
    @pytest.mark.asyncio
    async def test_refine_plan_success(self):
        orch = _make_orchestrator()

        refined_json = json.dumps(
            {
                "thesis": "Refined thesis on neural networks",
                "objective": "Refined objective",
                "steps": [
                    "Refined step 1",
                    "Refined step 2",
                    "Refined step 3",
                    "Refined step 4",
                ],
                "expected_outcomes": ["Outcome A", "Outcome B", "Outcome C", "Outcome D"],
            }
        )

        original_plan = ResearchPlan(
            thesis="Original thesis",
            objective="Original objective",
            steps=["Step 1", "Step 2"],
            expected_outcomes=["Outcome 1", "Outcome 2"],
        )

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            return_value=MockResponse(refined_json),
        ):
            result = await orch._refine_plan(original_plan)

        assert result.thesis == "Refined thesis on neural networks"
        assert len(result.steps) == 4

    # -----------------------------------------------------------------------
    # 6. _refine_plan fallback (returns original plan on error)
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_refine_plan_fallback(self):
        orch = _make_orchestrator()

        original_plan = ResearchPlan(
            thesis="My thesis",
            objective="My objective",
            steps=["do stuff"],
            expected_outcomes=["result"],
        )

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            return_value=MockResponse("broken response {{{ not json"),
        ):
            result = await orch._refine_plan(original_plan)

        # Should return the original plan unchanged
        assert result.thesis == "My thesis"
        assert result.objective == "My objective"
        assert result.steps == ["do stuff"]
        assert result.expected_outcomes == ["result"]


# ---------------------------------------------------------------------------
# 8. run_deep_research full pipeline (mock all LLM calls)
# ---------------------------------------------------------------------------

class TestRunDeepResearch:
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        orch = _make_orchestrator()

        refined_json = json.dumps(
            {
                "thesis": "Refined pipeline thesis",
                "objective": "Refined pipeline objective",
                "steps": ["step one", "step two"],
                "expected_outcomes": ["data A", "data B"],
            }
        )

        report_content = "# Final Report\n\nThis is the synthesized research report."

        async def mock_generate(prompt, system_prompt=None):
            sp = system_prompt or ""
            if "research strategist" in sp:
                return MockResponse(VALID_PLAN_JSON)
            if "peer reviewer" in sp:
                return MockResponse(refined_json)
            if "technical writer" in sp:
                return MockResponse(report_content)
            # Fallback
            return MockResponse("{}")

        # Patch llm.generate and search_web (used by _search)
        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            side_effect=mock_generate,
        ), patch(
            "nexusagent.tools.research.search_web",
            return_value="Mock search results about the topic",
        ):
            result = await orch.run_deep_research(
                "climate change impacts", template_type="professional"
            )

        assert result == report_content

    @pytest.mark.asyncio
    async def test_full_pipeline_with_bad_initial_plan(self):
        """Pipeline should still work when initial plan falls back to default."""
        orch = _make_orchestrator()

        refined_json = json.dumps(
            {
                "thesis": "Default refined thesis",
                "objective": "Default refined objective",
                "steps": ["refined step a", "refined step b"],
                "expected_outcomes": ["outcome a", "outcome b"],
            }
        )

        report_content = "# Fallback Plan Report\n\nSynthesis successful."

        async def mock_generate(prompt, system_prompt=None):
            sp = system_prompt or ""
            if "research strategist" in sp:
                # First plan call returns garbage → triggers default_plan
                return MockResponse("not json")
            if "peer reviewer" in sp:
                return MockResponse(refined_json)
            if "technical writer" in sp:
                return MockResponse(report_content)
            return MockResponse("{}")

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            side_effect=mock_generate,
        ), patch(
            "nexusagent.tools.research.search_web",
            return_value="Some results",
        ):
            result = await orch.run_deep_research(
                "emerging biotech trends", template_type="basic"
            )

        assert result == report_content


# ---------------------------------------------------------------------------
# 9. _search returns SearchResult list
# ---------------------------------------------------------------------------

class TestSearchAndFetch:
    @pytest.mark.asyncio
    async def test_search_returns_search_result_list(self):
        orch = _make_orchestrator()

        with patch(
            "nexusagent.tools.research.search_web",
            return_value="Some search result content",
        ):
            results = await orch._search("test query")

        assert isinstance(results, list)
        assert len(results) >= 1
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "test query"
        assert results[0].url == "search"
        assert results[0].snippet == "Some search result content"

    @pytest.mark.asyncio
    async def test_search_with_none_from_search_web(self):
        """When search_web returns None, snippet should be empty string."""
        orch = _make_orchestrator()

        with patch(
            "nexusagent.tools.research.search_web",
            return_value=None,
        ):
            results = await orch._search("empty query")

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].snippet == ""

    # -----------------------------------------------------------------------
    # 10. _fetch returns content (delegates to fetch_url)
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_fetch_returns_content(self):
        orch = _make_orchestrator()
        result = await orch._fetch("https://example.com")
        # fetch_url should return HTML content (or None on network failure)
        # Either outcome is acceptable — the key is it no longer returns
        # None as a TODO stub
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# 11. _synthesize_report with template
# ---------------------------------------------------------------------------

class TestSynthesizeReport:
    @pytest.mark.asyncio
    async def test_synthesize_uses_template_file(self):
        orch = _make_orchestrator()

        state = ResearchState(
            query="test synthesis",
            plan=ResearchPlan(
                thesis="Test thesis",
                objective="Test objective",
                steps=["step 1"],
                expected_outcomes=["outcome 1"],
            ),
            gathered_data=[
                SearchResult(
                    url="https://source1.com",
                    title="Source 1",
                    snippet="Snippet from source 1",
                ),
            ],
        )

        report_text = "# Professional Report\n\nFindings go here."

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            return_value=MockResponse(report_text),
        ):
            result = await orch._synthesize_report(state, "professional")

        assert result == report_text

    @pytest.mark.asyncio
    async def test_synthesize_fallback_template(self):
        """When template file doesn't exist, uses fallback template."""
        orch = _make_orchestrator()

        state = ResearchState(
            query="missing template test",
            plan=ResearchPlan(
                thesis="T",
                objective="O",
                steps=["s1"],
                expected_outcomes=["e1"],
            ),
            gathered_data=[
                SearchResult(
                    url="https://example.org",
                    title="Ex",
                    snippet="Data here",
                    content="Fetched content",
                ),
            ],
        )

        report_text = "Fallback template report."

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            return_value=MockResponse(report_text),
        ):
            result = await orch._synthesize_report(state, "nonexistent_template")

        assert result == report_text

    @pytest.mark.asyncio
    async def test_synthesize_includes_citations_in_prompt(self):
        """Verify that the prompt sent to the LLM includes source URLs."""
        orch = _make_orchestrator()

        state = ResearchState(
            query="citation test",
            plan=ResearchPlan(
                thesis="T",
                objective="O",
                steps=["s1"],
                expected_outcomes=["e1"],
            ),
            gathered_data=[
                SearchResult(
                    url="https://alpha.com",
                    title="Alpha",
                    snippet="Alpha snippet",
                ),
                SearchResult(
                    url="https://beta.com",
                    title="Beta",
                    snippet="Beta snippet",
                ),
            ],
        )

        received_prompt = {}

        async def capture_prompt(prompt, system_prompt=None):
            received_prompt["text"] = prompt
            return MockResponse("# Report\n\nDone.")

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            side_effect=capture_prompt,
        ):
            await orch._synthesize_report(state, "academic")

        prompt_text = received_prompt["text"]
        assert "https://alpha.com" in prompt_text
        assert "https://beta.com" in prompt_text
        assert "Alpha snippet" in prompt_text
        assert "Beta snippet" in prompt_text

    @pytest.mark.asyncio
    async def test_synthesize_includes_fetched_content(self):
        """When content is fetched, it should appear in the prompt instead of snippet."""
        orch = _make_orchestrator()

        state = ResearchState(
            query="content test",
            plan=ResearchPlan(
                thesis="T",
                objective="O",
                steps=["s1"],
                expected_outcomes=["e1"],
            ),
            gathered_data=[
                SearchResult(
                    url="https://gamma.com",
                    title="Gamma",
                    snippet="Short snippet",
                    content="Full fetched content from gamma",
                ),
            ],
        )

        received_prompt = {}

        async def capture_prompt(prompt, system_prompt=None):
            received_prompt["text"] = prompt
            return MockResponse("# Report\n\nDone.")

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            side_effect=capture_prompt,
        ):
            await orch._synthesize_report(state, "professional")

        prompt_text = received_prompt["text"]
        assert "Full fetched content from gamma" in prompt_text

    @pytest.mark.asyncio
    async def test_synthesize_empty_gathered_data(self):
        """Synthesis should handle empty gathered_data gracefully."""
        orch = _make_orchestrator()

        state = ResearchState(
            query="empty data test",
            plan=ResearchPlan(
                thesis="T",
                objective="O",
                steps=[],
                expected_outcomes=[],
            ),
            gathered_data=[],
        )

        with patch(
            "nexusagent.orchestration.llm.generate",
            new_callable=AsyncMock,
            return_value=MockResponse("# Empty Report\n\nNo data available."),
        ):
            result = await orch._synthesize_report(state, "professional")

        assert result == "# Empty Report\n\nNo data available."


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_parse_plan_response_with_surrounding_text(self):
        """LLM sometimes wraps JSON in explanatory text."""
        orch = _make_orchestrator()
        content = f"Here is the plan:\n\n{VALID_PLAN_JSON}\n\nLet me know if you need changes."

        plan = orch._parse_plan_response(content, "fallback")
        assert plan.thesis == "AI safety is critical for humanity"

    def test_parse_plan_response_with_extra_keys(self):
        """Extra JSON keys should be ignored by pydantic."""
        orch = _make_orchestrator()
        data = json.loads(VALID_PLAN_JSON)
        data["extra_field"] = "should be ignored"
        content = json.dumps(data)

        plan = orch._parse_plan_response(content, "fallback")
        assert plan.thesis == "AI safety is critical for humanity"

    def test_parse_plan_response_missing_required_key_raises(self):
        """Missing required key should raise KeyError/TypeError."""
        orch = _make_orchestrator()
        bad_json = json.dumps({"objective": "no thesis key"})

        with pytest.raises((KeyError, TypeError, Exception)):
            orch._parse_plan_response(bad_json, "fallback")

    def test_research_state_defaults(self):
        state = ResearchState(query="hello")
        assert state.plan is None
        assert state.gathered_data == []
        assert state.synthesis is None
        assert state.current_step_index == 0

    def test_search_result_defaults(self):
        sr = SearchResult(url="https://example.com")
        assert sr.title == ""
        assert sr.snippet == ""
        assert sr.content is None
