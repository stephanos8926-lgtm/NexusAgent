import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from nexusagent.graph import create_graph

def test_graph_creation():
    db_path = "test.db"
    graph = create_graph(db_path)
    assert graph is not None
    if os.path.exists(db_path):
        os.remove(db_path)

def test_graph_loop_and_research():
    db_path = "test_loop.db"
    graph = create_graph(db_path)
    state = {"plan": "test", "code": "test", "loop_count": 0, "research_done": False}
    
    # Run 5 times to trigger research
    for _ in range(5):
        state = graph.invoke(state)
        
    assert state["loop_count"] == 5
    assert state["research_done"] is True
    
    if os.path.exists(db_path):
        os.remove(db_path)
