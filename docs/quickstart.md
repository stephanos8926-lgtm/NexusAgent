# Tool System

NexusAgent's tool system provides **progressive discovery** — agents start lean and unlock tools on demand.

## Core Concepts

### Tool Registry
All tools are registered in a central catalog with metadata:

```python
from nexusagent.tools.registry import register_tool

@register_tool(
    name="read_file",
    description="Read file contents with optional line-range selection",
    parameters={"path": "File path", "offset": "Start line", "limit": "Max lines"},
    example='read_file("src/main.py", offset=10, limit=20)',
    category="fs",
)
def read_file(path, offset=1, limit=None):
    ...
```

### Tool Search
Agents discover tools via `tool_search()`:

```python
# List all available tools
tool_search()

# Search by use case
tool_search("run tests")

# Get specific tool details
tool_search("read_file", exact=True)

# Filter by category
tool_search(category="git")
```

## Available Tools

### Core Tools
| Tool | Description |
|---|---|
| `tool_search` | Search for tools by name or use case |
| `auto_correct` | Validate tool calls and get corrections |

### File System Tools
| Tool | Description |
|---|---|
| `read_file` | Read file with line-range support |
| `write_file` | Full file replacement (requires read-first) |
| `edit_file` | Surgical line-range edit |
| `list_directory` | Recursive directory listing |
| `apply_patch` | Apply unified diff |

### Git Tools
| Tool | Description |
|---|---|
| `git_status` | Working tree status |
| `git_diff` | Show changes |
| `git_log` | Commit history |
| `git_commit` | Stage and commit |
| `git_checkout_branch` | Checkout/create branches |

### Test Tools
| Tool | Description |
|---|---|
| `run_tests` | Auto-detect framework and run |
| `run_single_test` | Run specific test file |

### Search Tools
| Tool | Description |
|---|---|
| `search_code` | ripgrep-based code search |
| `find_symbol` | Multi-language symbol search |
| `find_references` | Find all references to a symbol |

### Shell Tools
| Tool | Description |
|---|---|
| `run_shell` | Execute shell command |
| `run_shell_streaming` | Streaming output for long commands |

### Research Tools
| Tool | Description |
|---|---|
| `search_web` | Web search (Exa + Tavily) |
| `search_local_docs` | Local documentation search |
