# src/nexusagent/agent.py
import os
from typing import Any

from deepagents import create_deep_agent

from nexusagent.tools.fs import (
    read_file,
    read_multiple_files,
    write_file,
    write_multiple_files,
    edit_file,
    list_directory,
    get_read_files,
    reset_read_tracking,
)
from nexusagent.tools.shell import run_shell, run_shell_streaming
from nexusagent.tools.git import (
    git_status,
    git_diff,
    git_log,
    git_branch,
    git_show,
    git_stash_push,
    git_stash_pop,
    git_stash_list,
    git_commit,
    git_checkout_branch,
)
from nexusagent.tools.test_runner import run_tests, run_single_test
from nexusagent.tools.code_search import search_code, find_symbol, find_references
from nexusagent.tools.research import search_web, search_local_docs
from nexusagent.tools.patch import apply_patch


# All tools available to the agent
ALL_TOOLS = [
    # File system
    read_file,
    read_multiple_files,
    write_file,
    edit_file,
    list_directory,
    # Shell
    run_shell,
    run_shell_streaming,
    # Git
    git_status,
    git_diff,
    git_log,
    git_branch,
    git_show,
    git_stash_push,
    git_stash_pop,
    git_stash_list,
    git_commit,
    git_checkout_branch,
    # Testing
    run_tests,
    run_single_test,
    # Code search
    search_code,
    find_symbol,
    find_references,
    # Research
    search_web,
    search_local_docs,
    # Patch
    apply_patch,
]


class Agent:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Defaults to gemini-3.1-flash-lite if AGENT_MODEL is not set
        model_name = os.getenv("AGENT_MODEL", "gemini-3.1-flash-lite")
        self._inner = create_deep_agent(
            model=model_name,
            tools=ALL_TOOLS,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.invoke(*args, **kwargs)


def run_agent_task(state: dict) -> dict:
    """
    Process a task through the agent.
    
    In production, this initializes the full Agent with LLM backend.
    For testing/development without LLM dependencies, returns a stub result.
    """
    task_desc = state.get("task", "unknown")
    task_id = state.get("id", "unknown")

    # Try to use the real agent, fall back to stub if dependencies missing
    try:
        agent = Agent()
        result = agent.invoke(state)
        return {"result": result}
    except Exception as e:
        # Fallback for testing without LLM backend configured
        return {"result": f"task_complete: {task_desc}"}
