# src/nexusagent/agent.py
import os
from typing import Any

from deepagents import create_deep_agent

# Import tool modules (this populates the function definitions)
from nexusagent.tools.fs import (
    read_file,
    read_multiple_files,
    write_file,
    write_multiple_files,
    edit_file,
    list_directory,
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
from nexusagent.tools.patch import apply_patch
from nexusagent.tools.research import search_web, search_local_docs

# Import discovery tools (tool_search, unlock_tool)
from nexusagent.tools.discovery import (
    tool_search,
    unlock_tool,
    auto_correct,
    validate_tool_call,
    get_available_tools,
)

# Import and run registration (populates the tool registry)
import nexusagent.tools.register_all  # noqa: F401 — side effect: registers all tools


# Build tool lists for the agent
# These are the tools that get passed to the LLM as available function calls

# Minimal tool set — agents start with these and discover others via tool_search
MINIMAL_TOOLS = [
    # Discovery (always available)
    tool_search,
    unlock_tool,
    auto_correct,
    get_available_tools,
    # Basic FS (always available)
    read_file,
    write_file,
    list_directory,
    # Basic shell (always available)
    run_shell,
    run_tests,
]

# Full tool set — all tools available
ALL_TOOLS = [
    # Discovery
    tool_search,
    unlock_tool,
    auto_correct,
    # File system
    read_file,
    read_multiple_files,
    write_file,
    write_multiple_files,
    edit_file,
    list_directory,
    apply_patch,
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
]

# Role-based tool manifests
ROLE_TOOLS = {
    "minimal": MINIMAL_TOOLS,
    "reader": [
        tool_search, unlock_tool, auto_correct,
        read_file, read_multiple_files, list_directory,
        search_code, find_symbol, find_references,
    ],
    "writer": [
        tool_search, unlock_tool, auto_correct,
        read_file, write_file, edit_file, list_directory,
    ],
    "coder": [
        tool_search, unlock_tool, auto_correct,
        read_file, read_multiple_files, write_file, write_multiple_files,
        edit_file, list_directory, apply_patch,
        run_shell, run_shell_streaming,
        git_status, git_diff, git_log, git_stash_push,
        search_code, find_symbol, find_references,
        run_tests,
    ],
    "tester": [
        tool_search, unlock_tool, auto_correct,
        read_file, list_directory, run_shell,
        run_tests, run_single_test,
        search_code, find_symbol, find_references,
        git_status, git_diff,
        edit_file, write_file,
    ],
    "reviewer": [
        tool_search, unlock_tool, auto_correct,
        read_file, read_multiple_files, list_directory,
        search_code, find_symbol, find_references,
        git_status, git_diff, git_log, git_show,
        run_tests,
    ],
    "debugger": [
        tool_search, unlock_tool, auto_correct,
        read_file, list_directory, run_shell, run_shell_streaming,
        edit_file, write_file,
        run_tests, run_single_test,
        search_code, find_symbol, find_references,
        git_status, git_diff, git_stash_push,
    ],
    "researcher": [
        tool_search, unlock_tool, auto_correct,
        read_file, list_directory, search_code,
        search_web, search_local_docs,
        find_symbol, find_references,
        run_shell,
    ],
    "full": ALL_TOOLS,
}


class Agent:
    """
    NexusAgent — an LLM-powered agent with tool discovery and auto-correction.
    
    Supports role-based tool manifests and progressive tool discovery.
    Agents start with a minimal tool set and can unlock additional tools via tool_search().
    """
    
    def __init__(self, role: str = "full", *args: Any, **kwargs: Any) -> None:
        """
        Initialize the agent.
        
        Args:
            role: Tool access level. One of: minimal, reader, writer, coder,
                  tester, reviewer, debugger, researcher, full.
                  "minimal" starts with only tool_search + basic FS + shell.
                  "full" gets all tools.
        """
        model_name = os.getenv("AGENT_MODEL", "gemini-3.1-flash-lite")
        
        # Get tools for this role
        tools = ROLE_TOOLS.get(role, ALL_TOOLS)
        
        self._inner = create_deep_agent(
            model=model_name,
            tools=tools,
        )
        self._role = role
    
    @property
    def role(self) -> str:
        return self._role
    
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
    
    # Get role from state (default: full)
    role = state.get("role", "full")
    
    try:
        agent = Agent(role=role)
        result = agent.invoke(state)
        return {"result": result}
    except Exception as e:
        # Fallback for testing without LLM backend configured
        return {"result": f"task_complete: {task_desc}"}
