# SPEC-007 — Runtime Foundation (Phase 1)

> **Status:** Draft  
> **Date:** 2026-07-19  
> **Author:** Lucien  
> **Mode:** MEDIUM (architecture-critical, multi-phase foundation)  
> **Depends on:** Nothing (Phase 1 is the base)  
> **Related docs:** `docs/architecture/current-state.md`, `docs/architecture/target-state.md`, `docs/architecture/phase-1-gap-analysis.md`

---

## Problem Statement

NexusAgent has no unified runtime. 20+ module-level singletons with implicit initialization order are scattered across the codebase. Three independent entry points (server, CLI, TUI) each do their own lifecycle management. Agents, sessions, and workers lack identity, explicit lifecycle, and dependency injection — making it impossible to build reliable autonomous execution on top.

The system works today through convention and careful sequencing of global state, but this pattern cannot scale to support durable workers, POL governance, or event-driven orchestration.

---

## Goals

| ID | Priority | Description |
|----|----------|-------------|
| G1 | P0 | Create `Runtime` kernel with explicit `initialize()` and `shutdown()` sequences |
| G2 | P0 | Define `LifecycleState` enum and `LifecycleMixin` ABC for all runtime components |
| G3 | P0 | Create `RuntimeContext` dependency injection container |
| G4 | P1 | Create `ToolManager` wrapping `_ensure_tools_registered()` |
| G5 | P1 | Create `ManagedSession` wrapping existing `Session` with lifecycle |
| G6 | P1 | Create `ManagedWorker` wrapping existing workers with identity |
| G7 | P1 | Migrate top-5 global singletons into `RuntimeContext` |
| G8 | P2 | Adapt server lifespan to use `Runtime` |
| G9 | P3 | Adapt CLI `run` command to use `Runtime` |
| G10 | P0 | All existing tests pass post-migration |
| G11 | P0 | Create ADRs for lifecycle model, DI design, adapter strategy |

---

## Compatibility & Behavior Rules

### Rule 1 — Backward Compatibility First
The existing system MUST continue working **without** a Runtime. Creating a Runtime is optional. Old code paths (module-level singletons, ContextVars) must fall back gracefully when no Runtime is present.

### Rule 2 — Adapters, Not Rewrites
Existing classes (`Session`, `SessionManager`, `NexusWorker`, `WorkerPool`, `Agent`) are NOT modified in their core logic. They are wrapped by adapter classes (`ManagedSession`, `ManagedWorker`).

### Rule 3 — Runtime Does Not Own Agent Logic
The Runtime provides lifecycle, DI, and identity — NOT planning, reasoning, policy, or execution. Agent execution remains in `core/agent.py` and `core/worker/handler.py`.

### Rule 4 — No New Dependencies
Phase 1 adds zero new pip packages. All code uses stdlib + existing project dependencies.

### Rule 5 — Runtime is Optional at Startup
Entry points SHOULD use Runtime, but legacy code paths that skip Runtime creation must still work. This ensures we can roll back per-commit.

### Rule 6 — Thread Safety
`RuntimeContext` is read-only after initialization (no setters on the dataclass). Shared mutable state (session map, worker map) uses the same locking patterns as current code.

---

## File Manifest

### New Files (~20)

| # | File | Description | Lines |
|---|------|-------------|-------|
| 1 | `src/nexusagent/runtime/__init__.py` | Package init, exports all public API | ~30 |
| 2 | `src/nexusagent/runtime/lifecycle.py` | `LifecycleState` enum, `LifecycleMixin` ABC, `HealthStatus` | ~80 |
| 3 | `src/nexusagent/runtime/context.py` | `RuntimeContext` dataclass, `current_context()` helper | ~100 |
| 4 | `src/nexusagent/runtime/runtime.py` | `Runtime` class with `initialize()` and `shutdown()` | ~200 |
| 5 | `src/nexusagent/runtime/tools.py` | `ToolManager` wrapping registration guard | ~80 |
| 6 | `src/nexusagent/runtime/session.py` | `ManagedSession`, `RuntimeSessionManager` | ~150 |
| 7 | `src/nexusagent/runtime/worker.py` | `ManagedWorker`, `RuntimeWorkerManager` | ~150 |
| 8 | `docs/adrs/0009-runtime-lifecycle-model.md` | Lifecycle design decision | ~50 |
| 9 | `docs/adrs/0010-runtime-dependency-injection.md` | DI container design decision | ~50 |
| 10 | `docs/adrs/0011-phase-1-adapter-strategy.md` | Adapter pattern decision | ~50 |
| 11 | `tests/core/runtime/__init__.py` | Test package init | ~5 |
| 12 | `tests/core/runtime/test_lifecycle.py` | Lifecycle state machine tests | ~100 |
| 13 | `tests/core/runtime/test_runtime_context.py` | Context creation and access tests | ~80 |
| 14 | `tests/core/runtime/test_runtime.py` | Runtime init/shutdown tests | ~120 |
| 15 | `tests/core/runtime/test_tool_manager.py` | ToolManager registration tests | ~80 |
| 16 | `tests/core/runtime/test_managed_session.py` | ManagedSession adapter tests | ~100 |
| 17 | `tests/core/runtime/test_managed_worker.py` | ManagedWorker adapter tests | ~100 |
| 18 | `tests/core/runtime/test_global_migration.py` | Backward compat tests for global state | ~80 |

### Modified Files (~5)

| # | File | Change | Risk |
|---|------|--------|------|
| 1 | `src/nexusagent/core/agent.py` | Add RuntimeContext shims for `_current_session`, `_ws_memory_dir`, `_tools_registered`; Agent accepts optional RuntimeContext | HIGH |
| 2 | `src/nexusagent/core/session/session.py` | Set `context.current_session_id` alongside `_current_session.set()` | MEDIUM |
| 3 | `src/nexusagent/tools/register_all.py` | Read context fields alongside ContextVars | LOW |
| 4 | `src/nexusagent/server/server.py` | lifespan creates Runtime → delegate init/shutdown | MEDIUM |
| 5 | `src/nexusagent/interfaces/cli.py` | Optional Runtime for `nexus run` path | LOW |

### Untouched (~103 files)

Core agent logic, SessionBase, worker handler, all tools, memory system, LangGraph, TUI, NATS bus, config, DB, auth, hooks, widgets, remaining interfaces, tests (other than new runtime tests).

---

## Acceptance Criteria

- [ ] AC1: `RuntimeContext` can be created with all fields accessible
- [ ] AC2: `LifecycleState` rejects all invalid transitions (e.g., CREATED → TERMINATED without going through RUNNING)
- [ ] AC3: `LifecycleMixin` ABC cannot be instantiated without implementing `state`, `initialize`, `shutdown`, `health`
- [ ] AC4: `Runtime.initialize()` transitions through CREATED → INITIALIZING → RUNNING
- [ ] AC5: `Runtime.shutdown()` transitions through RUNNING → TERMINATING → TERMINATED
- [ ] AC6: `ToolManager.ensure_registered()` works both with and without a RuntimeContext
- [ ] AC7: `ManagedSession` wraps a `Session` instance and reports its lifecycle state
- [ ] AC8: `ManagedWorker` wraps a `SubAgentHandle` and reports its lifecycle state
- [ ] AC9: The 5 migrated globals (`_current_session`, `_ws_memory_dir`, `_tools_registered`, `_session_manager_instance`, hooks `_manager`) have backward-compat shims
- [ ] AC10: Server starts and stops via `Runtime` without changing REST or WebSocket behavior
- [ ] AC11: Pre-migration test baseline matches post-migration (no regressions)
- [ ] AC12: 3 new ADRs created and committed
- [ ] AC13: Server stops cleanly (no hung tasks, no exceptions in shutdown)
- [ ] AC14: `current_context()` returns `None` when no Runtime is active (safe fallback)
- [ ] AC15: `Session.send()` works identically with and without RuntimeContext

---

## Rollback Plan

Every step is a self-contained commit. Full rollback:

```bash
git log --oneline | grep "phase-1:" | tail -1   # find first commit SHA
git revert <first-sha>..HEAD --no-edit            # batch revert all commits
```

Per-step rollback:
```bash
git revert <step-commit> --no-edit
```

Because adapters wrap rather than replace, reverting any step leaves the old code path working immediately. No data migration required.

---

## Key Risks

| Risk | Mitigation |
|------|-----------|
| Circular imports between `runtime/` and existing modules | `runtime/` imports existing modules, NOT vice versa. RuntimeContext injected lazily via `set_current_context()` |
| Test env doesn't create Runtime — old path still used | Shims fall back to module-level state when no RuntimeContext active |
| RAM pressure (385MB) slows full test suite | Run targeted tests per step (`tests/core/runtime/` + affected module's tests) |
| Server lifespan change crashes startup | Maintain legacy lifespan path as backup; test with mock before server integration |
| ContextVar shims miss a code path | Exhaustive grep for all `_current_session`, `_ws_memory_dir`, `_tools_registered` references before and after migration |

---

**Document version:** 1.0  
**Total new code:** ~1,500 lines  
**Total modified code:** ~200 lines  
**New tests:** ~80-120  
**Zero new dependencies**
