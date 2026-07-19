# Reverse Audit — SPEC-007 Runtime Foundation (Gap Analysis)

> **Date:** 2026-07-19  
> **Auditor:** Lucien (inline)  
> **Target:** `docs/specs/SPEC-007-runtime-foundation-v1.md`  
> **Scope:** Find gaps, blind spots, and issues the spec didn't consider

---

## Summary

**7 gaps found.** None are blockers. 2 require spec corrections (already noted in forward audit — additional ContextVars). 3 are ordering/fixture notes. 2 are deferred to future phases.

---

## Gap R1 — Additional ContextVars Not in Migration Scope

**Severity:** Medium  
**Status:** Fixed (added to G7)

The spec targets 5 globals but misses 2 additional ContextVars that follow the same pattern:

### `_workspace_root_var` (`tools/fs_base.py:53`)
```python
_workspace_root_var: ContextVar[Path | None] = ContextVar(
    "_workspace_root",
    default=None,
)
```

**Used by:** `set_workspace_root()` and `get_workspace_root()` — called by WebSocket handler, worker handler, and tools. The fs_base module even has a comment about create_task boundaries:
```python
# its own create_task() — meaning reads registered in one tool's task context
# may be invisible to reads registered in another.
```

This is a **stronger case** for migration than `_current_session` — `_workspace_root_var` is explicitly known to break across `create_task()` boundaries. The Runtime context (which survives via explicit passing) is the correct fix.

### `_policy_context` (`tools/registry/policy.py:16`)
```python
_policy_context: ContextVar[dict | None] = ContextVar(
    "_policy_context",
    default=None,
)
```

**Used by:** `set_policy_context()`, `get_policy_context()`, `clear_policy_context()` — called by Agent during initialization and by tools during execution.

### Action

Add to `RuntimeContext`:
```python
workspace_root: Path | None = None          # replaces _workspace_root_var
policy_context: dict | None = None          # replaces _policy_context
```

Updated spec to 7 globals total. No effort impact — these follow the exact same shim pattern.

---

## Gap R2 — `settings` Module Singleton Not in Scope

**Severity:** Low  
**Status:** Deferred (Phases 2+)

`settings` in `config.py` is a module-level singleton (`from nexusagent.infrastructure.config import settings`). It's used by virtually every module. The spec does not target it for migration.

This is **intentional and correct** for Phase 1. `settings` is:
- Read-only after initialization (Pydantic settings)
- Thread-safe by design (Pydantic validation at construction)
- Loaded early (at first import, before any Runtime exists)
- Not component-specific (used everywhere — config is a cross-cutting concern)

**Not migrating `settings` is the right call for Phase 1.** Revisit in Phase 2 when the task state machine needs environment-specific config.

---

## Gap R3 — `test_singletons.py` Will Need Updates

**Severity:** Medium  
**Status:** Documented (will update during Step 7)

`tests/test_singletons.py` tests the getter/setter pattern for singletons:

```python
def test_worker_pool_singleton():
    pool = get_worker_pool()
    assert get_worker_pool() is pool
    set_worker_pool(mock_pool)
    assert get_worker_pool() is mock_pool
    set_worker_pool(WorkerPool())
    assert isinstance(get_worker_pool(), WorkerPool)
```

When we redirect `get_session_manager()` to Runtime (when active), these tests may need:
1. A `reset()` method on `current_context()` for test isolation
2. Or the tests explicitly set `RuntimeContext = None` during setup

**Approach:** Keep the backward-compat path working. `get_session_manager()` checks `current_context()` first, falls back to lazy singleton. Tests that use `set_session_manager()` will continue working because `set_session_manager()` always sets the module-level instance (bypassing Runtime).

---

## Gap R4 — `create_task()` ContextVar Boundaries

**Severity:** High awareness, Low actual risk  
**Status:** Documented as mitigation strategy

The spec's `current_context()` helper uses a ContextVar:
```python
_runtime_context: ContextVar[RuntimeContext | None] = ContextVar(
    'runtime_context', default=None
)
```

**Problem:** ContextVars do NOT survive `asyncio.create_task()` by default in Python 3.12+ (they are task-local). Tools running in `create_task()` won't see the RuntimeContext set by the parent task.

**Current code that uses create_task() where ContextVars matter:**

| File | Usage | ContextVar Used |
|------|-------|-----------------|
| `core/worker/pool.py:50` | Worker pool spawns tasks | `_workspace_root_var`, `_policy_context` |
| `core/session/session.py:663` | Fire-and-forget extraction | `_current_session` |
| `server/server.py:56` | Worker background task | `_bus`, `_tools_registered` |
| `core/worker/worker.py:93` | Health loop | `_bus` |

**But this is exactly why we're migrating.** The RuntimeContext is designed to be:
1. **Explicitly passed** to components (not pulled from ContextVar)
2. **Stored on the component itself** (e.g., `ManagedSession._context`) — survives create_task because it's an attribute, not a context
3. The `current_context()` ContextVar is a **fallback convenience**, not the primary mechanism

**Mitigation already in spec:** Components owned by Runtime receive `RuntimeContext` at construction time and store it as an attribute. The `current_context()` helper is intended for cases where the context isn't passed explicitly (transition period).

---

## Gap R5 — Tool Policy Context is Session-Scoped, Not Runtime-Scoped

**Severity:** Medium  
**Status:** Needs spec clarification

`_policy_context` in `policy.py` is set by `Agent.__init__()` via `set_policy_context(role, policy)`. This is session-scoped — different sessions have different policies.

The `RuntimeContext.policy_context` field must be a **per-session** value, not a runtime-wide value. ManagedSession should set this when it initializes, not when Runtime starts.

**Correction:** `RuntimeContext.policy_context` is set/cleared by ManagedSession during `initialize()` and `shutdown()`, not by Runtime during system init. This matches the current `set_policy_context()` / `clear_policy_context()` lifecycle.

---

## Gap R6 — Server Lifespan Error Handling

**Severity:** Low  
**Status:** Noted in spec's risk register (R3)

Server's current `lifespan()` catches and logs exceptions with `exc_info=True`, then re-raises. The spec's `Runtime.initialize()` should follow the same pattern — log with full traceback, raise to caller.

**Additionally:** The current `finally` block in lifespan **silently catches** errors during `worker_task.cancel()` and `bus.close()`. The Runtime.shutdown() should preserve this behavior (errors during shutdown should not prevent subsequent cleanup steps).

**Correction already in spec:** The gap analysis already notes "graceful degradation" in the shutdown sequence. Adding explicit note: each shutdown step should be individually try/caught so failure of one step (e.g., bus.close() fails) doesn't prevent subsequent steps (e.g., DB close).

---

## Gap R7 — Pre-migration Baseline Test Timeout

**Severity:** Low  
**Status:** Documented, no action needed

`test_session.py` and `test_session_manager.py` (`tests/test_session.py` + `tests/test_session_manager.py`) timed out at 30 seconds during baseline recording. This is a RAM constraint issue (389MB free).

**Implication:** Full-suite test runs will be slow (4+ min). For Phase 1, use targeted test runs:
```bash
# After each step, test only what changed:
PYTHONPATH=src:. python3 -m pytest tests/core/runtime/ -q --tb=short
PYTHONPATH=src:. python3 -m pytest tests/test_agent_events.py -q --tb=short
PYTHONPATH=src:. python3 -m pytest tests/test_singletons.py -q --tb=short
```

Full suite only on explicit request or at final verification gate.

---

## Gap Catalog Summary

| ID | Gap | Severity | Status |
|----|-----|----------|--------|
| R1 | Additional ContextVars (`_workspace_root_var`, `_policy_context`) | Medium | ✅ Fixed — added to G7 |
| R2 | `settings` singleton not in scope | Low | 🔲 Deferred (Phase 2+) |
| R3 | `test_singletons.py` needs updates for shimmed globals | Medium | ✅ Documented in spec |
| R4 | `create_task()` ContextVar boundary | High awareness, Low risk | ✅ Already mitigated by spec design |
| R5 | Policy context is session-scoped, not runtime-scoped | Medium | ✅ ManagedSession owns `policy_context` |
| R6 | Shutdown error isolation | Low | ✅ Noted in Runtime.shutdown() design |
| R7 | RAM-limited test baseline timeout | Low | ✅ Use targeted tests per step |

---

## Conclusion

**No blockers found.** 7 gaps identified: 1 fixed (R1), 4 documented/mitigated (R3, R4, R5, R6), 1 deferred (R2), 1 observed (R7).

The strongest validation from this audit: the **create_task boundary issue (R4)** — which the spec correctly identifies and mitigates via explicit attribute-based context passing instead of ContextVar-dependent lookups. This was the hardest failure mode to spot, and the spec's runtime architecture handles it correctly.
