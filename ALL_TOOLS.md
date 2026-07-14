# NexusAgent — Complete Tool Registry

**Total Built-in Tools:** 44 (from `TOOL_SPECS`) + Dynamic Memory Tools (11) + MCP Tools (dynamic)

---

## 📋 Core / Discovery Tools (2)

| Tool | Category | Description |
|------|----------|-------------|
| `tool_search` | core | Search for tools available to you. Only shows tools your policy allows. Call with no args to list all available tools. |
| `auto_correct` | core | Validate a tool call before executing. Checks tool name, policy access, and parameters. Returns corrections if anything is wrong. |

---

## 📁 File System Tools (8)

| Tool | Category | Description |
|------|----------|-------------|
| `read_file` | fs | Read a file's contents with optional line-range selection. Tracks files read in session. |
| `read_multiple_files` | fs | Read multiple files at once. Each file is marked as read in session tracking. |
| `write_file` | fs | Write content to a file (full replacement). SAFETY: existing files must be read first. |
| `write_multiple_files` | fs | Write multiple files at once. Each file must be read first if it already exists. |
| `edit_file` | fs | Surgical line-range edit. Replaces exact old_text with new_text. Requires read-first. Validates old_text exists. |
| `list_directory` | fs | List directory contents as a nested tree. Supports recursion, depth limits, glob patterns, and exclude filters. |
| `apply_patch` | fs | Apply a unified diff patch to a file. |

---

## 🐚 Shell Tools (2)

| Tool | Category | Description |
|------|----------|-------------|
| `run_shell` | shell | Execute a shell command with timeout, working directory, and environment variable control. |
| `run_shell_streaming` | shell | Execute a shell command with line-by-line streaming output. Better for long-running commands. |

⚠️ **WARNING:** These tools run arbitrary shell commands with full user permissions. They require explicit opt-in in config. NEVER enable by default.

---

## 🌿 Git Tools (10)

| Tool | Category | Description |
|------|----------|-------------|
| `git_status` | git | Show working tree status (short format). |
| `git_diff` | git | Show changes between working tree and index/HEAD. Supports specific files. |
| `git_log` | git | Show commit history. |
| `git_branch` | git | List branches. Current branch is marked with *. |
| `git_show` | git | Show a commit's details and diff. |
| `git_stash_push` | git | Stash current changes. Write operation. |
| `git_stash_pop` | git | Pop the most recent stash. Write operation. |
| `git_stash_list` | git | List stashed changes. |
| `git_commit` | git | Stage and commit changes. Write operation. |
| `git_checkout_branch` | git | Checkout a branch. Optionally create it first. |

⚠️ **Git write operations** (`git_commit`, `git_stash_push`, `git_stash_pop`, `git_checkout_branch`) require explicit opt-in.

---

## 🧪 Test Runner Tools (2)

| Tool | Category | Description |
|------|----------|-------------|
| `run_tests` | test | Auto-detect test framework (pytest/jest/maven/gradle/go/cargo) and run tests with structured output. |
| `run_single_test` | test | Run a single test file or test case. |

---

## 🔍 Code Search Tools (3)

| Tool | Category | Description |
|------|----------|-------------|
| `search_code` | search | Search code using ripgrep with context lines. Falls back to grep. |
| `find_symbol` | search | Find symbol definitions across languages (def/class/func/fn/struct/impl). |
| `find_references` | search | Find all references to a symbol (not just definitions). |

---

## 🌐 Research / Web Tools (3)

| Tool | Category | Description |
|------|----------|-------------|
| `search_web` | web | Web search with Exa primary and Tavily fallback. |
| `search_local_docs` | web | Search local documentation using ctx7. |
| `fetch_url` | web | Fetch a URL and return content as formatted text (HTML→text, JSON pretty-printed). |

---

## 📝 Code Review Tool (1)

| Tool | Category | Description |
|------|----------|-------------|
| `review_code` | review | Analyze code for bugs, style issues, security vulnerabilities, and performance problems. Uses static analysis (pattern matching + AST for Python) — no LLM call required. |

---

## ⚙️ Orchestration Tools (1)

| Tool | Category | Description |
|------|----------|-------------|
| `spawn_subagent` | orchestration | Spawn an isolated worker to handle a task autonomously. The worker runs in its own space with bounded turns and reports back. |

---

## 💬 Interaction Tools (1)

| Tool | Category | Description |
|------|----------|-------------|
| `ask_user` | interaction | Ask the user a question and wait for their response. In TUI mode, shows the question in the chat. |

---

## 🧠 Memory Tools (11 — Dynamic)

| Tool | Category | Description |
|------|----------|-------------|
| `memory_search` | memory | Search memory using hybrid keyword + vector search. Returns results with source citations. |
| `memory_get` | memory | Read a memory file by its relative path (e.g., 'bank/auth-20260712.md'). |
| `memory_write` | memory | Write a memory entry. Stores in bank/ directory with YAML frontmatter and indexes it. |
| `memory_index_search` | memory | Search the hybrid memory index (FTS5 + vector similarity) directly. More powerful than memory_search. |
| `memory_index_rebuild` | memory | Rebuild the hybrid memory index from workspace files. Drops all indexed chunks and re-scans. |
| `memory_delete` | memory | Delete a memory entry by its relative path. Removes the file and all its index entries. |
| `memory_update` | memory | Update an existing memory entry. Replaces the content and re-indexes it. Preserves YAML frontmatter. |
| `memory_list` | memory | List memory entries with optional filtering. Shows file paths, types, descriptions, and creation dates. |
| `memory_prune` | memory | Prune memory entries matching criteria. Supports dry-run mode to preview what would be deleted. |
| `memory_consolidate` | memory | Consolidate memory entries by removing duplicates and stale entries. Supports dry-run mode. |
| `memory_health` | memory | Report memory health metrics including total entries, duplicates, stale entries, and overall health score. |
| `memory_dream` | memory | Manually trigger a dream cycle to consolidate memories. Runs the 4-phase cycle: scan, patterns, consolidate, trim. |

---

## 🔌 MCP Tools (Dynamic)

Loaded at runtime from configured MCP servers (`settings.mcp_servers`). Each server's tools are prefixed with `[MCP:server_name]`.

---

## ⚠️ Terminal Command vs Run Shell

### `run_shell`
- **Full shell command execution** with arbitrary commands
- Runs via `subprocess.run()` with shell=True
- Can execute ANY command: `rm -rf /`, `sudo apt install`, `curl | bash`, etc.
- Full user permissions — can modify system files, install packages, network access
- **Requires explicit opt-in** (not in default `enabled_tools`)
- In config: `enable_shell_tool: true` or user adds to `enabled_tools`

### `terminal_command`
- **Does not exist in current codebase** — not a registered tool
- The config references `"terminal_command"` in defaults but it's **not implemented**
- May have been a planned alias for `run_shell` or a different tool

### Current Default `enabled_tools` (7 tools):
```yaml
enabled_tools:
  - "read_file"
  - "write_file"
  - "list_directory"
  - "search_files"      # Note: NOT in TOOL_SPECS — may be alias for search_code
  - "grep_files"        # Note: NOT in TOOL_SPECS — may be alias for search_code
  - "execute_python"    # Note: NOT in TOOL_SPECS
  - "execute_bash"      # Note: NOT in TOOL_SPECS — likely alias for run_shell
```

**Note:** `search_files`, `grep_files`, `execute_python`, `execute_bash` are referenced in config but **NOT in TOOL_SPECS**. They may be:
- Aliases handled by policy layer
- Planned tools not yet implemented
- Legacy names

### Actual implemented shell tools:
- `run_shell` — full shell (dangerous, opt-in only)
- `run_shell_streaming` — streaming shell (dangerous, opt-in only)

### To enable shell access:
Add to your `~/.nexusagent/config/nexusagent.yaml`:
```yaml
agent:
  enabled_tools:
    - "read_file"
    - "write_file"
    - "list_directory"
    - "search_code"
    - "run_shell"           # Add this for shell access
    - "run_shell_streaming" # Or this for streaming
```

---

## 📊 Summary

| Category | Count |
|----------|-------|
| Core / Discovery | 2 |
| File System | 8 |
| Shell | 2 |
| Git | 10 |
| Test Runner | 2 |
| Code Search | 3 |
| Research / Web | 3 |
| Code Review | 1 |
| Orchestration | 1 |
| Interaction | 1 |
| Memory | 11 |
| **Total Built-in** | **44** |
| MCP Tools | Dynamic |

**Tool access is controlled by Agent role/policy** (see `nexusagent.tools.registry.policy`), not by config. Default agent uses `role="full"`, `policy="permissive"` (all 44 tools available, auto-unlock on first call).

---

## ⚠️ Hallucination Prevention — Config ≠ Reality

**Root cause:** The config template (`config/nexusagent.yaml`) listed 8 tools that don't exist in the registry:
- ✗ `search_files` → **doesn't exist** (real: `search_code`)
- ✗ `grep_files` → **doesn't exist** (real: `search_code` with pattern)
- ✗ `execute_python` → **doesn't exist**
- ✗ `execute_bash` → **doesn't exist** (real: `run_shell`)
- ✗ `terminal_command` → **doesn't exist** (real: `run_shell`)

**Fixed:** Config template now lists only REAL tool names with commented examples for opt-in tools. The dead `enabled_tools` config field was removed from `AgentConfig` in `config.py`.