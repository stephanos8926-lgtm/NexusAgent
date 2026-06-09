"""Tests for the hybrid memory search index."""

import shutil
import tempfile
from pathlib import Path

import pytest

from nexusagent.memory_index import HybridMemoryIndex


@pytest.fixture
def tmp_index_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def populated_index(tmp_index_dir):
    """Create an index with some test data."""
    idx = HybridMemoryIndex(tmp_index_dir)

    # Write some test files
    workspace = Path(tmp_index_dir)
    (workspace / "bank").mkdir(exist_ok=True)
    (workspace / "bank" / "auth.md").write_text(
        "---\nname: Auth System\ndescription: Authentication uses JWT tokens\ntype: world\n---\n\n"
        "The authentication module uses JWT tokens for session management."
    )
    (workspace / "bank" / "testing.md").write_text(
        "---\nname: Testing\ndescription: We use pytest for testing\ntype: opinion\nconfidence: 0.9\n---\n\n"
        "We use pytest with xdist for parallel test execution."
    )

    # Index the files
    idx.index_file("bank/auth.md")
    idx.index_file("bank/testing.md")

    return idx


@pytest.mark.asyncio
async def test_keyword_search(populated_index):
    results = await populated_index.search("pytest", max_results=5)
    assert len(results) >= 1
    assert any("pytest" in r["content"].lower() for r in results)


@pytest.mark.asyncio
async def test_semantic_search(populated_index):
    # "authentication" should match "auth" semantically
    results = await populated_index.search("authentication", max_results=5)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_hybrid_merges_results(populated_index):
    results = await populated_index.search("auth tokens", max_results=5)
    # Should get results from both keyword and vector
    assert len(results) >= 1


def test_citation_format(populated_index):
    results = populated_index.search_sync("pytest", max_results=5)
    for r in results:
        assert "file" in r
        assert "content" in r
        assert "score" in r


def test_rebuild_index(tmp_index_dir):
    idx = HybridMemoryIndex(tmp_index_dir)
    workspace = Path(tmp_index_dir)
    (workspace / "bank").mkdir(exist_ok=True)
    (workspace / "bank" / "test.md").write_text("Test content about Python")

    idx.index_file("bank/test.md")
    idx.rebuild()

    results = idx.search_sync("Python", max_results=5)
    assert len(results) >= 1
