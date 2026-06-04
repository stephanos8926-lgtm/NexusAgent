# src/nexusagent/agent.py
import os
from typing import Any

from deepagents import create_deep_agent

from nexusagent.tools.fs import read_file, write_file
from nexusagent.tools.shell import run_shell


class Agent:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Defaults to gemini-3.1-flash-lite if AGENT_MODEL is not set
        model_name = os.getenv("AGENT_MODEL", "gemini-3.1-flash-lite")
        self._inner = create_deep_agent(
            model=model_name,
            tools=[read_file, write_file, run_shell]
        )
    
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.invoke(*args, **kwargs)

# Define the task function that LangGraph nodes will call
def run_agent_task(state: dict):
    # Initialize the agent
    agent = Agent()
    # Execute the task based on the current state/plan
    # For this task, we will simulate planning/execution
    return {"result": "task_complete"}
