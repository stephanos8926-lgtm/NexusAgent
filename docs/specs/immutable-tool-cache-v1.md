# Immutable Tool Cache — Specification v1

## Problem
`tools/registry/core.py:15` exposes `_REGISTRY: dict[str, ToolInfo]` as a mutable module-level dict.
- Static tools register at import time via `register_all()` → `TOOL_SPECS`
- Dynamic MCP tools register mid-session via `register_mcp_tools()`
- No thread safety, no snapshot isolation, version counter only checked at Agent.__init__

## Design
`ToolRegistry` class with immutable snapshots via `MappingProxyType`.

```python
class ToolRegistry:
    _lock: RLock
    _snapshots: dict[int, MappingProxyType]
    _latest_version: int
    _pending: dict[str, ToolInfo]

    @property
    def current(self) -> MappingProxyType
    def register(self, name, info) -> None
    def freeze(self) -> int
    def get_snapshot(self, version=None) -> MappingProxyType
    def cleanup(self, min_version) -> None
```

## Files to modify
1. `src/nexusagent/tools/registry/core.py` — Extract mutable _REGISTRY into ToolRegistry class
2. `src/nexusagent/tools/registry/__init__.py` — Export registry singleton
3. `src/nexusagent/core/agent.py` — Replace _ROLE_TOOLS/version counter with per-agent snapshot
4. `src/nexusagent/tools/register_all.py` — Call registry.freeze() after batch registrations
5. `src/nexusagent/tools/registry/types.py` — (add ToolRegistry import, no circular dep)

## Invariants
- No agent sees mid-mutation registry
- Registration is thread-safe (RLock)
- Old snapshots survive until no agent references them
- MCP batch registration is atomic (N × register + 1 × freeze)
- Backward compat: `_REGISTRY` property wraps `registry.current`
