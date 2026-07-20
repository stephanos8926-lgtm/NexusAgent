"""Integration and unit tests for the LLMRefinement synthesis layer."""

import pytest
from unittest.mock import AsyncMock

from nexusagent.memory.refinement import LLMRefinement, RefinementResult


@pytest.mark.asyncio
async def test_heuristic_synthesis_fallback():
    """Verify that heuristic fallback groups similar observations without an LLM call."""
    refinement = LLMRefinement(llm_call=None, min_observations=2)

    observations = [
        "User prefers pytest for Python projects.",
        "User prefers pytest over unittest.",
        "Completely unrelated observation about cats.",
    ]

    results = await refinement.synthesize(observations)
    assert len(results) >= 1

    # Check that the overlapping observations were merged/heuristically processed
    assert any(r.source_count > 1 for r in results)


@pytest.mark.asyncio
async def test_llm_synthesis_layer():
    """Verify that LLM-based synthesis correctly builds prompts and parses JSON responses."""
    mock_llm = AsyncMock()
    # Mock LLM returns a JSON array of insights
    mock_llm.return_value = """
    [
      {
        "content": "Synthesized: User prefers pytest for all Python development.",
        "confidence": 0.95,
        "entities": ["pytest", "python"]
      }
    ]
    """

    refinement = LLMRefinement(llm_call=mock_llm, min_observations=1)

    observations = ["User prefers pytest."]
    results = await refinement.synthesize(observations)

    assert len(results) == 1
    assert results[0].content == "Synthesized: User prefers pytest for all Python development."
    assert results[0].confidence == 0.95
    assert results[0].entities == ["pytest", "python"]

    # Verify LLM was called with expected arguments
    mock_llm.assert_called_once()
    kwargs = mock_llm.call_args[1]
    assert "User prefers pytest." in kwargs["user"]


@pytest.mark.asyncio
async def test_contradiction_detection_heuristic():
    """Verify heuristic contradiction detection between memories with low and high confidence."""
    refinement = LLMRefinement(llm_call=None)

    memories = [
        {"content": "User prefers pytest.", "entities": ["testing"], "confidence": 0.9},
        {"content": "User prefers unittest.", "entities": ["testing"], "confidence": 0.4},
    ]

    contradictions = await refinement.detect_contradictions(memories)
    assert len(contradictions) == 1
    assert contradictions[0]["entity"] == "testing"
    # Keep the higher confidence one, mark the lower confidence one for removal
    assert contradictions[0]["keep"] == 0
    assert 1 in contradictions[0]["remove"]


@pytest.mark.asyncio
async def test_contradiction_detection_llm():
    """Verify LLM-based contradiction detection is called and parsed properly."""
    mock_llm = AsyncMock()
    mock_llm.return_value = """
    {
      "has_contradiction": true,
      "resolution": "Prefer pytest as it has higher confidence.",
      "keep": 0,
      "remove": [1]
    }
    """

    refinement = LLMRefinement(llm_call=mock_llm)

    memories = [
        {"content": "User prefers pytest.", "entities": ["testing"], "confidence": 0.9},
        {"content": "User prefers unittest.", "entities": ["testing"], "confidence": 0.4},
    ]

    contradictions = await refinement.detect_contradictions(memories)
    assert len(contradictions) == 1
    assert contradictions[0]["entity"] == "testing"
    assert contradictions[0]["keep"] == 0
    assert contradictions[0]["remove"] == [1]
