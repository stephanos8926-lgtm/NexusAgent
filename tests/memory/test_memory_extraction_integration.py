"""Integration tests verifying memory extraction runs and stores results after agent turns."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexusagent.core.session.session import Session


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d)


@pytest.mark.asyncio
async def test_session_extract_and_store_integration(temp_dir):
    """Verify that calling extract_and_store extracts facts and saves them to memory."""
    # Create a minimal mock agent
    agent = MagicMock()

    async def _astream(input_data, stream_mode=None, **kwargs):
        from langchain_core.messages import AIMessageChunk
        yield AIMessageChunk(content="I decided to use PostgreSQL because of scalability.")

    agent.astream = _astream

    db_repo = MagicMock()
    db_repo.add_message = AsyncMock()
    db_repo.update_status = AsyncMock()

    # Create the session
    session = Session(
        session_id="test-extraction-session",
        working_dir=str(temp_dir),
        agent=agent,
        db_repo=db_repo,
    )

    # Trigger extraction manually for a conversation turn containing a clear preference/decision
    user_msg = "What database are we using?"
    assistant_resp = "I decided to use PostgreSQL because of scalability. I prefer Python."

    # Verify that extract_and_store finds and saves these observations
    stored_count = await session.extract_and_store(user_msg, assistant_resp)
    assert stored_count >= 2  # Should extract "decided to use PostgreSQL" and "prefer Python"

    # Verify the files were created in the bank directory
    bank_dir = temp_dir / ".nexusagent" / "memory" / "bank"
    assert bank_dir.exists()
    files = list(bank_dir.glob("*.md"))
    assert len(files) >= 2

    # Verify the contents can be recalled
    results = await session.hybrid_memory.recall("PostgreSQL")
    assert len(results) >= 1
    assert any("postgresql" in r["content"].lower() for r in results)

    # Clean up the session connections
    await session.close()
