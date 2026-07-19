# src/nexusagent/orchestration.py
"""Compatibility shim for orchestration module.

This module is a compatibility shim. The actual implementations live in:
- ``nexusagent.core.orchestration`` — Deep Research Orchestrator and state models

All public symbols are re-exported here for backward compatibility.
"""

from nexusagent.core.orchestration import (
    DeepResearchOrchestrator,
    ResearchPlan,
    ResearchState,
    SearchResult,
    deep_research_orchestrator,
    get_deep_research_orchestrator,
    set_deep_research_orchestrator,
)

__all__ = [
    "DeepResearchOrchestrator",
    "ResearchPlan",
    "ResearchState",
    "SearchResult",
    "deep_research_orchestrator",
    "get_deep_research_orchestrator",
    "set_deep_research_orchestrator",
]
