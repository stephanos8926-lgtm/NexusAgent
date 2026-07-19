# Adversarial Audit: Immutable Tool Cache (v2)

## 🔴 Critical: ToolInfo.func is Mutable
**Attack scenario:** An attacker who gains a reference to a `ToolInfo` object can reassign its `func` attribute, effectively replacing a legitimate tool function with a malicious one.
**Exploit path:** 1. Attacker obtains a `ToolInfo` instance (e.g., if a debug utility exposes it). → 2. `tool_info.func = malicious_function`. → 3. Any subsequent calls to that tool will execute `malicious_function`.
**Impact:** Arbitrary code execution within the agent's process, leading to complete compromise of the agent's capabilities and environment.
**Current defense:** None. `ToolInfo` is a dataclass without `frozen=True`.
**Mitigation:** Mark `ToolInfo` as `@dataclass(frozen=True)`.

## 🟠 High: MappingProxyType Shallow Immutability — ToolInfo fields remain mutable
**Attack scenario:** Although `MappingProxyType` prevents adding or removing tools from the snapshot, the `ToolInfo` objects *within* the snapshot are still mutable. An attacker who obtains a reference to a `ToolInfo` object from the snapshot could modify its non-`func` attributes (e.g., `description`, `parameters`, `example`).
**Exploit path:** 1. Attacker gets a reference to `ToolInfo` from `registry.current['tool_name']`. → 2. Attacker modifies `tool_info.description = 'EVIL DESCRIPTION'`. → 3. The agent's LLM sees the tampered description, potentially leading to prompt injection or misleading behavior.
**Impact:** Misdirection of the agent, prompt injection via modified tool descriptions/examples, or breaking tool invocation by altering parameters. While less direct than `func` reassignment, it's a significant control flow vulnerability.
**Current defense:** The spec states "no code path mutates ToolInfo after registration (verified by forward audit)". This is a procedural defense, not a technical one.
**Mitigation:** Mark `ToolInfo` as `@dataclass(frozen=True)`. This would make all fields immutable.

## 🟠 High: RegistryProxy bypass via MutableMapping methods
**Attack scenario:** The `RegistryProxy` explicitly overrides `__setitem__` and `__delitem__` to raise `TypeError`, but it inherits other `MutableMapping` methods like `update()`, `setdefault()`, `pop()`, `popitem()`, and `clear()`. If the underlying `_registry.current` (which is a `MappingProxyType`) is accessed indirectly through these inherited methods, an attacker might be able to modify or delete entries.
**Exploit path:** If a code path directly uses `_REGISTRY.update(...)` or `_REGISTRY.setdefault(...)`, these calls will likely go through without the `TypeError` as the `RegistryProxy` itself doesn't implement them, passing them down to the underlying `MappingProxyType`. `MappingProxyType` itself will raise `TypeError` if `update` or `setdefault` attempt to modify its *own* internal dictionary. However, the spec only explicitly calls out `__setitem__` protection. The current implementation of `RegistryProxy` would cause `update` to fail because `MappingProxyType` also prevents mutation. The risk here is primarily in the *lack of explicit protection* in the `RegistryProxy` for these methods, which could lead to a false sense of security or be vulnerable if `_registry.current` were ever replaced with a truly mutable object.
**Impact:** Potential for unexpected behavior if the underlying `MappingProxyType` were to change its behavior or if a custom `Mapping` implementation was used that *did* allow mutation via these methods. At minimum, the `RegistryProxy` is not as robustly immutable as the spec implies, leading to maintenance surprises.
**Current defense:** `MappingProxyType` implicitly protects these operations by raising `TypeError` itself.
**Mitigation:** Explicitly override all `MutableMapping` methods in `RegistryProxy` to raise `TypeError`, ensuring a consistent and robust immutability contract.

## 🟡 Medium: _pending accumulation attack (pre-implementation)
**Attack scenario:** The spec describes `_pending` accumulating tools if `freeze()` is never called. In the *current* codebase (pre-spec implementation), `register()` and `freeze()` methods on `ToolRegistry` do not exist. The existing `register_tool()` directly modifies the global `_REGISTRY`. If an attacker could repeatedly call `register_tool()` without a mechanism to "freeze" or publish the changes, this could lead to memory accumulation, though it's not a direct security exploit in the same way. In the *spec's design*, if `freeze()` is not called after calls to `register()`, `_pending` would grow indefinitely.
**Exploit path:** In the spec's design, if `freeze()` calls were somehow suppressed after `register()` calls (e.g., an error prevents `freeze()` from executing), the `_pending` dictionary could grow, consuming memory and potentially leading to a denial-of-service.
**Impact:** Resource exhaustion (memory leak) if `freeze()` is never called.
**Current defense:** The spec outlines that `freeze()` is called after static tool registration and after MCP discovery. If these calls are implemented correctly, the `_pending` accumulation should be managed.
**Mitigation:** Ensure robust `freeze()` calls in all tool registration paths. Implement monitoring for `_pending` size in production.

## 🟡 Medium: `get_snapshot(version=0)` before first `freeze()` crashes
**Attack scenario:** If `ToolRegistry.get_snapshot(version=0)` (or `registry.current` when `_latest_version` is `0`) is called before `ToolRegistry.freeze()` has been invoked even once, it will attempt to access `self._snapshots[0]`, resulting in a `KeyError` because `_snapshots` is empty.
**Exploit path:** Any component calling `get_snapshot()` before initial static tool registration (which includes the first `freeze()`) could crash the application. While `register_all()` and its subsequent `freeze()` should run at startup, external modules or tests could trigger this edge case.
**Impact:** Application crash (denial of service) on startup or during early lifecycle phases if an agent attempts to access tools before they are initially frozen.
**Current defense:** Implicit reliance on `register_all()` running at startup.
**Mitigation:** `ToolRegistry.get_snapshot()` should handle `_snapshots` being empty gracefully, perhaps returning an empty `MappingProxyType` for `version=0` if no freeze has occurred, or raising a more specific error if an invalid version is requested.

## 🟡 Medium: Existing Race Condition: Agent `__init__` vs. MCP tool loading
**Attack scenario:** The current design (and the spec's proposed `Agent.__init__` integration) involves `Agent.__init__` firing `_ensure_mcp_tools_loaded()` as a fire-and-forget `asyncio.Task`. Immediately after, the agent proceeds to build its tool list from the current `_REGISTRY` (or `registry.current` in the new design). Because MCP tool loading is asynchronous, it's highly likely that the `_ensure_mcp_tools_loaded()` task has not completed, and thus `_role_tools_version` (or `registry.version` in the new design) has not been incremented, and the MCP tools have not been `freeze()`d into the registry.
**Exploit path:** An agent created early in the application lifecycle will *not* have access to dynamically loaded MCP tools in its initial tool snapshot. If the task requires MCP tools, the agent will fail to find or use them, leading to incorrect behavior or task failure.
**Impact:** Agents will operate with an incomplete view of available tools, potentially missing critical capabilities provided by MCP servers. This is a functional correctness issue, not a direct security exploit, but it impacts the reliability and completeness of agent operations.
**Current defense:** None. This is an inherent race condition in the asynchronous loading and synchronous snapshot acquisition.
**Mitigation:** The agent's initialization should `await _ensure_mcp_tools_loaded()` (or a similar blocking mechanism) to guarantee that all static and dynamic tools are registered and frozen before the agent's tool snapshot is created. Alternatively, agents could subscribe to registry updates and dynamically refresh their tool list if the version changes.

## 🔵 Low: `ToolInfo.parameters` mutable (shallow immutability)
**Attack scenario:** Similar to the `ToolInfo` object itself being mutable, the `parameters` dictionary within `ToolInfo` is also mutable. An attacker who gets a reference to a `ToolInfo` could modify the `parameters` dictionary directly.
**Exploit path:** 1. Attacker obtains `tool_info = registry.current['tool_name']`. → 2. `tool_info.parameters['evil_param'] = 'description'`. → 3. This could confuse the LLM or other components expecting a specific parameter schema.
**Impact:** Misleading agent behavior, potential for prompt injection if the parameter descriptions are displayed to the LLM.
**Current defense:** None, `ToolInfo` is not frozen.
**Mitigation:** Mark `ToolInfo` as `@dataclass(frozen=True)`. This would automatically make the `parameters` dict (and all other fields) immutable.

## 🔵 Low: deepagents tool list reference
**Attack scenario:** The `Agent.__init__` method passes a list of tool functions (`tools = _ROLE_TOOLS.get(role, _ROLE_TOOLS["full"])`) directly to `create_deep_agent(..., tools=tools)`. If the `deepagents` library internally holds a reference to this list rather than making a defensive copy, and if `_ROLE_TOOLS` (or its equivalent in the new `ToolRegistry` design) were somehow mutated *after* an agent was initialized, the running agent's tool list could be affected.
**Exploit path:** 1. Agent A is initialized, and `create_deep_agent` gets a reference to its tool list. → 2. `_ROLE_TOOLS` (or the underlying `ToolRegistry` snapshot if `freeze()` is called again) is mutated in a way that alters the original list. → 3. Agent A's `_inner` deep agent might observe a changed tool list mid-operation.
**Impact:** Unpredictable behavior of running agents if their tool list changes unexpectedly. This is a more complex race condition, but less likely given Python's object model and `deepagents`' probable internal copying.
**Current defense:** The spec changes `_ROLE_TOOLS` to be per-agent snapshot and `MappingProxyType` for the `_snapshot` which contains `ToolInfo` objects, which in turn have references to the actual `func`. The `_inner` agent gets a list of `func` references. If deepagents makes a copy of the list, this is mitigated. If deepagents does not copy, and the original list of funcs for a role can change (which it shouldn't under the new design), then there is a risk.
**Mitigation:** Verify `deepagents.create_deep_agent` either copies the `tools` list or guarantees that it's treated as immutable.

## 🔵 Low: `prune()` KeyError on accessing old snapshots
**Attack scenario:** The `ToolRegistry.prune(keep_version)` method removes snapshots older than `keep_version`. If an agent or another component attempts to retrieve a snapshot using `get_snapshot(version=N)` where `N` is a version that has been pruned, it will result in a `KeyError`.
**Exploit path:** A long-running agent or a system monitoring tool might attempt to retrieve an old snapshot for historical analysis, only to crash when the version has been pruned.
**Impact:** Application crash (denial of service) for components attempting to access pruned historical snapshots.
**Current defense:** The spec mentions `prune` is called periodically and on session end, keeping "last 2 versions". This suggests a window of availability.
**Mitigation:** `ToolRegistry.get_snapshot()` should handle `KeyError` when a version is not found, perhaps by returning `None` or raising a more descriptive `SnapshotNotFound` error, rather than crashing. The `keep_version` logic should also consider any active long-running agents.

---

### Summary Table:

| ID | Severity | Risk | Mitigated by spec? | Action needed |
|----|----------|------|--------------------|---------------|
| 1 | Critical | Arbitrary Code Execution | No | Mark ToolInfo as `@dataclass(frozen=True)` |
| 2 | High     | Prompt Injection / Misdirection | No, only procedural | Mark ToolInfo as `@dataclass(frozen=True)` |
| 3 | High     | Inconsistent Immutability Contract | Partially (MappingProxyType protects) | Explicitly override all MutableMapping methods in RegistryProxy |
| 4 | Medium   | Resource Exhaustion (DoS) | Yes (with correct `freeze()` implementation) | Ensure robust `freeze()` calls; monitor `_pending` size |
| 5 | Medium   | Application Crash (DoS) | No | `get_snapshot()` to handle `KeyError` gracefully |
| 6 | Medium   | Incomplete Tool Access | No (existing race preserved) | `await _ensure_mcp_tools_loaded()` in `Agent.__init__` |
| 7 | Low      | Misleading Agent Behavior | No | Mark ToolInfo as `@dataclass(frozen=True)` |
| 8 | Low      | Unpredictable Agent Behavior | Unknown (depends on deepagents) | Verify `deepagents` copies tool list |
| 9 | Low      | Application Crash (DoS) | No | `get_snapshot()` to handle `KeyError` gracefully |
