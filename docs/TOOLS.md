# NexusAgent Tools Reference — AST-Tools MCP Integration

> Generated: 2026-07-18
> MCP Server: `ast-tools` (mcp_ast_tools_*)
> Purpose: Structural code analysis and surgical editing via Abstract Syntax Tree (AST)

---

## Overview

NexusAgent integrates with the `ast-tools` MCP server for structural code operations.
These tools operate on AST nodes rather than raw text, enabling precise refactoring
that preserves formatting, comments, and indentation.

**Key principle:** All ast-tools calls use `mcp_ast_tools_*` function calls.
NexusAgent does not import the AST library directly — the MCP server handles parsing.

---

## Available Tools

### 1. `ast_grep` — Structural Code Search

Search for code patterns using AST-aware matching. Finds structures regardless of
whitespace, comments, or variable naming.

**Input Schema:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pattern` | `string` | **Yes** | AST pattern (e.g., `def $FUNC($$$ARGS)`) |
| `path` | `string` | No | File or directory to search (default: `.`) |
| `lang` | `string` | No | Language: `python`, `javascript`, `typescript`, `rust`, `go`, `java`, `c`, `cpp` |
| `json_output` | `boolean` | No | Return JSON with file, line, column, text (default: `true`) |

**Pattern Syntax:**
- `$VAR` — matches any single node
- `$$$VAR` — matches zero or more nodes (greedy)
- Literal text matches exactly

**Example Usage:**
```python
# Find all function definitions in Python files
ast_grep(pattern="def $FUNC($$$ARGS)", path="src/", lang="python")

# Find all method calls with 2 arguments
ast_grep(pattern="call($OBJ, $METHOD)", path="src/nexusagent/")

# Find all class definitions
ast_grep(pattern="class $NAME", path="src/")
```

---

### 2. `ast_edit` — Surgical AST-Based Code Modification

Perform precise structural edits that preserve formatting and comments.
Uses libcst (Concrete Syntax Tree) for lossless transformations.

**Input Schema:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | `string` | **Yes** | Path to the file to edit |
| `operation` | `string` | **Yes** | One of: `replace_node`, `insert_after`, `insert_before`, `remove_node`, `rename_function`, `add_parameter`, `change_signature` |
| `params` | `object` | **Yes** | Operation-specific parameters (see below) |
| `dry_run` | `boolean` | No | Preview changes without writing (default: `false`) |

**Operations:**

| Operation | Params | Description |
|-----------|--------|-------------|
| `replace_node` | `{old_node, new_node}` | Replace an AST node |
| `insert_after` | `{anchor, new_code}` | Insert code after anchor node |
| `insert_before` | `{anchor, new_code}` | Insert code before anchor node |
| `remove_node` | `{node}` | Remove an AST node |
| `rename_function` | `{old_name, new_name}` | Rename a function |
| `add_parameter` | `{func_name, param, default?}` | Add parameter to function |
| `change_signature` | `{func_name, new_signature}` | Change function signature |

**Example Usage:**
```python
# Rename a function
ast_edit(file="src/nexusagent/core/session.py",
         operation="rename_function",
         params={"old_name": "old_func", "new_name": "new_func"})

# Add a parameter to a function
ast_edit(file="src/nexusagent/core/agent.py",
         operation="add_parameter",
         params={"func_name": "Agent", "param": "verbose: bool = False"})

# Dry run before committing
ast_edit(file="src/nexusagent/tools/fs.py",
         operation="remove_node",
         params={"node": "dead_function"},
         dry_run=True)
```

---

### 3. `ast_read` — Structural Context Extraction

Extract high-level API surface without reading every line. Returns classes,
functions, imports, and variables with signatures and docstrings.

**Input Schema:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | `string` | **Yes** | Path to the source file |
| `include_private` | `boolean` | No | Include `_`-prefixed members (default: `false`) |
| `include_imports` | `boolean` | No | Include import statements (default: `true`) |

**Example Usage:**
```python
# Get public API surface of a module
ast_read(file="src/nexusagent/core/session.py")

# Include private members for full analysis
ast_read(file="src/nexusagent/tools/registry/core.py", include_private=True)

# Skip imports for cleaner output
ast_read(file="src/nexusagent/version.py", include_imports=False)
```

---

### 4. `structural_analysis` — Multi-Hop Structural Analysis

Analyze call graphs, type hierarchies, symbol references, and dependency maps.

**Input Schema:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `analysis_type` | `string` | **Yes** | One of: `callers`, `callees`, `type_hierarchy`, `references`, `dependencies` |
| `symbol` | `string` | No | Symbol name to analyze |
| `file` | `string` | No | File containing the symbol (required for callers/callees/references) |
| `line` | `integer` | No | Line number of symbol definition (required for callers/callees/references) |
| `project_root` | `string` | No | Project root for cross-file analysis |

**Analysis Types:**

| Type | Description |
|------|-------------|
| `callers` | Who calls this function/class? |
| `callees` | What does this function call? |
| `type_hierarchy` | Class inheritance tree |
| `references` | Every use of a name across the project |
| `dependencies` | Module import graph |

**Example Usage:**
```python
# Find all callers of a function
structural_analysis(analysis_type="callers",
                    symbol="Session.send",
                    file="src/nexusagent/core/session.py",
                    line=303)

# Get the full dependency graph
structural_analysis(analysis_type="dependencies",
                    project_root="src/nexusagent/")

# Find all references to a symbol
structural_analysis(analysis_type="references",
                    symbol="VERSION",
                    file="src/nexusagent/version.py",
                    line=9)
```

---

### 5. `project_info` — Project-Level Structural Summary

Get a high-level structural overview of the entire project.

**Input Schema:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | `string` | No | Project root (default: `.`) |
| `lang` | `string` | No | Primary language filter |

**Example Usage:**
```python
# Get full project structure
project_info(path="src/nexusagent/")

# Python-only view
project_info(path=".", lang="python")
```

---

### 6. `codebase_summary` — Codebase Statistics and Hotspots

Generate statistics about the codebase: file counts, line counts, complexity
hotspots, and coupling metrics.

**Input Schema:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | `string` | No | Root directory (default: `.`) |
| `include_tests` | `boolean` | No | Include test files in analysis |

**Example Usage:**
```python
# Full codebase summary
codebase_summary(path=".", include_tests=True)

# Source only
codebase_summary(path="src/")
```

---

### 7. `find_references` — Cross-File Symbol References

Find all references to a symbol across the entire codebase. More comprehensive
than `structural_analysis` for simple reference finding.

**Input Schema:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbol` | `string` | **Yes** | Symbol name to find |
| `path` | `string` | No | Root directory (default: `.`) |
| `lang` | `string` | No | Language filter |

**Example Usage:**
```python
# Find all uses of VERSION constant
find_references(symbol="VERSION", path="src/")

# Find all uses of a class
find_references(symbol="NexusSDK", path="src/nexusagent/")
```

---

### 8. `impact_analysis` — Change Impact Prediction

Predict the impact of a proposed change: which files, functions, and tests
would be affected.

**Input Schema:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | `string` | **Yes** | File to analyze changes in |
| `symbol` | `string` | No | Specific symbol to analyze |
| `change_type` | `string` | No | Type of change: `rename`, `remove`, `modify_signature` |

**Example Usage:**
```python
# Analyze impact of renaming a function
impact_analysis(file="src/nexusagent/core/session.py",
                symbol="Session.send",
                change_type="rename")

# Analyze impact of removing a module
impact_analysis(file="src/nexusagent/version.py",
                change_type="remove")
```

---

## Integration with NexusAgent

### When to Use Each Tool

| Task | Tool |
|------|------|
| Find all functions matching a pattern | `ast_grep` |
| Understand a module's public API | `ast_read` |
| Rename a function across the codebase | `ast_edit` (rename_function) |
| Add a parameter to a function | `ast_edit` (add_parameter) |
| Find who calls a function | `structural_analysis` (callers) |
| Find all uses of a symbol | `find_references` |
| Understand class hierarchy | `structural_analysis` (type_hierarchy) |
| Predict change impact | `impact_analysis` |
| Get project overview | `project_info` or `codebase_summary` |

### Workflow: Safe Refactoring

1. **Read** — Use `ast_read` to understand the target module
2. **Search** — Use `ast_grep` to find all instances of the pattern
3. **Analyze** — Use `structural_analysis` or `find_references` to find all usages
4. **Impact** — Use `impact_analysis` to predict consequences
5. **Edit** — Use `ast_edit` with `dry_run=True` first
6. **Verify** — Run tests: `PYTHONPATH=src python3 -m pytest tests/ -q --tb=short`
7. **Commit** — Use conventional commit format

### Supported Languages

All tools support: Python, JavaScript, TypeScript, Rust, Go, Java, C, C++

NexusAgent is a Python project, so `lang="python"` is the default for most operations.
