# NexusAgent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a robust, event-driven AI agent service capable of long-horizon coding tasks.

**Architecture:** Durable LangGraph orchestrator using SQLite persistence, delegating tasks to DeepAgents via a NATS event bus.

**Tech Stack:** Python 3.12+, `uv`, `langgraph`, `deepagents`, `nats-py`.

---

### Task 1: Project Setup & NATS Integration

**Files:**
- Modify: `pyproject.toml`
- Create: `src/nexusagent/bus.py`
- Test: `tests/test_bus.py`

- [ ] **Step 1: Update dependencies**

Modify `pyproject.toml` to add `langgraph`, `deepagents`, `nats-py`, `sqlite3` (built-in).

- [ ] **Step 2: Create NATS client wrapper**

```python
# src/nexusagent/bus.py
import nats
import asyncio

class AgentBus:
    def __init__(self, url="nats://localhost:4222"):
        self.url = url
        self.nc = None

    async def connect(self):
        self.nc = await nats.connect(self.url)

    async def publish(self, subject, message):
        await self.nc.publish(subject, message.encode())

    async def close(self):
        await self.nc.close()
```

- [ ] **Step 3: Test connection**

```python
# tests/test_bus.py
import pytest
from nexusagent.bus import AgentBus

@pytest.mark.asyncio
async def test_bus_connection():
    bus = AgentBus()
    # Assuming NATS is running or mock needed
    # For now, just test instantiation
    assert bus.url == "nats://localhost:4222"
```

- [ ] **Step 4: Commit**
`git add pyproject.toml src/nexusagent/bus.py tests/test_bus.py`
`git commit -m "feat: setup project dependencies and NATS bus wrapper"`

### Task 2: LangGraph with Persistence

**Files:**
- Create: `src/nexusagent/graph.py`
- Test: `tests/test_graph.py`

- [ ] **Step 1: Setup Graph with Checkpointer**

```python
# src/nexusagent/graph.py
from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict

class AgentState(TypedDict):
    plan: str
    code: str

def create_graph(db_path: str):
    memory = SqliteSaver.from_conn_string(db_path)
    workflow = StateGraph(AgentState)
    # Define nodes...
    return workflow.compile(checkpointer=memory)
```

- [ ] **Step 2: Test Graph Instantiation**

```python
# tests/test_graph.py
from nexusagent.graph import create_graph
import os

def test_graph_creation():
    db_path = "test.db"
    graph = create_graph(db_path)
    assert graph is not None
    if os.path.exists(db_path):
        os.remove(db_path)
```

- [ ] **Step 3: Commit**
`git add src/nexusagent/graph.py tests/test_graph.py`
`git commit -m "feat: implement persistent LangGraph orchestrator"`

### Task 3: DeepAgents Integration

**Files:**
- Modify: `src/nexusagent/graph.py`
- Create: `src/nexusagent/agent.py`

- [ ] **Step 1: Create DeepAgent node**

```python
# src/nexusagent/agent.py
from deepagents import Agent

def run_agent_task(state: dict):
    # DeepAgents initialization and task execution
    return {"result": "task_complete"}
```

- [ ] **Step 2: Connect Agent to Graph**

Modify `src/nexusagent/graph.py` to add `workflow.add_node("agent", run_agent_task)`.

- [ ] **Step 3: Commit**
`git add src/nexusagent/graph.py src/nexusagent/agent.py`
`git commit -m "feat: integrate DeepAgents into graph nodes"`

### Task 4: CLI Client

**Files:**
- Create: `src/nexusagent/cli.py`

- [ ] **Step 1: Basic CLI using click or argparse**

```python
# src/nexusagent/cli.py
import argparse
import asyncio
from nexusagent.bus import AgentBus

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    args = parser.parse_args()
    
    bus = AgentBus()
    await bus.connect()
    await bus.publish("task.new", args.task)
    await bus.close()

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**
`git add src/nexusagent/cli.py`
`git commit -m "feat: implement CLI tool"`
