import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict

class AgentState(TypedDict):
    plan: str
    code: str

def dummy_node(state: AgentState):
    return state

def create_graph(db_path: str):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)
    workflow = StateGraph(AgentState)
    
    workflow.add_node("dummy", dummy_node)
    workflow.add_edge(START, "dummy")
    workflow.add_edge("dummy", END)
    
    return workflow.compile(checkpointer=memory)
