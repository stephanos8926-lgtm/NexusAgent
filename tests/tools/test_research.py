import pytest
from nexusagent.tools.research import search_web, search_local_docs
import os

# Assuming EXA_API_KEY is set in environment for testing
@pytest.mark.skipif("not os.environ.get('EXA_API_KEY')", reason="EXA_API_KEY not set")
def test_search_web():
    result = search_web("What is LangGraph?")
    assert result is not None
    assert len(result) > 0

def test_search_local_docs():
    # Assuming ctx7 is installed and available
    result = search_local_docs("How to use AgentState?")
    assert result is not None
    assert len(result) > 0
