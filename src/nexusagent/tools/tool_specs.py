"""Tool metadata registry — data-driven tool registration.

Each tool is defined as a TOOL_SPEC dict with:
    name, description, parameters, example, category, returns, func

register_all.py imports these specs and calls register_tool(**spec)(func).
Adding a new tool = add one entry to this file (or export TOOL_INFO from the tool module).
"""

from __future__ import annotations

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
from nexusagent.tools.registry import register_tool, tool_search, auto_correct
from nexusagent.tools.research import fetch_url, search_local_docs, search_web
from nexusagent.tools.shell import run_shell, run_shell_streaming
from nexusagent.tools.test_runner import run_single_test, run_tests
from nexusagent.tools.write_todos import read_todos, write_todos

# ═══════════════════════════════════════════════════════════════════════
# Tool Specifications
# ═══════════════════════════════════════════════════════════════════════
# Each spec: (name, description, parameters, example, category, returns, func)

TOOL_SPECS: list[tuple] = [
    # ── Core / Discovery ──
    (
        "tool_search",
        (
            "Search for tools available to you. "
            "Only shows tools your policy allows. "
            "Call with no args to list all available tools."
        ),
        {
            "query": "Tool name or use case (empty = list all available)",
            "exact": "If True, match exact name only",
            "category": "Filter by category (fs, git, test, search, shell, web)",
            "max_results": "Maximum results (default: 5)",
        },
        (
            "tool_search()                              # List all available tools\n"
            'tool_search("run tests")                   # Search by use case\n'
            'tool_search("read_file", exact=True)       # Get specific tool details\n'
            'tool_search(category="git")                # List git tools'
        ),
        "core",
        "Tool description, parameters, and example.",
        tool_search,
    ),
    (
        "auto_correct",
        (
            "Validate a tool call before executing. "
            "Checks tool name, policy access, and parameters. "
            "Returns corrections if anything is wrong."
        ),
        {
            "tool_name": "Name of the tool",
            "kwargs": "Optional dict of parameters to validate",
        },
        'auto_correct("read_file", {"path": "main.py"})',
        "core",
        "Correction message or validation confirmation.",
        auto_correct,
    ),
    # ── File System ──
    (
        "read_file",
        "Read a file's contents with optional line-range selection. Tracks files read in session.",
        {
            "path": "File path (absolute or relative)",
            "offset": "Starting line number (1-indexed, default: 1)",
            "limit": "Maximum number of lines to read (None = read to end)",
        },
        'read_file("src/main.py", offset=10, limit=20)',
        "fs",
        "File content as string. Line-range mode includes line numbers.",
        read_file,
    ),
    (
        "read_multiple_files",
        "Read multiple files at once. Each file is marked as read in session tracking.",
        {"paths": "List of file paths"},
        'read_multiple_files(["src/main.py", "tests/test_main.py"])',
        "fs",
        "Dict mapping file path to content.",
        read_multiple_files,
    ),
    (
        "write_file",
        "Write content to a file (full replacement). SAFETY: existing files must be read first.",
        {
            "path": "File path",
            "content": "Full file content to write",
        },
        'write_file("src/main.py", "print(\'hello\')")',
        "fs",
        "Success message.",
        write_file,
    ),
    (
        "write_multiple_files",
        "Write multiple files at once. Each file must be read first if it already exists.",
        {"files": "Dict mapping file path to content"},
        'write_multiple_files({"a.py": "x=1", "b.py": "y=2"})',
        "fs",
        "Success message.",
        write_multiple_files,
    ),
    (
        "edit_file",
        (
            "Surgical line-range edit. Replaces exact old_text with new_text. "
            "Requires read-first. Validates old_text exists."
        ),
        {
            "path": "File path",
            "old_text": "Exact text to find and replace (must match exactly)",
            "new_text": "Replacement text",
            "start_line": "Optional start line (1-indexed) to constrain search",
            "end_line": "Optional end line (1-indexed) to constrain search",
        },
        'edit_file("src/main.py", old_text="x = 1", new_text="x = 42", start_line=10, end_line=15)',
        "fs",
        "Success message with line change summary.",
        edit_file,
    ),
    (
        "list_directory",
        (
            "List directory contents as a nested tree. "
            "Supports recursion, depth limits, glob patterns, and exclude filters."
        ),
        {
            "path": "Directory path",
            "recursive": "Whether to recurse into subdirectories (default: False)",
            "max_depth": "Maximum recursion depth (default: 2)",
            "pattern": "Glob pattern to filter files (e.g., '*.py')",
            "exclude": "List of directory names to exclude",
        },
        'list_directory("src/", recursive=True, max_depth=3, pattern="*.py")',
        "fs",
        "Nested dict of directory structure.",
        list_directory,
    ),
    (
        "apply_patch",
        "Apply a unified diff patch to a file.",
        {
            "path": "File to patch",
            "diff": "Unified diff content",
        },
        'apply_patch("src/main.py", diff_content)',
        "fs",
        "Success or error message.",
        apply_patch,
    ),
    # ── Shell ──
    (
        "run_shell",
        "Execute a shell command with timeout, working directory, and environment variable control.",
        {
            "command": "Shell command to execute",
            "workdir": "Working directory (default: cwd)",
            "env": "Additional environment variables as dict",
            "timeout": "Maximum execution time in seconds (default: 120)",
        },
        'run_shell("ls -la", workdir="/tmp", timeout=30)',
        "shell",
        "Command stdout. Errors prefixed with 'Error:'.",
        run_shell,
    ),
    (
        "run_shell_streaming",
        (
            "Execute a shell command with line-by-line streaming output. "
            "Better for long-running commands."
        ),
        {
            "command": "Shell command to execute",
            "workdir": "Working directory",
            "env": "Additional environment variables",
            "timeout": "Maximum execution time in seconds (default: 300)",
        },
        'run_shell_streaming("npm install", timeout=300)',
        "shell",
        "Full command output with exit code.",
        run_shell_streaming,
    ),
    # ── Git ──
    (
        "git_status",
        "Show working tree status (short format).",
        {"workdir": "Repository working directory"},
        "git_status()",
        "git",
        "Short-format status output.",
        git_status,
    ),
    (
        "git_diff",
        "Show changes between working tree and index/HEAD. Supports specific files.",
        {
            "file_path": "Optional specific file to diff",
            "cached": "If True, show staged changes",
            "workdir": "Repository working directory",
        },
        'git_diff(file_path="src/main.py")',
        "git",
        "Unified diff output.",
        git_diff,
    ),
    (
        "git_log",
        "Show commit history.",
        {
            "count": "Number of commits to show (default: 10)",
            "file_path": "Optional specific file to show history for",
            "oneline": "Show one commit per line (default: True)",
            "workdir": "Repository working directory",
        },
        "git_log(count=5, oneline=True)",
        "git",
        "Commit log output.",
        git_log,
    ),
    (
        "git_branch",
        "List branches. Current branch is marked with *.",
        {"workdir": "Repository working directory"},
        "git_branch()",
        "git",
        "Branch list with current marker.",
        git_branch,
    ),
    (
        "git_show",
        "Show a commit's details and diff.",
        {
            "commit": "Commit hash, branch name, or ref (default: HEAD)",
            "workdir": "Repository working directory",
        },
        'git_show("HEAD")',
        "git",
        "Commit details + diff stat.",
        git_show,
    ),
    (
        "git_stash_push",
        "Stash current changes. Write operation.",
        {
            "message": "Optional stash message",
            "workdir": "Repository working directory",
        },
        'git_stash_push(message="WIP: refactor")',
        "git",
        "Stash result.",
        git_stash_push,
    ),
    (
        "git_stash_pop",
        "Pop the most recent stash. Write operation.",
        {"workdir": "Repository working directory"},
        "git_stash_pop()",
        "git",
        "Pop result.",
        git_stash_pop,
    ),
    (
        "git_stash_list",
        "List stashed changes.",
        {"workdir": "Repository working directory"},
        "git_stash_list()",
        "git",
        "Stash list.",
        git_stash_list,
    ),
    (
        "git_commit",
        "Stage and commit changes. Write operation.",
        {
            "message": "Commit message",
            "files": "Optional list of specific files (default: all)",
            "workdir": "Repository working directory",
        },
        'git_commit(message="feat: add auth module")',
        "git",
        "Commit result.",
        git_commit,
    ),
    (
        "git_checkout_branch",
        "Checkout a branch. Optionally create it first.",
        {
            "branch": "Branch name",
            "create": "If True, create the branch first (-b flag)",
            "workdir": "Repository working directory",
        },
        'git_checkout_branch("feature/auth", create=True)',
        "git",
        "Checkout result.",
        git_checkout_branch,
    ),
    # ── Test Runner ──
    (
        "run_tests",
        (
            "Auto-detect test framework (pytest/jest/maven/gradle/go/cargo) "
            "and run tests with structured output."
        ),
        {
            "workdir": "Project root directory (default: '.')",
            "test_path": "Specific test file or directory",
            "framework": "Force a specific framework",
            "timeout": "Maximum execution time (default: 300)",
        },
        'run_tests(workdir=".", test_path="tests/")',
        "test",
        "Structured test results with summary.",
        run_tests,
    ),
    (
        "run_single_test",
        "Run a single test file or test case.",
        {
            "test_path": "Path to test file",
            "workdir": "Project root directory",
            "framework": "Force a specific framework",
            "timeout": "Maximum execution time (default: 60)",
        },
        'run_single_test("tests/test_auth.py")',
        "test",
        "Test results.",
        run_single_test,
    ),
    # ── Code Search ──
    (
        "search_code",
        "Search code using ripgrep with context lines. Falls back to grep.",
        {
            "query": "Search pattern (regex supported)",
            "path": "Directory or file to search (default: '.')",
            "file_pattern": "Glob pattern to filter files",
            "context_lines": "Context lines around each match (default: 2)",
            "max_results": "Maximum results (default: 50)",
            "case_sensitive": "Case-sensitive search (default: False)",
        },
        'search_code("def.*auth", file_pattern="*.py", context_lines=3)',
        "search",
        "Search results with file paths, line numbers, and context.",
        search_code,
    ),
    (
        "find_symbol",
        "Find symbol definitions across languages (def/class/func/fn/struct/impl).",
        {
            "symbol": "Symbol name to find",
            "path": "Directory to search (default: '.')",
            "file_pattern": "Glob pattern to filter files",
        },
        'find_symbol("UserController", file_pattern="*.py")',
        "search",
        "List of symbol definitions with file paths and line numbers.",
        find_symbol,
    ),
    (
        "find_references",
        "Find all references to a symbol (not just definitions).",
        {
            "symbol": "Symbol name",
            "path": "Directory to search (default: '.')",
            "file_pattern": "Glob pattern to filter files",
            "max_results": "Maximum results (default: 100)",
        },
        'find_references("user_service", file_pattern="*.ts")',
        "search",
        "All lines containing the symbol.",
        find_references,
    ),
    # ── Research ──
    (
        "search_web",
        "Web search with Exa primary and Tavily fallback.",
        {"query": "Search query"},
        'search_web("Python asyncio best practices")',
        "web",
        "Search results with titles, URLs, and snippets.",
        search_web,
    ),
    (
        "search_local_docs",
        "Search local documentation using ctx7.",
        {"query": "Search query"},
        'search_local_docs("react hooks")',
        "web",
        "Documentation results.",
        search_local_docs,
    ),
    (
        "fetch_url",
        (
            "Fetch a URL and return the content as formatted text. "
            "Supports HTML (converted to text), JSON (pretty-printed), and plain text. "
            "Output truncated to 5000 chars max."
        ),
        {"url": "HTTP or HTTPS URL to fetch"},
        'fetch_url("https://example.com")',
        "web",
        "Formatted page content as text.",
        fetch_url,
    ),
    # ── Code Review ──
    (
        "review_code",
        (
            "Analyze code for bugs, style issues, security vulnerabilities, "
            "and performance problems. Uses static analysis (pattern matching "
            "+ AST for Python) — no LLM call required. Returns structured "
            "review with severity levels (CRITICAL, HIGH, MEDIUM, LOW, INFO)."
        ),
        {
            "code": "str — the source code to review",
            "language": "str — programming language (default: 'python')",
        },
        'review_code(code="eval(user_input)", language="python")',
        "review",
        "Formatted review report with categorized issues and severity levels.",
        review_code,
    ),
]


def register_all() -> None:
    """Register all static tools from TOOL_SPECS into the global registry."""
    for spec in TOOL_SPECS:
        name, description, parameters, example, category, returns, func = spec
        register_tool(
            name=name,
            description=description,
            parameters=parameters,
            example=example,
            category=category,
            returns=returns,
        )(func)


# Set of all built-in tool names — used to prevent MCP tools from shadowing them
BUILTIN_TOOL_NAMES: set[str] = {spec[0] for spec in TOOL_SPECS}
