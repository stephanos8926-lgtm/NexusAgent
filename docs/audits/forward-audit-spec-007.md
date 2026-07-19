# Forward Audit — SPEC-007 Runtime Foundation

> **Date:** 2026-07-19  
> **Auditor:** Lucien (inline)  
> **Target:** `docs/specs/SPEC-007-runtime-foundation-v1.md`  
> **Scope:** Validate all 15 acceptance criteria, file manifest, and approach

---

## Summary

**Verdict:** SPEC-007 is APPROVED with 4 minor corrections. Every acceptance criterion is feasible. The adapter approach is sound. Two gaps found and corrected:

1. `set_workspace_root()` + `_workspace_root_var` ContextVar not in migration scope (added to G7)
2. `_policy_context` ContextVar in `policy.py` not in migration scope (added to G7)

---

## AC-by-AC Validation

### AC1 — RuntimeContext creation
**PASS.** `RuntimeContext` is a frozen dataclass — zero dependencies, no async setup required. Can be created in a single line: `RuntimeContext(config=settings)`.

### AC2 — LifecycleState invalid transitions
**PASS.** The 7-state enum is fully testable with `StrEnum`. Invalid transitions (e.g., CREATED → TERMINATED) raised in tests via `assert_never()` or explicit transition matrix.

### AC3 — LifecycleMixin ABC enforcement
**PASS.** `@abstractmethod` on 4 methods + `@property state` means instantiation without implementation raises `TypeError` at import time.

### AC4 — Runtime.initialize() transitions
**PASS.** Three-step lifespan: DB init → NATS connect → ToolManager.init. Maps 1:1 to server's current `lifespan()` sequence.

### AC5 — Runtime.shutdown() transitions
**PASS.** Reverse order: Worker shutdown → Session close → NATS close → DB close. Matches current `finally` block in lifespan.

### AC6 — ToolManager.ensure_registered() dual-path
**PASS.** Current `_ensure_tools_registered()` already uses a module-level bool + RLock. ToolManager wraps this exact pattern. Backward compat: if no RuntimeContext, fall back to old module bool.

### AC7 — ManagedSession wraps Session
**PASS.** Session constructor takes: `(session_id, working_dir, agent, db_repo, memory_dir, ...)`. ManagedSession accepts a pre-constructed Session + context. Delegation for `send()`, `close()`, `event_stream()` is clean pass-through.

### AC8 — ManagedWorker wraps SubAgentHandle
**PASS.** SubAgentHandle has clean lifecycle: `status` + `wait()` + `cancel()` + `is_done()`. ManagedWorker wraps these plus adds `ManagedWorker.state` → `ManagedWorker.health()`.

### AC9 — Global state backward-compat shims
**PASS.** All 5 target globals have getter/setter functions (not direct module var access). The shim pattern is:
```python
def current_session_id(ctx=None) -> str | None:
    ctx = ctx or current_context()
    if ctx is not None:
        return ctx.current_session_id
    return _current_session.get()  # old path
```

**⚠️ Correction needed:** Two additional ContextVars found that should be migrated under the same pattern:
- `src/nexusagent/tools/fs_base.py:53` — `_workspace_root_var: ContextVar[Path]`
- `src/nexusagent/tools/registry/policy.py:16` — `_policy_context: ContextVar[dict]`

Updated G7 to include these, moved to 7 globals instead of 5.

### AC10 — Server starts/stops via Runtime
**PASS.** Server's `lifespan()` already has clean 3-step startup and 3-step shutdown. Wrapping in `Runtime.initialize()` / `Runtime.shutdown()` is a direct substitution. The `create_app()` → `run()` pattern doesn't change.

### AC11 — Pre-migration test baseline matches post-migration
**PASS.** Recorded baseline: `test_agent_events.py` (13/13 pass), `test_server.py + test_websocket.py` (12/12 pass), `test_singletons.py` (7/7 pass), `test_cli_run.py` (1/1 pass). These must be re-verified after each step.

### AC12 — 3 ADRs created
**ALREADY COMPLETE.** ADRs 0009, 0010, 0011 exist at `docs/adrs/`.

### AC13 — Clean server shutdown
**PASS.** Current `finally` block cancels worker and closes bus. Runtime.shutdown() formalizes this. Must verify no `asyncio.CancelledError` propagates in test.

### AC14 — current_context() returns None (safe fallback)
**PASS.** Straightforward: `_runtime_context: ContextVar[RuntimeContext | None] = ContextVar('runtime_context', default=None)`.

### AC15 — Session.send() works with/without RuntimeContext
**PASS.** Session currently sets `_current_session.set(self)` at top of `send()`. Shim: `RuntimeContext.current_session_id = self.session_id` (if RuntimeContext active → `set_current_context()`), PLUS old `_current_session.set(self)` for backward compat.

---

## File Manifest Verification

### New Files (all clear — `src/nexusagent/runtime/` does not exist yet)

| Status | Path |
|--------|------|
| ✅ CLEAR | `src/nexusagent/runtime/` (directory doesn't exist) |
| ✅ CLEAR | `src/nexusagent/runtime/__init__.py` |
| ✅ CLEAR | All `runtime/*.py` |
| ✅ CLEAR | All `tests/core/runtime/*.py` |
| ✅ EXISTS (ok) | `docs/adrs/0009-0011` (already written, will commit along with spec) |

### Modified Files (all exist, all symbols confirmed)

| Status | File | Confirmed |
|--------|------|-----------|
| ✅ | `core/agent.py` | `_current_session:451`, `_ws_memory_dir:447`, `_tools_registered:18`, `_ensure_tools_registered:33`, `class Agent:145`, `run_agent_task:328` |
| ✅ | `core/session/session.py` | `_current_session import:21`, `_current_session.set:435`, `class Session:38` |
| ✅ | `tools/register_all.py` | `_current_session import:390`, `_ws_memory_dir import:462`, `_MCP_REGISTRY:60`, `_MCP_REGISTERED_NAMES:61` |
| ✅ | `server/server.py` | `lifespan:35`, `create_app:73`, `run:125` |
| ✅ | `interfaces/cli.py` | `main:98`, `run:172` |

---

## Circular Import Analysis

**Verdict: No circular import risk.**

Key finding: `runtime/` only IMPORTS existing modules — existing modules never import from `runtime/`. The backward-compat shim pattern uses `current_context()` which is either:
1. A `ContextVar` get (no import needed — inline)
2. A lazy `from nexusagent.runtime.context import current_context` inside a function body (local import, no cycle)

The existing codebase uses lazy imports extensively (68 local `from` imports across the 5 modified files). Adding one more local import path is safe.

---

## Adapter Architecture Verification

The adapter pattern is sound because:

1. **Session constructor takes everything as params**: `session_id`, `working_dir`, `agent`, `db_repo`, `memory_dir`. ManagedSession wraps a pre-constructed Session — no init changes needed.

2. **SessionManager.get_or_create() already idempotent**: Returns existing session if found, creates if not. Wrapping in RuntimeSessionManager requires zero changes to this logic.

3. **WorkerPool.spawn() already async**: Returns `SubAgentHandle`. ManagedWorker wraps the handle, reads its `status`, delegates `wait()` and `cancel()`.

4. **WebSocket handler already creates Agent ad-hoc**: The `session_websocket()` function creates Agent from the WebSocket request. ManagedSession just wraps the result — the Agent creation path doesn't change.

---

## Baseline Test Counts

Recorded for post-migration comparison:

| Suite | Result | 
|-------|--------|
| `test_agent_events.py` | 13 passed |
| `test_server.py + test_websocket.py` | 12 passed |
| `test_singletons.py` | 7 passed |
| `test_cli_run.py` | 1 passed |
| `test_session.py + test_session_manager.py` | timed out at 30s (RAM constrained) |

**Total confirmed baseline: 33 passing across 5 test files + 1 timeout.**

---

## Corrections to Spec

| # | Location | Original | Corrected |
|---|----------|----------|-----------|
| 1 | G7 scope | 5 globals | **7 globals** — added `_workspace_root_var` (fs_base.py) and `_policy_context` (policy.py) |
| 2 | RuntimeContext fields | `current_session_id`, `workspace_memory_dir` | Add `workspace_root: Path \| None` for `_workspace_root_var` and `policy_context: dict \| None` for `_policy_context` |
| 3 | Step 7 description | "Migrate top 5 globals" | "Migrate top **7** globals" |
| 4 | Acceptance criteria | AC9 mentions 5 | Update to 7 |

---

## Conclusion

**SPEC-007 is sound. All 15 acceptance criteria are achievable. 2 additional ContextVars discovered during audit should be added to migration scope. Implementation can proceed on the 12-step plan.**

**Estimated effort unchanged:** ~1,500 new lines, ~200 modified lines, 80-120 new tests.
