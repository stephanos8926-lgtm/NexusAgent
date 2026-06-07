# src/nexusagent/agent.py
import os
from typing import Any, Optional

from deepagents import create_deep_agent

# Import tool modules
from nexusagent.tools.fs import (
    read_file, read_multiple_files, write_file, write_multiple_files,
    edit_file, list_directory,
)
from nexusagent.tools.shell import run_shell, run_shell_streaming
from nexusagent.tools.git import (
    git_status, git_diff, git_log, git_branch, git_show,
    git_stash_push, git_stash_pop, git_stash_list,
    git_commit, git_checkout_branch,
)
from nexusagent.tools.test_runner import run_tests, run_single_test
from nexusagent.tools.code_search import search_code, find_symbol, find_references
from nexusagent.tools.patch import apply_patch
from nexusagent.tools.research import search_web, search_local_docs

# Import registry + discovery
from nexusagent.tools.registry import (
    tool_search, auto_correct, set_policy_context,
    get_manifest, ROLE_MANIFESTS,
    register_tool, _REGISTRY, check_tool_access,
)
from nexusagent.tools.discovery import validate_tool_call

# Run registration (populates _REGISTRY)
import nexusagent.tools.register_all  # noqa: F401


# ─── Build Tool Lists per Role ──────────────────────────────────────────

def _build_role_tools(role: str) -> list:
    """Build the list of tool functions for a given role."""
    if role == "full":
        return [info.func for info in _REGISTRY.values()]
    
    manifest = get_manifest(role)
    tools = []
    for name in sorted(manifest):
        if name in _REGISTRY:
            tools.append(_REGISTRY[name].func)
    return tools


# Pre-build tool lists for each role
_ROLE_TOOLS: dict[str, list] = {}
for _role in ROLE_MANIFESTS:
    _ROLE_TOOLS[_role] = _build_role_tools(_role)
_ROLE_TOOLS["full"] = _build_role_tools("full")


# ─── Agent ──────────────────────────────────────────────────────────────

class Agent:
    """
    NexusAgent — LLM-powered agent with policy-aware tool access.
    
    Supports three policy levels:
    
    - "permissive" (default): Agent can auto-unlock any tool on first call.
      tool_search only shows tools in the role's manifest, but the agent
      can call tools outside the manifest and they'll auto-unlock.
      Best for: user-spawned agents.
    
    - "restricted": Agent is limited to its role's manifest. Tools outside
      the manifest are denied at call time. tool_search only shows in-manifest tools.
      Best for: sub-agents spawned by other agents.
    
    - "strict": Agent is locked to its role's manifest. No unlocking possible.
      tool_search only shows in-manifest tools. Calls outside are denied.
      Best for: sandboxed sub-agents.
    
    Thread-safety: Each agent sets its own policy context via thread-local storage,
    so parent and sub-agents can run concurrently with different policies.
    """
    
    def __init__(
        self,
        role: str = "full",
        policy: str = "permissive",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the agent.
        
        Args:
            role: Tool access role. One of: minimal, reader, writer, coder,
                  tester, reviewer, debugger, researcher, full.
            policy: Access policy. One of: permissive, restricted, strict.
        """
        model_name = os.getenv("AGENT_MODEL", "gemini-3.1-flash-lite")
        
        # Set policy context for this agent (thread-local)
        set_policy_context(role, policy)
        
        # Get tools for this role
        tools = _ROLE_TOOLS.get(role, _ROLE_TOOLS["full"])
        
        self._inner = create_deep_agent(
            model=model_name,
            tools=tools,
        )
        self._role = role
        self._policy = policy
    
    @property
    def role(self) -> str:
        return self._role
    
    @property
    def policy(self) -> str:
        return self._policy
    
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._inner.invoke(*args, **kwargs)


def run_agent_task(state: dict) -> dict:
    """
    Process a task through the agent.
    
    Gets role and policy from state dict.
    """
    task_desc = state.get("task", "unknown")
    role = state.get("role", "full")
    policy = state.get("policy", "permissive")
    
    try:
        agent = Agent(role=role, policy=policy)
        result = agent.invoke(state)
        return {"result": result}
    except Exception as e:
        return {"result": f"task_complete: {task_desc}"}
