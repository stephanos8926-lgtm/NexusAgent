"""
Tool registration — registers all tools in the global registry.

This module imports all tools and calls register_tool() for each one.
Import this module once at startup to populate the registry.
"""

from nexusagent.tools.code_review import review_code
from nexusagent.tools.code_search import find_references, find_symbol, search_code
from nexusagent.tools.fs import (
    edit_file,
    list_directory,
    read_file,
    read_multiple_files,
    write_file,
    write_multiple_files,
)
from nexusagent.tools.git import (
    git_branch,
    git_checkout_branch,
    git_commit,
    git_diff,
    git_log,
    git_show,
    git_stash_list,
    git_stash_pop,
    git_stash_push,
    git_status,
)
from nexusagent.tools.patch import apply_patch
from nexusagent.tools.registry import auto_correct, register_tool, tool_search
from nexusagent.tools.research import fetch_url, search_local_docs, search_web
from nexusagent.tools.shell import run_shell, run_shell_streaming
from nexusagent.tools.test_runner import run_single_test, run_tests
from nexusagent.tools.write_todos import read_todos, write_todos

# ═══════════════════════════════════════════════════════════════════════
# MCP Plugin Loader
# ═══════════════════════════════════════════════════════════════════════

_MCP_REGISTRY: dict[str, list[dict]] = {}
_MCP_REGISTERED_NAMES: set[str] = set()


async def register_mcp_tools() -> list[str]:
    """Dynamically load MCP tools from configured servers.

    Reads MCP server configuration from settings.mcp_servers (list of
    dicts with 'name', 'url', 'transport' keys) and calls each
    server's tools/list endpoint to discover available tools.

    Discovered tools are:
      1. Wrapped as async callables
      2. Registered in the global tool registry via register_tool()
      3. Added to tool_search results (category='mcp')

    Returns:
        List of newly registered tool names.
    """
    import logging

    from nexusagent.infrastructure.config import settings

    logger = logging.getLogger(__name__)
    registered: list[str] = []

    # Read MCP server configuration
    servers = getattr(settings, "mcp_servers", None)
    if not servers:
        return registered

    try:
        import httpx  # noqa: F401
    except ImportError:
        logger.warning("httpx not installed — MCP tool loading skipped")
        return registered

    for server_cfg in servers:
        server_name = server_cfg.get("name", "unknown")
        server_url = server_cfg.get("url", "")
        transport = server_cfg.get("transport", "http")

        if not server_url:
            logger.warning("MCP server '%s' has no URL — skipping", server_name)
            continue

        try:
            tool_list = await _discover_mcp_tools(
                server_name, server_url, transport
            )
        except Exception as exc:
            logger.warning(
                "Failed to discover tools from MCP server '%s': %s",
                server_name, exc,
            )
            continue

        for tool_def in tool_list:
            tool_name = tool_def.get("name", "")
            if not tool_name or tool_name in _MCP_REGISTERED_NAMES:
                continue

            _MCP_REGISTERED_NAMES.add(tool_name)
            _MCP_REGISTRY.setdefault(server_name, []).append(tool_def)
            wrapped = _wrap_mcp_tool(server_name, server_url, transport, tool_def)
            tool_description = tool_def.get("description", f"MCP tool from {server_name}")
            tool_params = _extract_param_descriptions(tool_def.get("inputSchema", {}))

            register_tool(
                name=tool_name,
                description=f"[MCP:{server_name}] {tool_description}",
                parameters=tool_params,
                example=f"{tool_name}()",
                category="mcp",
                returns="Result from MCP server.",
            )(wrapped)

            registered.append(tool_name)
            logger.info("Registered MCP tool: %s (from %s)", tool_name, server_name)

    return registered


async def _discover_mcp_tools(
    server_name: str,
    server_url: str,
    transport: str,
) -> list[dict]:
    """Call an MCP server's tools/list endpoint and return tool definitions.

    Supports both Streamable HTTP and SSE transports.
    """

    # Normalize URL
    base_url = server_url.rstrip("/")

    if transport in ("http", "streamable"):
        # MCP Streamable HTTP: POST to /tools/list
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{base_url}/tools")
                response.raise_for_status()
                data = response.json()
                return data.get("tools", [])
        except Exception:
            # Fallback: try JSON-RPC tools/list
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                }
                response = await client.post(
                    f"{base_url}/mcp",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("result", {}).get("tools", [])
    else:
        raise ValueError(f"Unsupported MCP transport: {transport}")


def _wrap_mcp_tool(
    server_name: str,
    server_url: str,
    transport: str,
    tool_def: dict,
) -> callable:
    """Return an async callable that proxies calls to an MCP tool."""
    import httpx

    base_url = server_url.rstrip("/")
    tool_name = tool_def["name"]

    async def call_mcp_tool(**kwargs):
        """Dynamically generated MCP tool proxy."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": kwargs},
                }
                response = await client.post(
                    f"{base_url}/mcp",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
                result = data.get("result", {})
                content = result.get("content", [])
                texts = [
                    c.get("text", "")
                    for c in content
                    if c.get("type") == "text"
                ]
                return "\n".join(texts) if texts else str(result)
        except Exception as exc:
            return f"[MCP:{server_name}] Error calling '{tool_name}': {exc}"

    call_mcp_tool.__name__ = tool_name
    call_mcp_tool.__doc__ = tool_def.get("description", f"MCP tool: {tool_name}")
    return call_mcp_tool


def _extract_param_descriptions(schema: dict) -> dict[str, str]:
    """Extract parameter descriptions from a JSON Schema."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    params: dict[str, str] = {}
    for pname, pdef in props.items():
        desc = pdef.get("description", pdef.get("type", "parameter"))
        if pname in required:
            desc = f"[required] {desc}"
        params[pname] = desc
    return params

# ═══════════════════════════════════════════════════════════════════════
# Discovery Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="tool_search",
    description=(
        "Search for tools available to you. "
        "Only shows tools your policy allows. "
        "Call with no args to list all available tools."
    ),
    parameters={
        "query": "Tool name or use case (empty = list all available)",
        "exact": "If True, match exact name only",
        "category": "Filter by category (fs, git, test, search, shell, web)",
        "max_results": "Maximum results (default: 5)",
    },
    example=(
        "tool_search()                              # List all available tools\n"
        'tool_search("run tests")                   # Search by use case\n'
        'tool_search("read_file", exact=True)       # Get specific tool details\n'
        'tool_search(category="git")                # List git tools'
    ),
    category="core",
    returns="Tool description, parameters, and example.",
)(tool_search)

register_tool(
    name="auto_correct",
    description=(
        "Validate a tool call before executing. "
        "Checks tool name, policy access, and parameters. "
        "Returns corrections if anything is wrong."
    ),
    parameters={
        "tool_name": "Name of the tool",
        "kwargs": "Optional dict of parameters to validate",
    },
    example='auto_correct("read_file", {"path": "main.py"})',
    category="core",
    returns="Correction message or validation confirmation.",
)(auto_correct)

# ═══════════════════════════════════════════════════════════════════════
# File System Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="read_file",
    description=(
        "Read a file's contents with optional line-range selection. Tracks files read in session."
    ),
    parameters={
        "path": "File path (absolute or relative)",
        "offset": "Starting line number (1-indexed, default: 1)",
        "limit": "Maximum number of lines to read (None = read to end)",
    },
    example='read_file("src/main.py", offset=10, limit=20)',
    category="fs",
    returns="File content as string. Line-range mode includes line numbers.",
)(read_file)

register_tool(
    name="read_multiple_files",
    description=("Read multiple files at once. Each file is marked as read in session tracking."),
    parameters={"paths": "List of file paths"},
    example='read_multiple_files(["src/main.py", "tests/test_main.py"])',
    category="fs",
    returns="Dict mapping file path to content.",
)(read_multiple_files)

register_tool(
    name="write_file",
    description=(
        "Write content to a file (full replacement). SAFETY: existing files must be read first."
    ),
    parameters={
        "path": "File path",
        "content": "Full file content to write",
    },
    example='write_file("src/main.py", "print(\'hello\')")',
    category="fs",
    returns="Success message.",
)(write_file)

register_tool(
    name="write_multiple_files",
    description=(
        "Write multiple files at once. Each file must be read first if it already exists."
    ),
    parameters={"files": "Dict mapping file path to content"},
    example='write_multiple_files({"a.py": "x=1", "b.py": "y=2"})',
    category="fs",
    returns="Success message.",
)(write_multiple_files)

register_tool(
    name="edit_file",
    description=(
        "Surgical line-range edit. Replaces exact old_text with new_text. "
        "Requires read-first. Validates old_text exists."
    ),
    parameters={
        "path": "File path",
        "old_text": "Exact text to find and replace (must match exactly)",
        "new_text": "Replacement text",
        "start_line": "Optional start line (1-indexed) to constrain search",
        "end_line": "Optional end line (1-indexed) to constrain search",
    },
    example=(
        'edit_file("src/main.py", old_text="x = 1", new_text="x = 42", start_line=10, end_line=15)'
    ),
    category="fs",
    returns="Success message with line change summary.",
)(edit_file)

register_tool(
    name="list_directory",
    description=(
        "List directory contents as a nested tree. "
        "Supports recursion, depth limits, glob patterns, and exclude filters."
    ),
    parameters={
        "path": "Directory path",
        "recursive": "Whether to recurse into subdirectories (default: False)",
        "max_depth": "Maximum recursion depth (default: 2)",
        "pattern": "Glob pattern to filter files (e.g., '*.py')",
        "exclude": "List of directory names to exclude",
    },
    example='list_directory("src/", recursive=True, max_depth=3, pattern="*.py")',
    category="fs",
    returns="Nested dict of directory structure.",
)(list_directory)

register_tool(
    name="apply_patch",
    description="Apply a unified diff patch to a file.",
    parameters={
        "path": "File to patch",
        "diff": "Unified diff content",
    },
    example='apply_patch("src/main.py", diff_content)',
    category="fs",
    returns="Success or error message.",
)(apply_patch)

# ═══════════════════════════════════════════════════════════════════════
# Shell Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="run_shell",
    description=(
        "Execute a shell command with timeout, working directory, and environment variable control."
    ),
    parameters={
        "command": "Shell command to execute",
        "workdir": "Working directory (default: cwd)",
        "env": "Additional environment variables as dict",
        "timeout": "Maximum execution time in seconds (default: 120)",
    },
    example='run_shell("ls -la", workdir="/tmp", timeout=30)',
    category="shell",
    returns="Command stdout. Errors prefixed with 'Error:'.",
)(run_shell)

register_tool(
    name="run_shell_streaming",
    description=(
        "Execute a shell command with line-by-line streaming output. "
        "Better for long-running commands."
    ),
    parameters={
        "command": "Shell command to execute",
        "workdir": "Working directory",
        "env": "Additional environment variables",
        "timeout": "Maximum execution time in seconds (default: 300)",
    },
    example='run_shell_streaming("npm install", timeout=300)',
    category="shell",
    returns="Full command output with exit code.",
)(run_shell_streaming)

# ═══════════════════════════════════════════════════════════════════════
# Git Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="git_status",
    description="Show working tree status (short format).",
    parameters={"workdir": "Repository working directory"},
    example="git_status()",
    category="git",
    returns="Short-format status output.",
)(git_status)

register_tool(
    name="git_diff",
    description=("Show changes between working tree and index/HEAD. Supports specific files."),
    parameters={
        "file_path": "Optional specific file to diff",
        "cached": "If True, show staged changes",
        "workdir": "Repository working directory",
    },
    example='git_diff(file_path="src/main.py")',
    category="git",
    returns="Unified diff output.",
)(git_diff)

register_tool(
    name="git_log",
    description="Show commit history.",
    parameters={
        "count": "Number of commits to show (default: 10)",
        "file_path": "Optional specific file to show history for",
        "oneline": "Show one commit per line (default: True)",
        "workdir": "Repository working directory",
    },
    example="git_log(count=5, oneline=True)",
    category="git",
    returns="Commit log output.",
)(git_log)

register_tool(
    name="git_branch",
    description="List branches. Current branch is marked with *.",
    parameters={"workdir": "Repository working directory"},
    example="git_branch()",
    category="git",
    returns="Branch list with current marker.",
)(git_branch)

register_tool(
    name="git_show",
    description="Show a commit's details and diff.",
    parameters={
        "commit": "Commit hash, branch name, or ref (default: HEAD)",
        "workdir": "Repository working directory",
    },
    example='git_show("HEAD")',
    category="git",
    returns="Commit details + diff stat.",
)(git_show)

register_tool(
    name="git_stash_push",
    description="Stash current changes. Write operation.",
    parameters={
        "message": "Optional stash message",
        "workdir": "Repository working directory",
    },
    example='git_stash_push(message="WIP: refactor")',
    category="git",
    returns="Stash result.",
)(git_stash_push)

register_tool(
    name="git_stash_pop",
    description="Pop the most recent stash. Write operation.",
    parameters={"workdir": "Repository working directory"},
    example="git_stash_pop()",
    category="git",
    returns="Pop result.",
)(git_stash_pop)

register_tool(
    name="git_stash_list",
    description="List stashed changes.",
    parameters={"workdir": "Repository working directory"},
    example="git_stash_list()",
    category="git",
    returns="Stash list.",
)(git_stash_list)

register_tool(
    name="git_commit",
    description="Stage and commit changes. Write operation.",
    parameters={
        "message": "Commit message",
        "files": "Optional list of specific files (default: all)",
        "workdir": "Repository working directory",
    },
    example='git_commit(message="feat: add auth module")',
    category="git",
    returns="Commit result.",
)(git_commit)

register_tool(
    name="git_checkout_branch",
    description="Checkout a branch. Optionally create it first.",
    parameters={
        "branch": "Branch name",
        "create": "If True, create the branch first (-b flag)",
        "workdir": "Repository working directory",
    },
    example='git_checkout_branch("feature/auth", create=True)',
    category="git",
    returns="Checkout result.",
)(git_checkout_branch)

# ═══════════════════════════════════════════════════════════════════════
# Test Runner Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="run_tests",
    description=(
        "Auto-detect test framework (pytest/jest/maven/gradle/go/cargo) "
        "and run tests with structured output."
    ),
    parameters={
        "workdir": "Project root directory (default: '.')",
        "test_path": "Specific test file or directory",
        "framework": "Force a specific framework",
        "timeout": "Maximum execution time (default: 300)",
    },
    example='run_tests(workdir=".", test_path="tests/")',
    category="test",
    returns="Structured test results with summary.",
)(run_tests)

register_tool(
    name="run_single_test",
    description="Run a single test file or test case.",
    parameters={
        "test_path": "Path to test file",
        "workdir": "Project root directory",
        "framework": "Force a specific framework",
        "timeout": "Maximum execution time (default: 60)",
    },
    example='run_single_test("tests/test_auth.py")',
    category="test",
    returns="Test results.",
)(run_single_test)

# ═══════════════════════════════════════════════════════════════════════
# Code Search Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="search_code",
    description=("Search code using ripgrep with context lines. Falls back to grep."),
    parameters={
        "query": "Search pattern (regex supported)",
        "path": "Directory or file to search (default: '.')",
        "file_pattern": "Glob pattern to filter files",
        "context_lines": "Context lines around each match (default: 2)",
        "max_results": "Maximum results (default: 50)",
        "case_sensitive": "Case-sensitive search (default: False)",
    },
    example='search_code("def.*auth", file_pattern="*.py", context_lines=3)',
    category="search",
    returns="Search results with file paths, line numbers, and context.",
)(search_code)

register_tool(
    name="find_symbol",
    description=("Find symbol definitions across languages (def/class/func/fn/struct/impl)."),
    parameters={
        "symbol": "Symbol name to find",
        "path": "Directory to search (default: '.')",
        "file_pattern": "Glob pattern to filter files",
    },
    example='find_symbol("UserController", file_pattern="*.py")',
    category="search",
    returns="List of symbol definitions with file paths and line numbers.",
)(find_symbol)

register_tool(
    name="find_references",
    description="Find all references to a symbol (not just definitions).",
    parameters={
        "symbol": "Symbol name",
        "path": "Directory to search (default: '.')",
        "file_pattern": "Glob pattern to filter files",
        "max_results": "Maximum results (default: 100)",
    },
    example='find_references("user_service", file_pattern="*.ts")',
    category="search",
    returns="All lines containing the symbol.",
)(find_references)

# ═══════════════════════════════════════════════════════════════════════
# Research Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="search_web",
    description="Web search with Exa primary and Tavily fallback.",
    parameters={"query": "Search query"},
    example='search_web("Python asyncio best practices")',
    category="web",
    returns="Search results with titles, URLs, and snippets.",
)(search_web)

register_tool(
    name="search_local_docs",
    description="Search local documentation using ctx7.",
    parameters={"query": "Search query"},
    example='search_local_docs("react hooks")',
    category="web",
    returns="Documentation results.",
)(search_local_docs)

register_tool(
    name="fetch_url",
    description=(
        "Fetch a URL and return the content as formatted text. "
        "Supports HTML (converted to text), JSON (pretty-printed), and plain text. "
        "Output truncated to 5000 chars max."
    ),
    parameters={"url": "HTTP or HTTPS URL to fetch"},
    example='fetch_url("https://example.com")',
    category="web",
    returns="Formatted page content as text.",
)(fetch_url)

# ═══════════════════════════════════════════════════════════════════════
# Code Review Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="review_code",
    description=(
        "Analyze code for bugs, style issues, security vulnerabilities, "
        "and performance problems. Uses static analysis (pattern matching "
        "+ AST for Python) — no LLM call required. Returns structured "
        "review with severity levels (CRITICAL, HIGH, MEDIUM, LOW, INFO)."
    ),
    parameters={
        "code": "str — the source code to review",
        "language": "str — programming language (default: 'python')",
    },
    example=(
        'review_code(code="eval(user_input)", language="python")'
    ),
    category="review",
    returns="Formatted review report with categorized issues and severity levels.",
)(review_code)

# ═══════════════════════════════════════════════════════════════════════
# Orchestration Tools
# ═══════════════════════════════════════════════════════════════════════


@register_tool(
    name="spawn_subagent",
    description=(
        "Spawn an isolated worker to handle a task autonomously. "
        "The worker runs in its own space with bounded turns and reports back. "
        "Use for delegating PRs, isolated experiments, or parallel work."
    ),
    parameters={
        "task": "str — description of the work to do",
        "working_dir": "str — directory to work in (default: current)",
        "max_turns": "int — max agent iterations (default: 15)",
        "acceptance_criteria": "list[str] — how the agent knows it's done",
        "memory_mode": "str — 'isolated' or 'scoped' (default: 'isolated')",
    },
    example=(
        'spawn_subagent(task="Fix the auth bug in server.py", max_turns=20, '
        'acceptance_criteria=["All tests pass"])'
    ),
    category="orchestration",
    returns="str — worker ID and status",
)
async def spawn_subagent(
    task: str,
    working_dir: str = ".",
    max_turns: int = 15,
    acceptance_criteria: list[str] | None = None,
    memory_mode: str = "isolated",
) -> str:
    """Spawn a sub-agent worker to execute an isolated task and return its ID."""
    from nexusagent.llm.models import MemoryScope, TaskContract
    from nexusagent.core.worker import worker_pool

    contract = TaskContract(
        task_id=f"sub-{task[:20]}",
        title=task[:50],
        working_dir=working_dir,
        description=task,
        max_turns=max_turns,
        acceptance_criteria=acceptance_criteria or ["Task completed"],
        memory_scope=(
            MemoryScope(memory_mode)
            if memory_mode in ("isolated", "scoped")
            else MemoryScope.ISOLATED
        ),
    )

    handle = await worker_pool.spawn(contract)
    return f"Spawned worker {handle.worker_id} (status: {handle.status.value})"


# ═══════════════════════════════════════════════════════════════════════
# Interaction Tools
# ═══════════════════════════════════════════════════════════════════════


@register_tool(
    name="ask_user",
    description=(
        "Ask the user a question and wait for their response. "
        "In TUI mode, shows the question in the chat. "
        "In headless mode, returns a default/fallback response. "
        "Use for confirmation, clarification, or interactive decisions."
    ),
    parameters={
        "question": "str — the question to ask the user",
        "options": "list[str] — optional list of choices (default: free-form)",
    },
    example='ask_user("Which file should we edit?", options=["main.py", "config.py", "other"])',
    category="interaction",
    returns="str — the user's response",
)
def ask_user(question: str, options: list[str] | None = None) -> str:
    """Ask the user a question. Returns their response or a fallback."""
    # In a TUI context, this would push a modal or inject a prompt
    # For headless/non-interactive mode, return a helpful fallback
    if options:
        opt_str = ", ".join(options)
        return (
            f"[ask_user] {question}\n"
            f"Options: {opt_str}\n"
            f"[No interactive session — returning default: {options[0]}]"
        )
    return f"[ask_user] {question}\n[No interactive session — please respond in the TUI]"


# ═══════════════════════════════════════════════════════════════════════
# Task Management Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="write_todos",
    description=(
        "Write a task list (todos) to a JSON file. "
        "Each todo is a dict with 'task' (required) and optional 'status', 'priority', 'notes'. "
        "Status values: pending, in_progress, done, blocked. "
        "Creates parent directories if needed."
    ),
    parameters={
        "todos": "list[dict] — list of todo dicts, each with at least 'task' key",
        "path": "str — file path for the todos JSON (default: './todos.json')",
    },
    example=(
        'write_todos(todos=['
        '{"task": "Fix auth bug", "status": "in_progress", "priority": "high"}, '
        '{"task": "Add tests", "status": "pending"}'
        '], path="./work/todos.json")'
    ),
    category="task_mgmt",
    returns="Success message with count and status breakdown.",
)(write_todos)

register_tool(
    name="read_todos",
    description=(
        "Read a task list (todos) from a JSON file. "
        "Returns list of todo dicts. "
        "Returns empty list if file doesn't exist or is invalid."
    ),
    parameters={
        "path": "str — file path for the todos JSON (default: './todos.json')",
    },
    example='read_todos(path="./work/todos.json")',
    category="task_mgmt",
    returns="list[dict] — list of todo dicts with task, status, etc.",
)(read_todos)


# ═══════════════════════════════════════════════════════════════════════
# Memory Tools
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_MEMORY_WORKSPACE = "~/.nexusagent/memory/"


def _get_memory_workspace() -> str:
    """Get (and create if needed) the default memory workspace path."""
    import os

    path = os.path.expanduser(_DEFAULT_MEMORY_WORKSPACE)
    os.makedirs(path, exist_ok=True)
    return path


@register_tool(
    name="memory_search",
    description="Search memory using hybrid keyword + vector search. Returns results with source citations.",
    parameters={
        "query": "Search query string",
        "max_results": "Maximum results to return (default: 6)",
    },
    example='memory_search("authentication", max_results=5)',
    category="memory",
    returns="Formatted search results with citations.",
)
async def memory_search(query: str, max_results: int = 6) -> str:
    """Search memory using hybrid keyword + vector search. Returns results with source citations."""
    from nexusagent.memory.memory import HybridMemoryManager

    workspace = _get_memory_workspace()
    mgr = HybridMemoryManager(workspace)
    mgr.initialize()
    results = await mgr.recall(query, max_results=max_results)
    if not results:
        return f"No memories found for: {query}"

    lines = [f"Memory search results for: {query}\n"]
    for r in results:
        source = r.get("file", "unknown")
        content = r.get("content", "").strip()
        score = r.get("score", 0)
        lines.append(f"Source: {source} (score: {score:.2f})")
        lines.append(f"{content}\n")
    return "\n".join(lines)


@register_tool(
    name="memory_get",
    description="Read a memory file by its relative path (e.g., 'bank/auth-20260712.md').",
    parameters={
        "path": "Relative path within the memory workspace",
        "offset": "Starting line number (1-indexed, default: 1)",
        "limit": "Maximum lines to read (default: 50)",
    },
    example='memory_get("bank/auth-20260712.md", offset=1, limit=50)',
    category="memory",
    returns="File content as string.",
)
def memory_get(path: str, offset: int = 1, limit: int = 50) -> str:
    """Read a memory file by its relative path (e.g., 'bank/auth-20260712.md')."""
    import os

    workspace = _get_memory_workspace()
    # Security: prevent path traversal
    full_path = os.path.realpath(os.path.join(workspace, path))
    if not full_path.startswith(os.path.realpath(workspace)):
        return "ACCESS DENIED: Path traversal detected"

    if not os.path.exists(full_path):
        return f"File not found: {path}"

    with open(full_path) as f:
        lines = f.readlines()

    start = max(0, offset - 1)
    end = min(len(lines), start + limit)
    selected = lines[start:end]

    # Add line numbers
    numbered = [f"{start + i + 1}|{line}" for i, line in enumerate(selected)]
    return "".join(numbered)


@register_tool(
    name="memory_write",
    description="Write a memory entry. Stores in bank/ directory with YAML frontmatter and indexes it.",
    parameters={
        "content": "The memory content to store",
        "type": "Entry type: world, experience, opinion, observation (default: world)",
        "description": "Short description/title for the entry",
        "confidence": "Confidence score 0.0-1.0 (optional, for opinion entries)",
        "entities": "List of entity names this relates to (optional)",
    },
    example='memory_write("The auth module uses JWT tokens", type="world", description="Auth uses JWT", entities=["auth", "jwt"])',
    category="memory",
    returns="Confirmation message with file path of the written entry.",
)
def memory_write(
    content: str,
    type: str = "world",
    description: str = "",
    confidence: float | None = None,
    entities: list[str] | None = None,
) -> str:
    """Write a memory entry. Stores in bank/ directory with YAML frontmatter and indexes it."""
    from nexusagent.memory.memory import HybridMemoryManager

    workspace = _get_memory_workspace()
    mgr = HybridMemoryManager(workspace)
    mgr.initialize()
    filepath = mgr.remember(
        content=content,
        type=type,
        description=description or content[:50],
        confidence=confidence,
        entities=entities,
    )
    return f"Memory written to: {filepath}"


@register_tool(
    name="memory_index_search",
    description=(
        "Search the hybrid memory index (FTS5 + vector similarity) directly. "
        "More powerful than memory_search — uses sqlite-vec for high-quality "
        "vector search."
    ),
    parameters={
        "query": "Search query string",
        "max_results": "Maximum results to return (default: 6)",
        "workspace": "Override workspace path (optional)",
    },
    example='memory_index_search(\"authentication flow\", max_results=5)',
    category="memory",
    returns="Formatted search results with file citations and scores.",
)
async def memory_index_search(
    query: str,
    max_results: int = 6,
    workspace: str | None = None,
) -> str:
    """Search the hybrid memory index directly using HybridMemoryIndex.search()."""
    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)
    os.makedirs(ws, exist_ok=True)

    try:
        from nexusagent.memory.index.index import HybridMemoryIndex

        idx = HybridMemoryIndex(ws)
        results = await idx.search(query, max_results=max_results)
    except Exception as exc:
        return f"Index search failed: {exc}"

    if not results:
        return f"No index results for: {query}"

    lines = [f"Index search results for: {query}\n"]
    for r in results:
        source = r.get("file", "unknown")
        content = r.get("content", "").strip()
        score = r.get("score", 0)
        lines.append(f"Source: {source} (score: {score:.4f})")
        lines.append(f"{content}\n")
    return "\n".join(lines)


@register_tool(
    name="memory_index_rebuild",
    description=(
        "Rebuild the hybrid memory index from workspace files. "
        "Drops all indexed chunks and re-scans bank/ and memory/ directories. "
        "Use after bulk file changes."
    ),
    parameters={
        "workspace": "Override workspace path (optional)",
    },
    example="memory_index_rebuild()",
    category="memory",
    returns="Confirmation message with file count.",
)
def memory_index_rebuild(workspace: str | None = None) -> str:
    """Rebuild the hybrid memory index using HybridMemoryIndex.rebuild()."""
    import os

    ws = workspace or _get_memory_workspace()
    ws = os.path.expanduser(ws)
    os.makedirs(ws, exist_ok=True)

    try:
        from nexusagent.memory.index.index import HybridMemoryIndex

        idx = HybridMemoryIndex(ws)
        idx.rebuild()
    except Exception as exc:
        return f"Index rebuild failed: {exc}"

    return f"Memory index rebuilt for workspace: {ws}"
