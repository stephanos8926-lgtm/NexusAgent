# tests/test_memory_extraction.py
"""Tests for regex-based auto memory extraction."""

import pytest

from nexusagent.memory.extraction import ExtractionResult, MemoryExtractor


@pytest.fixture
def extractor():
    return MemoryExtractor()


class TestMemoryExtractor:
    """Tests for the MemoryExtractor class."""

    def test_returns_empty_for_short_text(self, extractor):
        """Texts shorter than 20 chars should return no results."""
        assert extractor.extract("Hi") == []
        assert extractor.extract("OK thanks") == []

    def test_empty_string(self, extractor):
        assert extractor.extract("") == []

    def test_extracts_preferences(self, extractor):
        """Mentions of preferences should be extracted."""
        text = (
            "I've been working on this project for a while now. "
            "I prefer pytest over unittest. I always use type hints. "
            "I never commit directly to main. This is important."
        )
        results = extractor.extract(text)
        contents = [r.content.lower() for r in results]
        assert any("prefer pytest" in c for c in contents)
        assert any("always use type hints" in c for c in contents)
        assert any("never commit" in c for c in contents)

    def test_extracts_decisions(self, extractor):
        """Decision phrases should be extracted."""
        text = (
            "After evaluating the options, we decided to use PostgreSQL. "
            "The team chose to refactor the module. "
            "We will use async throughout the codebase."
        )
        results = extractor.extract(text)
        contents = [r.content.lower() for r in results]
        assert any("decided to use postgresql" in c for c in contents)
        assert any("chose to refactor" in c for c in contents)
        assert any("will use async" in c for c in contents)

    def test_extracts_errors(self, extractor):
        """Error/problem mentions should be extracted."""
        text = (
            "The build failed due to a missing dependency. "
            "There's a bug in the authentication flow. "
            "We need to fix the timeout issue in production."
        )
        results = extractor.extract(text)
        contents = [r.content.lower() for r in results]
        assert any("failed" in c for c in contents)
        assert any("bug" in c for c in contents)
        assert any("fix" in c for c in contents)

    def test_extracts_file_paths(self, extractor):
        """File paths should be extracted as entities."""
        text = (
            "Please look at src/nexusagent/core/agent.py and "
            "tests/test_main.py for the config. "
            "Also check docs/architecture.md for details."
        )
        results = extractor.extract(text)
        # Should have at least some file path results
        file_results = [r for r in results if "file" in r.description.lower() or "Referenced" in r.content]
        assert len(file_results) >= 2

    def test_results_have_required_fields(self, extractor):
        """All results should have the correct type and required fields."""
        text = "I prefer working with Python. We decided to use pytest. src/main.py is the entry point."
        results = extractor.extract(text)
        for r in results:
            assert isinstance(r, ExtractionResult)
            assert r.type == "observation"
            assert isinstance(r.content, str)
            assert len(r.content) > 0
            assert isinstance(r.confidence, float)
            assert 0.0 <= r.confidence <= 1.0
            assert isinstance(r.entities, list)

    def test_deduplication(self, extractor):
        """Same content should not be extracted twice."""
        text = (
            "I prefer Python. I prefer Python. "
            "I really prefer Python for everything."
        )
        results = extractor.extract(text)
        # Should deduplicate — only one preference result
        pref_results = [r for r in results if "prefer" in r.content.lower()]
        assert len(pref_results) == 1

    def test_confidence_scores(self, extractor):
        """Different extraction types should have appropriate confidence scores."""
        text = (
            "I prefer pytest. We decided to use Docker. "
            "There was a bug in the system."
        )
        results = extractor.extract(text)
        for r in results:
            if "prefer" in r.content.lower():
                assert r.confidence >= 0.8
            elif "decided" in r.content.lower():
                assert r.confidence >= 0.7

    def test_no_extraction_for_generic_text(self, extractor):
        """Generic conversation without memorable content should yield few/no results."""
        text = "Thanks for the help. Can you tell me more about this? That sounds good to me."
        results = extractor.extract(text)
        # Should extract very little or nothing from generic text
        assert len(results) <= 1


class TestExtractionResult:
    """Tests for the ExtractionResult dataclass."""

    def test_defaults(self):
        r = ExtractionResult(content="test")
        assert r.type == "observation"
        assert r.description == ""
        assert r.confidence == 0.5
        assert r.entities == []

    def test_custom_values(self):
        r = ExtractionResult(
            content="I prefer pytest",
            description="preference",
            confidence=0.85,
            entities=["pytest"],
        )
        assert r.type == "observation"
        assert r.confidence == 0.85
        assert r.entities == ["pytest"]
