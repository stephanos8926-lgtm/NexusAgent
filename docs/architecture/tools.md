# Tool System Architecture

## Design Principles

1. **Progressive Discovery**: Agents start with minimal tools and unlock on demand
2. **Policy Enforcement**: Two-layer security (discovery + execution)
3. **Auto-Correction**: Helpful hints for wrong names/params
4. **Role-Based Access**: Sub-agents get only the tools they need

## Tool Lifecycle

```
1. Register: @register_tool() decorator adds tool to _REGISTRY
2. Discover: tool_search() finds tools by name or use case
3. Validate: _is_tool_allowed() checks policy before execution
4. Execute: Tool runs with policy context
5. Auto-unlock: In permissive mode, first call adds to unlocked set
```

## Policy Enforcement Flow

```
Agent calls tool_search("run tests")
  → Filter registry by policy context
  → Return only in-scope tools
  → Agent never sees out-of-scope tools

Agent calls git_commit(...)
  → _is_tool_allowed("git_commit") checks policy
  → permissive: auto-unlock, allow
  → restricted: check manifest, allow/deny
  → strict: check manifest, deny if not in initial set
```
