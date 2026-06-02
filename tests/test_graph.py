import pytest
import os
import sqlite3
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
    
    # Run the graph multiple times
    config = {"configurable": {"thread_id": "test-thread"}}
    
    # State needs to be passed in
    state = {"plan": "test", "code": "test", "loop_count": 0, "research_done": False}
    
    # Initially node is "dummy", it will run and increment loop_count
    # Run 6 times to ensure it hits > 4 loop_count
    for i in range(6):
        state = graph.invoke(state, config=config)
        
    assert state["loop_count"] >= 4
    assert state["research_done"] is True
    
    if os.path.exists(db_path):
        os.remove(db_path)
