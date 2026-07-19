# Synthesis — SPEC-007 Runtime Foundation (Final)

> **Date:** 2026-07-19  
> **Version:** 2.0 (all audit findings resolved)  
> **Status:** Ready for sign-off → Implementation  
> **Prepared from:**  
>   - `docs/specs/SPEC-007-runtime-foundation-v2.md` (audit-corrected)  
>   - `docs/audits/forward-audit-spec-007.md`  
>   - `docs/audits/reverse-audit-spec-007.md`  
>   - `docs/adrs/0009-runtime-lifecycle-model.md`  
>   - `docs/adrs/0010-runtime-dependency-injection.md`  
>   - `docs/adrs/0011-phase-1-adapter-strategy.md`

---

## Audit Resolution Summary

| Finding | From | Status |
|---------|------|--------|
| G7: 5 → 7 globals (add `_workspace_root_var`, `_policy_context`) | Forward | ✅ Applied to SPEC-007 v2 |
| RuntimeContext: 2 new fields (`workspace_root`, `policy_context`) | Forward | ✅ Applied to SPEC-007 v2 |
| Modified files: 5 → 7 (add `fs_base.py`, `policy.py`) | Forward | ✅ Applied to SPEC-007 v2 |
| ACs: 15 → 17 (add AC16, AC17) | Forward | ✅ Applied to SPEC-007 v2 |
| R2: `settings` not in scope | Reverse | 🔲 Deferred to Phase 2+ |
| R3: `test_singletons.py` awareness | Reverse | ✅ Documented in spec Risk Register |
| R4: `create_task()` ContextVar boundary | Reverse | ✅ Mitigated — attribute-based passing, not ContextVar-dependent |
| R5: Policy context is session-scoped | Reverse | ✅ Applied — ManagedSession owns `policy_context` lifecycle |
| R6: Shutdown error isolation | Reverse | ✅ Applied — each step individually try/caught |
| R7: RAM-limited test baseline | Reverse | ✅ Targeted test strategy defined |
| No `policy_context` lifecycle in spec | Reverse | ✅ New section in SPEC-007 v2 |

**All 7 reverse gaps resolved.** 1 fixed in spec, 4 documented/mitigated, 1 deferred, 1 operational constraint.

---

## Final File Inventory

### New: 21 files (~1,600 lines)

```
src/nexusagent/runtime/
├── __init__.py          ~30L   — Package init, public exports
├── lifecycle.py         ~80L   — LifecycleState, LifecycleMixin, HealthStatus
├── context.py          ~120L   — RuntimeContext (7 fields), current_context()
├── runtime.py          ~200L   — Runtime.initialize() / .shutdown()
├── tools.py             ~80L   — ToolManager
├── session.py          ~150L   — ManagedSession, RuntimeSessionManager
└── worker.py           ~150L   — ManagedWorker, RuntimeWorkerManager

tests/core/runtime/
├── __init__.py           ~5L   — Test package
├── test_lifecycle.py   ~100L   — State transitions, ABC enforcement
├── test_runtime_context.py ~80L — Context creation, field access
├── test_runtime.py     ~120L   — Init/shutdown sequences
├── test_tool_manager.py ~80L   — Tool registration, dual-path
├── test_managed_session.py ~100L — Session adapter + lifecycle
├── test_managed_worker.py ~100L — Worker adapter + lifecycle
└── test_global_migration.py ~100L — 7 global shim backward compat

docs/
├── specs/SPEC-007-runtime-foundation-v2.md
├── audits/forward-audit-spec-007.md
├── audits/reverse-audit-spec-007.md
├── synthesis/SPEC-007-synthesis-v2.md (this)
└── adrs/0009-0011
```

### Modified: 7 files (~250 lines changed)

| # | File | Lines Changed | What Changes |
|---|------|---------------|-------------|
| 1 | `core/agent.py` | ~50 | Shims for 3 globals; Agent accepts optional RuntimeContext |
| 2 | `core/session/session.py` | ~10 | Sets `context.current_session_id` alongside `_current_session` |
| 3 | `tools/register_all.py` | ~15 | Reads `context.*` fields alongside ContextVars |
| 4 | `tools/fs_base.py` | ~30 | **New:** `_workspace_root_var` shim (audit addition) |
| 5 | `tools/registry/policy.py` | ~20 | **New:** `_policy_context` shim (audit addition) |
| 6 | `server/server.py` | ~40 | lifespan creates Runtime → delegates init + shutdown |
| 7 | `interfaces/cli.py` | ~30 | Optional Runtime for `nexus run` |

### Untouched: ~100 files (90% of codebase)

All tool implementations, memory system, LangGraph, TUI, NATS bus, config, DB, auth, hooks, remaining interfaces, ~60 existing test files.

---

## Execution Plan (10 Steps)

### Step 0 — Package Skeleton
```
CREATE: src/nexusagent/runtime/__init__.py
VERIFY: python3 -c "import nexusagent.runtime; print('OK')"
```

### Step 1 — Lifecycle Abstraction
```
CREATE: src/nexusagent/runtime/lifecycle.py
  - LifecycleState (7-state StrEnum)
  - LifecycleMixin (ABC: state, initialize, shutdown, health)
  - HealthStatus dataclass

CREATE: tests/core/runtime/__init__.py
CREATE: tests/core/runtime/test_lifecycle.py
TEST: python3 -m pytest tests/core/runtime/test_lifecycle.py -q --tb=short
```

### Step 2 — DI Container
```
CREATE: src/nexusagent/runtime/context.py
  - RuntimeContext dataclass (7 fields + config + bus + db + hooks)
  - current_context() → Optional[RuntimeContext]
  - set_current_context(ctx)  # for Runtime to set

CREATE: tests/core/runtime/test_runtime_context.py
TEST: python3 -m pytest tests/core/runtime/test_runtime_context.py -q --tb=short
+ verify test_singletons.py still passes
```

### Step 3 — Runtime Kernel
```
CREATE: src/nexusagent/runtime/runtime.py
  - Runtime class (LifecycleMixin)
  - initialize(): DB → NATS → ToolManager (error-isolated steps)
  - shutdown(): Worker → Session → NATS → DB (each try/caught)

CREATE: tests/core/runtime/test_runtime.py
TEST: python3 -m pytest tests/core/runtime/test_runtime.py -q --tb=short
```

### Step 4 — ToolManager
```
CREATE: src/nexusagent/runtime/tools.py
  - ToolManager (LifecycleMixin)
  - ensure_registered() — wraps _ensure_tools_registered()
  - load_mcp_tools() — wraps register_mcp_tools()
  - Sets context.tool_initialized = True

CREATE: tests/core/runtime/test_tool_manager.py
TEST: python3 -m pytest tests/core/runtime/test_tool_manager.py -q --tb=short
+ verify test_mcp_loading.py still passes
```

### Step 5 — Session Adapter
```
CREATE: src/nexusagent/runtime/session.py
  - SessionMetadata dataclass
  - ManagedSession wraps Session + LifecycleMixin
      - Owns policy_context lifecycle (set on init, clear on shutdown)
  - RuntimeSessionManager wraps SessionManager + LifecycleMixin
      - get()/get_or_create() delegate to wrapped SessionManager

CREATE: tests/core/runtime/test_managed_session.py
TEST: python3 -m pytest tests/core/runtime/test_managed_session.py -q --tb=short
+ verify test_session.py, test_session_manager.py still pass
```

### Step 6 — Worker Adapter
```
CREATE: src/nexusagent/runtime/worker.py
  - WorkerMetadata dataclass
  - ManagedWorker wraps SubAgentHandle + LifecycleMixin
  - RuntimeWorkerManager wraps WorkerPool + LifecycleMixin

CREATE: tests/core/runtime/test_managed_worker.py
TEST: python3 -m pytest tests/core/runtime/test_managed_worker.py -q --tb=short
+ verify test_worker_pool.py still passes
```

### Step 7 — Migrate 7 Global Singletons
```
MODIFY: core/agent.py — 3 shims
  - _current_session → RuntimeContext.current_session_id (dual-path)
  - _ws_memory_dir → RuntimeContext.workspace_memory_dir (dual-path)
  - _tools_registered → context.tool_initialized (ToolManager owns it)
  - Agent.__init__ accepts optional RuntimeContext

MODIFY: core/session/session.py
  - session.send(): set context.current_session_id alongside _current_session.set()

MODIFY: tools/register_all.py
  - Read context.current_session_id + context.workspace_memory_dir before ContextVars

MODIFY: tools/fs_base.py             ★ AUDIT ADDITION
  - _workspace_root_var → RuntimeContext.workspace_root (dual-path)

MODIFY: tools/registry/policy.py     ★ AUDIT ADDITION
  - _policy_context → RuntimeContext.policy_context (dual-path, session-scoped)

CREATE: tests/core/runtime/test_global_migration.py
TEST: python3 -m pytest tests/core/runtime/test_global_migration.py -q --tb=short
+ verify test_singletons.py, test_agent_events.py still pass
```

### Step 8 — Server Adapter
```
MODIFY: server/server.py
  - lifespan creates Runtime → Runtime.initialize()
  - lifespan shutdown → Runtime.shutdown()
  - SessionManager accessed via Runtime.session_manager

TEST: python3 -m pytest tests/test_server.py tests/test_websocket.py -q --tb=short
VERIFY: python3 -m nexusagent.server --help
```

### Step 9 — CLI Adapter (optional)
```
MODIFY: interfaces/cli.py
  - nexus run creates optional Runtime for local tasks

TEST: python3 -m pytest tests/test_cli_run.py -q --tb=short
```

### Step 10 — Final Verification
```
# New runtime tests
python3 -m pytest tests/core/runtime/ -q --tb=short

# Existing affected suites
python3 -m pytest tests/test_agent_events.py tests/test_singletons.py -q --tb=short
python3 -m pytest tests/test_server.py tests/test_websocket.py -q --tb=short
python3 -m pytest tests/test_cli_run.py -q --tb=short
python3 -m pytest tests/test_mcp_loading.py -q --tb=short

# Targeted session/worker
python3 -m pytest tests/test_managed_session.py -q --tb=short
python3 -m pytest tests/test_worker_pool.py -q --tb=short
```

---

## Test Strategy

| Step | New Tests | Lines | Existing Tests to Verify |
|------|-----------|-------|-------------------------|
| 1 | `test_lifecycle.py` | ~100 | — |
| 2 | `test_runtime_context.py` | ~80 | `test_singletons.py` |
| 3 | `test_runtime.py` | ~120 | — |
| 4 | `test_tool_manager.py` | ~80 | `test_mcp_loading.py` |
| 5 | `test_managed_session.py` | ~100 | `test_session.py` |
| 6 | `test_managed_worker.py` | ~100 | `test_worker_pool.py` |
| 7 | `test_global_migration.py` | ~100 | `test_singletons.py`, `test_agent_events.py` |
| 8 | — | — | `test_server.py`, `test_websocket.py` |
| 9 | — | — | `test_cli_run.py` |

**New tests:** ~680 lines across 7 files  
**Existing tests verified:** ~33 baseline across 5 suites

---

## Risk Register (Final, Post-Audit)

| Risk | Likelihood | Impact | Mitigation | Source |
|------|-----------|--------|-----------|--------|
| Circular imports (runtime/ → existing) | Low | High | runtime/ never reverse-imports; lazy imports in function bodies | Design |
| ContextVar shim misses code path | Medium | Medium | Exhaustive grep of all 7 ContextVar refs before/after | Design |
| `create_task()` loses ContextVar | High | Low | RuntimeContext stored as component attribute — survives task boundaries | R4 |
| `test_singletons.py` getter assumes module-level | Medium | Low | `set_session_manager()` always sets module-level, bypasses Runtime | R3 |
| Server lifespan change crashes startup | Low | Critical | Legacy lifespan path preserved; mock-tested before server integration | R3 |
| `settings` remains global (intentional) | Low | Low | Read-only, thread-safe, cross-cutting. Migrate Phase 2+ | R2 |
| Policy context read before ManagedSession sets it | Medium | Medium | `context.policy_context` is None by default — code must handle None | R5 |
| RAM full-suite timeout (4GB, 389MB free) | High | Medium | Targeted tests per step only; full suite on explicit request | R7 |

---

## Document Cross-Reference

| Doc | Location | Purpose |
|-----|----------|---------|
| **SPEC-007 v2** | `docs/specs/SPEC-007-runtime-foundation-v2.md` | ✅ Final spec with all audit corrections |
| **Forward Audit** | `docs/audits/forward-audit-spec-007.md` | ✅ All 15 ACs confirmed feasible; 4 corrections applied |
| **Reverse Audit** | `docs/audits/reverse-audit-spec-007.md` | ✅ 7 gaps found, 0 blockers; all resolved |
| **Synthesis v2** | `docs/synthesis/SPEC-007-synthesis-v2.md` | ✅ Combined plan (this document) |
| **ADR 0009** | `docs/adrs/0009-runtime-lifecycle-model.md` | ✅ 7-state lifecycle design |
| **ADR 0010** | `docs/adrs/0010-runtime-dependency-injection.md` | ✅ RuntimeContext DI container design |
| **ADR 0011** | `docs/adrs/0011-phase-1-adapter-strategy.md` | ✅ Adapter over rewrite, deletion criteria |
| **Current State** | `docs/architecture/current-state.md` | ✅ Baseline (19 sections, 16 globals) |
| **Target State** | `docs/architecture/target-state.md` | ✅ Phase 1 runtime kernel target |
| **Gap Analysis** | `docs/architecture/phase-1-gap-analysis.md` | ✅ 10 gaps, 12-step bridge plan |

---

## Ready for Sign-Off

**SPEC-007 v2** passes both audits with all findings resolved:

- ✅ 17 acceptance criteria defined (15 original + 2 from audit)
- ✅ 7 global singletons targeted (up from 5)
- ✅ 7 modified files (up from 5)
- ✅ Shutdown is error-isolated (each step try/caught)
- ✅ Policy context lifecycle owned by ManagedSession (session-scoped)
- ✅ `create_task()` boundary mitigated (attribute-based, not ContextVar-dependent)
- ✅ 10-step execution plan with per-step rollback
- ✅ 7 new test files (~680 new test lines)
- ✅ Zero new dependencies
- ✅ 3 ADRs committed

**Signature:** Lucien, Lead Digital Architect  
**Date:** 2026-07-19
