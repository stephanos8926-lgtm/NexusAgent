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
