"""
Tool registration — introspects existing tools and registers them in the registry.

This module imports all tools and calls register_tool() for each one.
Import this module once at startup to populate the registry.
"""

# Import discovery tools
from nexusagent.tools.registry import auto_correct, register_tool, tool_search

# ═══════════════════════════════════════════════════════════════════════
# Discovery Tools (register first so they're available in the registry)
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
        'tool_search("read_file", exact=True       # Get specific tool details\n'
        'tool_search(category="git")               # List git tools'
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
from nexusagent.tools.research import search_local_docs, search_web
from nexusagent.tools.shell import run_shell, run_shell_streaming
from nexusagent.tools.test_runner import run_single_test, run_tests

# Register FS tools
register_tool(
    name="read_file",
    description="Read a file's contents with optional line-range selection. Tracks files read in session.",
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
    description="Read multiple files at once. Each file is marked as read in session tracking.",
    parameters={"paths": "List of file paths"},
    example='read_multiple_files(["src/main.py", "tests/test_main.py"])',
    category="fs",
    returns="Dict mapping file path to content.",
)(read_multiple_files)

register_tool(
    name="write_file",
    description="Write content to a file (full replacement). SAFETY: existing files must be read first.",
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
    description="Write multiple files at once. Each file must be read first if it already exists.",
    parameters={"files": "Dict mapping file path to content"},
    example='write_multiple_files({"a.py": "x=1", "b.py": "y=2"})',
    category="fs",
    returns="Success message.",
)(write_multiple_files)

register_tool(
    name="edit_file",
    description="Surgical line-range edit. Replaces exact old_text with new_text. Requires read-first. Validates old_text exists.",
    parameters={
        "path": "File path",
        "old_text": "Exact text to find and replace (must match exactly)",
        "new_text": "Replacement text",
        "start_line": "Optional start line (1-indexed) to constrain search",
        "end_line": "Optional end line (1-indexed) to constrain search",
    },
    example='edit_file("src/main.py", old_text="x = 1", new_text="x = 42", start_line=10, end_line=15)',
    category="fs",
    returns="Success message with line change summary.",
)(edit_file)

register_tool(
    name="list_directory",
    description="List directory contents as a nested tree. Supports recursion, depth limits, glob patterns, and exclude filters.",
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

# ═══════════════════════════════════════════════════════════════════════
# Shell Tools
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="run_shell",
    description="Execute a shell command with timeout, working directory, and environment variable control.",
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
    description="Execute a shell command with line-by-line streaming output. Better for long-running commands.",
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
    description="Show changes between working tree and index/HEAD. Supports specific files.",
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
        "create": "If True, create the branch (-b flag)",
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
    description="Auto-detect test framework (pytest/jest/maven/gradle/go/cargo) and run tests with structured output.",
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
    description="Search code using ripgrep with context lines. Falls back to grep.",
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
    description="Find symbol definitions across languages (def/class/func/fn/struct/impl).",
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

# ═══════════════════════════════════════════════════════════════════════
# Patch Tool
# ═══════════════════════════════════════════════════════════════════════

register_tool(
    name="apply_patch",
    description="Apply a unified diff patch to a file.",
    parameters={
        "path": "File to patch",
        "diff": "Unified diff content",
    },
    example='apply_file("src/main.py", diff_content)',
    category="fs",
    returns="Success or error message.",
)(apply_patch)
