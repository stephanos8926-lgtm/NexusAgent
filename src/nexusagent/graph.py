import sqlite3
import asyncio
from nats.aio.client import Client as NATS
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict
from .tools.research import search_web, search_local_docs

class AgentState(TypedDict):
    plan: str
    code: str
    loop_count: int
    research_done: bool

async def push_error_to_nats(error: str):
    nc = NATS()
    try:
        await nc.connect("nats://localhost:4222")
        await nc.publish("task.error", error.encode())
        await nc.close()
    except Exception:
        pass

def research_node(state: AgentState):
    state["research_done"] = True
    state["loop_count"] = 0
    return state

def dummy_node(state: AgentState):
    # This node simply increments the loop count to simulate work/looping
    state["loop_count"] = state.get("loop_count", 0) + 1
    
    # Check for terminal failure (post-research retry exhaustion)
    if state.get("research_done", False) and state.get("loop_count", 0) > 4:
        asyncio.run(push_error_to_nats("Terminal failure after research"))
        return {"code": "terminal_failure"}
    return state

def create_graph(db_path: str):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)
    memory.setup()
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("dummy", dummy_node)
    workflow.add_node("research", research_node)
    
    # Start -> Dummy
    workflow.add_edge(START, "dummy")
    
    # Conditional edge from Dummy:
    # 1. If loop_count > 4 and research not done -> Research
    # 2. If loop_count <= 4 -> Dummy
    # 3. Else (loop_count > 4 and research_done) -> END
    workflow.add_conditional_edges(
        "dummy",
        lambda x: "research" if x.get("loop_count", 0) > 4 and not x.get("research_done", False) 
                  else "dummy" if x.get("loop_count", 0) <= 4 
                  else END,
        {"research": "research", "dummy": "dummy", END: END}
    )
    workflow.add_edge("research", "dummy")
    
    return workflow.compile(checkpointer=memory)
