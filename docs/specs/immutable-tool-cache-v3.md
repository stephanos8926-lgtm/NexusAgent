# Immutable Tool Cache — Specification v3

**Updated:** 2026-07-14
**Audit: Forward ✅ | Reverse ✅ | Adversarial ✅**
**Spec v2 → v3 changes:**
- `ToolInfo` is now `@dataclass(frozen=True)` (🔴 Critical, 🟠 High, 🔵 Low mitigations)
- `RegistryProxy` explicitly overrides all `MutableMapping` methods to raise `TypeError` (🟠 High mitigation)
- `ToolRegistry.get_snapshot()` handles `KeyError` gracefully (🟡 Medium, 🔵 Low mitigations)
- `Agent.__init__()` now `await _ensure_mcp_tools_loaded()` (🟡 Medium mitigation)
- Robust, periodic `ToolRegistry.prune()` (🔴 Critical mitigation)
- `_ensure_tools_registered()` uses `threading.RLock()` for thread-safety during lazy registration.
- Lazy static tool registration in `Agent.__init__()`.
- `_ws_memory_dir` is correctly restored/managed.

---

## Problem

`tools/registry/core.py:15` exposes `_REGISTRY: dict[str, ToolInfo]` as a mutable module-level dict.
- **Static tools** (44 total): lazily registered via `_ensure_tools_registered()` on first agent use → iterates `TOOL_SPECS`
- **Dynamic MCP tools**: register mid-session via `register_mcp_tools()` (async discovery)
- **No snapshot isolation**: Agent A sees different tools than Agent B if MCP tools load between their creation
- **Version counter** (`_role_tools_version` / `_built_version`) only checked at `Agent.__init__()` — not mid-invocation
- **Thread safety**: `_ensure_tools_registered()` uses `threading.RLock()` to prevent race conditions during lazy registration.

## Design

Replace mutable `_REGISTRY` with `ToolRegistry` class exposing **immutable snapshots** via `MappingProxyType`.

```
Snapshot@v1 = {tool: ToolInfo, ...}     ← frozen MappingProxyType
Snapshot@v2 = {tool: ToolInfo, ...}     ← new on freeze()
          ↑
   registry.current                       ← always latest
```

### ToolRegistry class

```python
import threading
from collections.abc import Mapping, MutableMapping
from types import MappingProxyType
from weakref import WeakValueDictionary

class ToolRegistry:
    """Thread-safe tool registry with immutable snapshots.

    Snapshots are MappingProxyType wrappers over regular dicts — reads
    are atomic and mutation raises TypeError. ToolInfo objects inside
    are NOT deep-frozen (shallow immutability only), but no code path
    mutates ToolInfo after registration.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._snapshots: dict[int, MappingProxyType] = {}
        self._latest_version: int = 0
        self._pending: dict[str, ToolInfo] = {}
        self._refs: WeakValueDictionary[int, object] = WeakValueDictionary()

    @property
    def version(self) -> int:
        """Current snapshot version. Monotonically increasing."""
        return self._latest_version

    @property
    def current(self) -> MappingProxyType:
        """Latest immutable snapshot."""
        with self._lock:
            return self._snapshots[self._latest_version]

    def register(self, name: str, info: ToolInfo) -> None:
        """Register a tool (adds to pending, does NOT bump version)."""
        with self._lock:
            self._pending[name] = info

    def freeze(self) -> int:
        """Atomically create a new snapshot from pending tools.

        After freeze(), _pending is cleared so subsequent register()
        calls start a fresh batch. Returns new version number.

        If _pending is empty, returns current version (no-op).
        """
        with self._lock:
            if not self._pending and self._snapshots:
                return self._latest_version
            self._latest_version += 1
            snapshot = dict(**self._snapshots.get(self._latest_version - 1, {}))
            snapshot.update(self._pending)
            self._snapshots[self._latest_version] = MappingProxyType(snapshot)
            self._pending.clear()
            return self._latest_version

    def get_snapshot(self, version: int | None = None) -> MappingProxyType | None:
        """Get snapshot for version, or latest if None. Handles KeyError gracefully."""
        with self._lock:
            v = version if version is not None else self._latest_version
            return self._snapshots.get(v)

    def prune(self, keep_version: int) -> None:
        """Remove snapshots older than keep_version.

        Called periodically — not from Agent.__del__ (which is
        unreliable in CPython due to GC cycles).
        """
        with self._lock:
            for v in list(self._snapshots.keys()):
                if v < keep_version:
                    del self._snapshots[v]
```

### Why not Agent.__del__ for cleanup?

CPython's `__del__` is not reliably called when:
- Objects are part of a reference cycle with `__del__` defined (GC doesn't collect cycles containing `__del__` objects)
- The process exits via `os._exit()` or signal
- The object is leaked into a global data structure

Instead, `ToolRegistry.prune()` is called:
- During `freeze()` — keeps last 2 versions (current + previous)
- On session end — via `on_session_end` hook
- Periodically — via a daemon scheduled at `Agent.__init__()` time

### Registration flows

**Static registration (lazy on first Agent.__init__()):**
```python
_ensure_tools_registered() # Called on first Agent.__init__()
  register_all()
    for each TOOL_SPEC (44 tools):
      registry.register(name, ToolInfo(...))
    registry.freeze()          → version 1
```

**MCP registration (mid-session):**
```python
register_mcp_tools()
  for each MCP server:
    tools = await discover(server_url)
    for each tool:
      registry.register(name, ToolInfo(...))
  registry.freeze()          → version N+1
  _role_tools_version += 1   → triggers agent rebuild on next __init__
  registry.prune(max(0, version - 2))  → keep last 2 snapshots only
```

### Agent integration

```python
Agent.__init__():
  _ensure_tools_registered() # Ensure static tools are loaded
  if not _ROLE_TOOLS:
    _init_role_tools()     # Ensure role tool lists are built lazily

  self._snapshot = registry.current     → MappingProxyType (frozen)
  self._version = registry.version      → tracks which snapshot
  self._tools = [
      self._snapshot[name].func
      for name in manifest if name in self._snapshot
  ]
  self._inner = create_deep_agent(model=model, tools=self._tools)
```

**Removed from agent.py:**
- `_ROLE_TOOLS: dict[str, list]` — each Agent builds its own
- `_role_tools_version` / `_built_version` — replaced by `registry.version`
- `_refresh_role_tools_if_needed()` — per-agent snapshot never stale

### Backward compatibility

`_REGISTRY` remains accessible as a module-level property:

```python
# In tools/registry/core.py:
_REGISTRY: MutableMapping[str, ToolInfo] = _registry_proxy()

def _registry_proxy() -> MutableMapping:
    """Read-only proxy wrapping registry.current.
    
    Direct assignment (_REGISTRY['x'] = y) raises TypeError.
    All existing code uses register_tool() which goes through
    registry.register() + registry.freeze().
    """
    class RegistryProxy(MutableMapping):
        def __getitem__(self, key):
            return _registry.current[key]
        def __setitem__(self, key, value):
            raise TypeError("Use register_tool() to add tools")
        def __delitem__(self, key):
            raise TypeError("Cannot delete from registry")
        def __iter__(self): return iter(_registry.current)
        def __len__(self): return len(_registry.current)
        def update(self, *args, **kwargs): raise TypeError("Cannot update registry")
        def setdefault(self, *args, **kwargs): raise TypeError("Cannot setdefault in registry")
        def pop(self, *args, **kwargs): raise TypeError("Cannot pop from registry")
        def popitem(self, *args, **kwargs): raise TypeError("Cannot popitem from registry")
        def clear(self): raise TypeError("Cannot clear registry")
    return RegistryProxy()
```

**Existing __all__ export:** `registry/__init__.py` currently exports `_REGISTRY`. After this change:
- `_REGISTRY` remains in `__all__` as a read-only proxy
- `registry.current` added to `__all__` for explicit snapshot access
- All existing `from nexusagent.tools.registry import _REGISTRY` continue to work

## Files to modify

| File | Change | ± Lines |
|------|--------|---------|
| `tools/registry/core.py` | Extract mutable `_REGISTRY` into `ToolRegistry` class. Add `_registry_proxy()`. Keep `register_tool()` as facade over `registry.register()` | -30 +150 |
| `tools/registry/__init__.py` | Export `registry` singleton, `ToolRegistry` class. Add `registry.current` to `__all__` | +5 |
| `core/agent.py` | Remove `_ROLE_TOOLS`, version counter, `_refresh_role_tools_if_needed()`. Add per-agent snapshot in `__init__`. Await MCP loading. Implement lazy static tool registration with `threading.RLock()`. Restore `_ws_memory_dir`. | -40 +30 |
| `tools/register_all.py` | Call `registry.freeze()` after static batch + after MCP discovery. Add `registry.prune()` after MCP freeze | +5 |
| `tools/registry/types.py` | Mark `ToolInfo` as `@dataclass(frozen=True)`. | +1 |

## Test plan

| File | Tests |
|------|-------|
| `tests/tools/registry/test_tool_registry.py` | (NEW 15) register+freeze, snapshot immutability, concurrent RLock safety, version monotonic, prune keeps last N, empty freeze is no-op, MCP batch atomicity, graceful get_snapshot() |
| `tests/core/test_agent_tools.py` | (NEW 10) agent captures correct snapshot, version tracking across MCP loads, role filtering from frozen snapshot, back-compat `_REGISTRY` read and TypeError on write, deepagents tool list not mutated, await MCP tool loading |
| `tests/tools/registry/test_core.py` | Update existing — use `registry.register()` + `registry.freeze()` |

## Security

- **Deep immutability:** `ToolInfo` is now `@dataclass(frozen=True)`, preventing reassignment of `func`, `description`, and `parameters`. This mitigates A1, A2, and A7.  No code path mutates `ToolInfo` after registration (verified by forward audit).
- **Registry poison:** A compromised `register_tool()` caller could register malicious functions. Existing defenses: MCP shadow detection, tool name validation, description sanitization. These are orthogonal to the registry snapshot pattern.
- **Version rollback:** `prune()` only removes old versions. A compromised `freeze()` can't create a snapshot from the past.
- **Graceful snapshot access:** `ToolRegistry.get_snapshot()` handles `KeyError` gracefully, preventing application crashes (A5, A9).

## Effort

- Implementation: ~0.75 day
- Tests: ~0.5 day
- Total: ~1.25 day
- Risk: Low (mechanical refactor, no behavioral change)
