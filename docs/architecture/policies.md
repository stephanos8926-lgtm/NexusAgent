# Policy System

The policy system enforces tool access control at two layers: **discovery** and **execution**.

## Policy Levels

| Level | Description | Use Case |
|---|---|---|
| `permissive` | Auto-unlock on first call | User-spawned agents |
| `restricted` | Enforced role boundaries | Sub-agents |
| `strict` | Locked to initial manifest | Sandboxed sub-agents |

## Defense in Depth

1. **Discovery layer**: `tool_search()` only returns tools the agent can use
2. **Execution layer**: Each tool checks policy before executing

An agent can't use what it can't find, and even if it guesses a tool name, the call is denied.

## Usage

```python
from nexusagent.agent import Agent

# Permissive (default) — auto-unlock on use
agent = Agent(role="coder", policy="permissive")

# Restricted — enforced boundaries
sub = Agent(role="tester", policy="restricted")

# Strict — locked forever
sandbox = Agent(role="reviewer", policy="strict")
```

## Role Manifests

Each role defines a set of accessible tools:

| Role | Tools |
|---|---|
| `minimal` | `tool_search` only |
| `reader` | Read + search |
| `writer` | Read + write |
| `coder` | Full dev tooling |
| `tester` | Test execution + edits |
| `reviewer` | Read + git history |
| `debugger` | Read + edit + test + shell |
| `researcher` | Search + read |
| `full` | All tools |
