# src/nexusagent/orchestration.py
"""
Deep Research Orchestrator — multi-phase research workflow.

Implements: Intent → Planning → Refinement → Execution → Synthesis
"""
import json
import logging
import re

from pydantic import BaseModel

from nexusagent.llm import llm

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """A single search result with optional fetched content."""
    url: str
    title: str = ""
    snippet: str = ""
    content: str | None = None


class ResearchPlan(BaseModel):
    thesis: str
    objective: str
    steps: list[str]
    expected_outcomes: list[str]


class ResearchState(BaseModel):
    query: str
    plan: ResearchPlan | None = None
    gathered_data: list[SearchResult] = []
    synthesis: str | None = None
    current_step_index: int = 0


# Re-export for graph node usage
DeepResearchPlan = ResearchPlan


class DeepResearchOrchestrator:
    """
    Implements the agentic Deep Research workflow:
    Intent -> Planning -> Refinement -> Approval -> Execution -> Synthesis.
    """

    async def run_deep_research(
        self, user_query: str, template_type: str = "professional"
    ) -> str:
        state = ResearchState(query=user_query)

        # 1. Intent Extraction & Initial Planning
        logger.info("Step 1: Extracting intent and generating initial plan...")
        state.plan = await self._generate_plan(user_query)

        # 2. Plan Refinement (Single Pass)
        logger.info("Step 2: Refining research plan...")
        state.plan = await self._refine_plan(state.plan)

        # 3. User Approval (Simulated/Triggered)
        # In a real app, this would pause for a UI signal. Here we assume approval.
        logger.info("Step 3: Plan approved. Starting execution...")

        # 4. Execution Loop
        for i, step in enumerate(state.plan.steps):
            state.current_step_index = i
            logger.info(
                f"Executing research step {i + 1}/{len(state.plan.steps)}: {step}"
            )

            # Perform search using the registered search_web tool
            results = await self._search(step)

            # Fetch high-value pages from the results
            for res in results[:2]:
                content = await self._fetch(res.url)
                res.content = content

            state.gathered_data.extend(results)

        # 5. Final Synthesis into Report
        logger.info("Step 5: Synthesizing final report using templates...")
        state.synthesis = await self._synthesize_report(state, template_type)

        return state.synthesis

    async def _search(self, query: str) -> list[SearchResult]:
        """Execute a web search and return structured results."""
        from nexusagent.tools.research import search_web

        raw = search_web(query)
        # search_web returns a string — parse it into SearchResult objects
        # If it returns structured data in the future, adapt here
        return [SearchResult(url="search", title=query, snippet=raw or "")]

    async def _fetch(self, url: str) -> str | None:
        """Fetch content from a URL. TODO: implement with httpx or similar."""
        # Placeholder — for now rely on search snippets
        return None

    async def _generate_plan(self, query: str) -> ResearchPlan:
        prompt = f"""The user wants to research: {query}
        Create a detailed research plan.
        Include a clear thesis, the primary objective, a sequence of 3-5 specific search queries (steps),
        and what the expected outcome of each step is.

        Respond ONLY in JSON format matching this schema:
        {{
            "thesis": "string",
            "objective": "string",
            "steps": ["query 1", "query 2"],
            "expected_outcomes": ["outcome 1", "outcome 2"]
        }}"""
        response = await llm.generate(
            prompt, system_prompt="You are a world-class research strategist."
        )
        try:
            return self._parse_plan_response(response.content, query)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse LLM plan response: {e}")
            return self._default_plan(query)

    async def _refine_plan(self, plan: ResearchPlan) -> ResearchPlan:
        prompt = f"""Here is a proposed research plan:
        Thesis: {plan.thesis}
        Steps: {plan.steps}

        Review this plan for blind spots, redundancy, or missing perspectives.
        Refine the steps to be more precise and exhaustive.

        Respond ONLY in JSON format matching the ResearchPlan schema."""
        response = await llm.generate(
            prompt, system_prompt="You are a critical peer reviewer."
        )
        try:
            return self._parse_plan_response(response.content, plan.thesis)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse LLM refine response: {e}")
            return plan

    def _parse_plan_response(self, content: str, fallback_query: str) -> ResearchPlan:
        """Parse LLM JSON response into a ResearchPlan."""
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        plan_data = json.loads(json_match.group()) if json_match else json.loads(content)
        return ResearchPlan(**plan_data)

    def _default_plan(self, query: str) -> ResearchPlan:
        """Fallback plan when LLM parsing fails."""
        return ResearchPlan(
            thesis=f"Research on {query}",
            objective=f"Gather information about {query}",
            steps=[
                f"Search for {query}",
                "Analyze key aspects",
                "Synthesize findings",
            ],
            expected_outcomes=["Basic information", "Key insights", "Summary"],
        )

    async def _synthesize_report(self, state: ResearchState, template_type: str) -> str:
        # Load the appropriate template
        from pathlib import Path

        template_path = (
            Path(__file__).parent / "templates" / f"{template_type}.md"
        )
        try:
            template = template_path.read_text()
        except FileNotFoundError:
            template = "General Report Template\n\n{content}"

        combined_evidence = "\n\n".join(
            [
                f"Source: {r.url}\n{r.content or r.snippet}"
                for r in state.gathered_data
            ]
        )

        prompt = f"""Using the following research evidence, generate a final report following this template:

        --- TEMPLATE ---
        {template}
        ---

        EVIDENCE:
        {combined_evidence}

        Instructions: Ensure every claim is backed by a source. Use citations like [1], [2].
        Maintain a {template_type} tone."""
        response = await llm.generate(
            prompt, system_prompt="You are a master technical writer."
        )
        return response.content


# Singleton orchestrator
deep_research_orchestrator = DeepResearchOrchestrator()
