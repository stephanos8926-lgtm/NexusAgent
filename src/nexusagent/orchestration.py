# src/nexusagent/orchestration.py
import logging
import asyncio
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from src.nexusagent.config import settings
from src.nexusagent.llm import llm
from src.nexusagent.tools.research import research_orchestrator, SearchResult
from src.nexusagent.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ResearchPlan(BaseModel):
    thesis: str
    objective: str
    steps: List[str]
    expected_outcomes: List[str]


class ResearchState(BaseModel):
    query: str
    plan: Optional[ResearchPlan] = None
    gathered_data: List[SearchResult] = []
    synthesis: Optional[str] = None
    current_step_index: int = 0


class DeepResearchOrchestrator:
    """
    Implements the agentic Deep Research workflow:
    Intent -> Planning -> Refinement -> Approval -> Execution -> Synthesis.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def run_deep_research(self, user_query: str, template_type: str = "professional"):
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
            logger.info(f"Executing research step {i+1}/{len(state.plan.steps)}: {step}")

            # Perform search and fetch
            results = await research_orchestrator.web_search(step, depth="deep")
            state.gathered_data.extend(results)

            # Fetch high-value pages from the results
            for res in results[:2]:
                content = await research_orchestrator.web_fetch(res.url)
                # We store enriched content back into the results
                for r in state.gathered_data:
                    if r.url == res.url:
                        r.content = content

        # 5. Final Synthesis into Report
        logger.info("Step 5: Synthesizing final report using templates...")
        state.synthesis = await self._synthesize_report(state, template_type)

        return state.synthesis

    async def _generate_plan(self, query: str) -> ResearchPlan:
        prompt = f"""The user wants to research: {query}
        Create a detailed research plan.
        Include a clear thesis, the primary objective, a sequence of 3-5 specific search queries (steps),
        and what the expected outcome of each step is.

        Respond ONLY in JSON format matching this schema:
        {
            'thesis': 'string',
            'objective': 'string',
            'steps': ['query 1', 'query 2', ...],
            'expected_outcomes': ['outcome 1', 'outcome 2', ...]
        }"""
        response = await llm.generate(prompt, system_prompt="You are a world-class research strategist.")
        # Parse JSON response from LLM
        import json
        import re
        try:
            # Try to extract JSON from response (handle cases where LLM adds extra text)
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group())
            else:
                # Fallback: try to parse the entire content as JSON
                plan_data = json.loads(response.content)
            return ResearchPlan(**plan_data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"LLM response content: {response.content}")
            # Fallback to a basic plan if parsing fails
            return ResearchPlan(
                thesis=f"Research on {query}",
                objective=f"Gather information about {query}",
                steps=[f"Search for {query}", "Analyze key aspects", "Synthesize findings"],
                expected_outcomes=["Basic information", "Key insights", "Summary"]
            )

    async def _refine_plan(self, plan: ResearchPlan) -> ResearchPlan:
        prompt = f"""Here is a proposed research plan:
        Thesis: {plan.thesis}
        Steps: {plan.steps}

        Review this plan for blind spots, redundancy, or missing perspectives.
        Refine the steps to be more precise and exhaustive.

        Respond ONLY in JSON format matching the ResearchPlan schema."""
        response = await llm.generate(prompt, system_prompt="You are a critical peer reviewer.")
        # Parse JSON response from LLM
        import json
        import re
        try:
            # Try to extract JSON from response (handle cases where LLM adds extra text)
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group())
            else:
                # Fallback: try to parse the entire content as JSON
                plan_data = json.loads(response.content)
            return ResearchPlan(**plan_data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"LLM response content: {response.content}")
            # Fallback: return the original plan if parsing fails
            return plan

    async def _synthesize_report(self, state: ResearchState, template_type: str) -> str:
        # Load the appropriate template from /src/nexusagent/templates/
        template_path = f"src/nexusagent/templates/{template_type}.md"
        try:
            with open(template_path, "r") as f:
                template = f.read()
        except FileNotFoundError:
            template = "General Report Template\n\n{content}"

        combined_evidence = "\n\n".join([f"Source: {r.url}\n{r.content}" for r in state.gathered_data])

        prompt = f"""Using the following research evidence, generate a final report following this template:

        --- TEMPLATE ---
        {template}
        ---

        EVIDENCE:
        {combined_evidence}

        Instructions: Ensure every claim is backed by a source. Use citations like [1], [2].
        Maintain a {template_type} tone."""
        response = await llm.generate(prompt, system_prompt="You are a master technical writer.")
        return response.content


# Singleton orchestrator
deep_research_orchestrator = DeepResearchOrchestrator(ToolRegistry())