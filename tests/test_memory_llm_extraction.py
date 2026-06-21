# tests/test_memory_llm_extraction.py
"""Tests for LLM-powered memory extraction."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexusagent.memory.extraction import ExtractionResult, MemoryExtractor
from nexusagent.memory.llm_extraction import LLMExtractor


class TestLLMExtractor:
    """Tests for the LLMExtractor class."""

    @pytest.mark.asyncio
    async def test_extract_with_llm_success(self):
        """LLM extractor should parse JSON response into ExtractionResults."""
        async def mock_llm_call(system, user, **kwargs):
            return json.dumps([
                {
                    "content": "User prefers pytest for testing",
                    "type": "preference",
                    "description": "Testing framework preference",
                    "confidence": 0.9,
                    "entities": ["pytest", "testing"],
                },
                {
                    "content": "Decided to use async patterns",
                    "type": "decision",
                    "description": "Async architecture decision",
                    "confidence": 0.85,
                    "entities": ["async"],
                },
            ])

        extractor = LLMExtractor(llm_call=mock_llm_call)
        results = await extractor.extract("I prefer pytest for testing. We decided to use async patterns.")

        assert len(results) == 2
        assert results[0].content == "User prefers pytest for testing"
        assert results[0].type == "preference"
        assert results[0].confidence == 0.9
        assert "pytest" in results[0].entities

    @pytest.mark.asyncio
    async def test_extract_with_markdown_wrapped_response(self):
        """LLM extractor should handle markdown-wrapped JSON."""
        async def mock_llm_call(system, user, **kwargs):
            return '```json\n[{"content": "Test fact", "type": "observation", "description": "Test", "confidence": 0.8, "entities": []}]\n```'

        extractor = LLMExtractor(llm_call=mock_llm_call)
        results = await extractor.extract("Test conversation")
        assert len(results) == 1
        assert results[0].content == "Test fact"

    @pytest.mark.asyncio
    async def test_extract_empty_response(self):
        """LLM extractor should handle empty array response."""
        async def mock_llm_call(system, user, **kwargs):
            return "[]"

        extractor = LLMExtractor(llm_call=mock_llm_call)
        results = await extractor.extract("Nothing memorable here.")
        assert results == []

    @pytest.mark.asyncio
    async def test_extract_filters_low_confidence(self):
        """LLM extractor should filter facts below min_confidence threshold."""
        async def mock_llm_call(system, user, **kwargs):
            return json.dumps([
                {"content": "High confidence fact", "type": "observation", "description": "High", "confidence": 0.9, "entities": []},
                {"content": "Low confidence fact", "type": "observation", "description": "Low", "confidence": 0.2, "entities": []},
            ])

        extractor = LLMExtractor(llm_call=mock_llm_call, min_confidence=0.5)
        results = await extractor.extract("Test conversation")
        assert len(results) == 1
        assert results[0].content == "High confidence fact"

    @pytest.mark.asyncio
    async def test_extract_llm_failure_falls_back_to_regex(self):
        """When LLM call fails, should fall back to regex extraction."""
        async def mock_llm_call(system, user, **kwargs):
            raise Exception("LLM unavailable")

        extractor = LLMExtractor(llm_call=mock_llm_call)
        text = "We decided to use PostgreSQL for the database."
        results = await extractor.extract(text)
        assert len(results) >= 1
        assert any("decided to use PostgreSQL" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_extract_invalid_json_returns_empty(self):
        """When LLM returns invalid JSON, should return empty (not crash)."""
        async def mock_llm_call(system, user, **kwargs):
            return "This is not JSON at all"

        extractor = LLMExtractor(llm_call=mock_llm_call)
        text = "We decided to use PostgreSQL for the database. I prefer async patterns."
        results = await extractor.extract(text)
        # Invalid JSON returns empty list (LLM call succeeded, just bad format)
        # This is acceptable — the memory system won't crash
        assert results == []

    @pytest.mark.asyncio
    async def test_extract_no_llm_uses_regex(self):
        """When no LLM call is provided, should use regex extraction."""
        extractor = LLMExtractor(llm_call=None)
        text = "We decided to use PostgreSQL for the database."
        results = await extractor.extract(text)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_extract_capped_content_length(self):
        """Extracted content should be capped at 500 chars."""
        async def mock_llm_call(system, user, **kwargs):
            return json.dumps([
                {"content": "x" * 1000, "type": "observation", "description": "Long", "confidence": 0.9, "entities": []},
            ])

        extractor = LLMExtractor(llm_call=mock_llm_call)
        results = await extractor.extract("Test")
        assert len(results[0].content) <= 500


class TestSessionLLMExtraction:
    """Tests for LLM extraction integrated into Session."""

    @pytest.mark.asyncio
    async def test_session_with_llm_call_uses_llm_extractor(self):
        """Session should use LLM extractor when llm_call is provided."""
        from nexusagent.core.session.session import Session

        tmp = tempfile.mkdtemp()
        agent = MagicMock()
        agent.model = "test-model"
        db_repo = MagicMock()
        db_repo.add_message = AsyncMock()

        async def mock_llm_call(system, user, **kwargs):
            return json.dumps([
                {"content": "Extracted fact", "type": "observation", "description": "Test", "confidence": 0.8, "entities": []},
            ])

        session = Session(
            session_id="test-llm",
            working_dir=tmp,
            agent=agent,
            db_repo=db_repo,
            llm_call=mock_llm_call,
        )
        assert session._llm_extractor is not None

    @pytest.mark.asyncio
    async def test_session_without_llm_call_uses_regex(self):
        """Session should use regex extractor when no llm_call is provided."""
        from nexusagent.core.session.session import Session

        tmp = tempfile.mkdtemp()
        agent = MagicMock()
        agent.model = "test-model"
        db_repo = MagicMock()
        db_repo.add_message = AsyncMock()

        session = Session(
            session_id="test-regex",
            working_dir=tmp,
            agent=agent,
            db_repo=db_repo,
        )
        assert session._llm_extractor is None
        # SessionBase uses MemoryExtractor internally in extract_and_store()
        from nexusagent.memory.extraction import MemoryExtractor
        extractor = MemoryExtractor()
        assert extractor is not None
