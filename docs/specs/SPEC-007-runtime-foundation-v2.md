# SPEC-007 — Runtime Foundation (Phase 1)

> **Status:** FINAL — Approved  
> **Version:** 2.0 (audit-corrected)  
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
| G3 | P0 | Create `RuntimeContext` dependency injection container (7 global fields) |
| G4 | P1 | Create `ToolManager` wrapping `_ensure_tools_registered()` |
| G5 | P1 | Create `ManagedSession` wrapping existing `Session` with lifecycle |
| G6 | P1 | Create `ManagedWorker` wrapping existing workers with identity |
| G7 | P1 | **Migrate top-7** global singletons into `RuntimeContext` |
| G8 | P2 | Adapt server lifespan to use `Runtime` |
| G9 | P3 | Adapt CLI `run` command to use `Runtime` |
| G10 | P0 | All existing tests pass post-migration |
| G11 | P0 | ADRs 0009-0011 committed |

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
`RuntimeContext` is a frozen dataclass (read-only after init). Shared mutable state (session map, worker map) uses the same locking patterns as current code.

### Rule 7 — Policy Context is Session-Scoped
`policy_context` lives on `RuntimeContext` but is **owned by ManagedSession**, not Runtime. ManagedSession sets it during `initialize()` and clears it during `shutdown()`. This matches the current `set_policy_context()` / `clear_policy_context()` lifecycle.

### Rule 8 — Shutdown Is Error-Isolated
Each step of `Runtime.shutdown()` is individually try/caught. A failure in one step (e.g., `bus.close()`) does not prevent subsequent steps (e.g., `db.close()`).

---

## File Manifest

### New Files (~21)

| # | File | Description | Lines |
|---|------|-------------|-------|
| 1 | `src/nexusagent/runtime/__init__.py` | Package init, exports all public API | ~30 |
| 2 | `src/nexusagent/runtime/lifecycle.py` | `LifecycleState` enum, `LifecycleMixin` ABC, `HealthStatus` | ~80 |
| 3 | `src/nexusagent/runtime/context.py` | `RuntimeContext` dataclass (7 fields + helpers), `current_context()`, `set_current_context()` | ~120 |
| 4 | `src/nexusagent/runtime/runtime.py` | `Runtime` class with `initialize()` and `shutdown()` (error-isolated) | ~200 |
| 5 | `src/nexusagent/runtime/tools.py` | `ToolManager` wrapping registration guard + MCP loading | ~80 |
| 6 | `src/nexusagent/runtime/session.py` | `ManagedSession`, `RuntimeSessionManager` | ~150 |
| 7 | `src/nexusagent/runtime/worker.py` | `ManagedWorker`, `RuntimeWorkerManager` | ~150 |
| 8 | `docs/adrs/0009-runtime-lifecycle-model.md` | Lifecycle design decision | ~50 |
| 9 | `docs/adrs/0010-runtime-dependency-injection.md` | DI container design decision | ~50 |
| 10 | `docs/adrs/0011-phase-1-adapter-strategy.md` | Adapter pattern decision | ~50 |
| 11 | `docs/audits/forward-audit-spec-007.md` | Forward audit results | ~80 |
| 12 | `docs/audits/reverse-audit-spec-007.md` | Reverse audit results (7 gaps) | ~100 |
| 13 | `docs/synthesis/SPEC-007-synthesis-v1.md` | Combined audit synthesis | ~100 |
| 14 | `tests/core/runtime/__init__.py` | Test package init | ~5 |
| 15 | `tests/core/runtime/test_lifecycle.py` | Lifecycle state machine tests | ~100 |
| 16 | `tests/core/runtime/test_runtime_context.py` | Context creation and access tests | ~80 |
| 17 | `tests/core/runtime/test_runtime.py` | Runtime init/shutdown tests | ~120 |
| 18 | `tests/core/runtime/test_tool_manager.py` | ToolManager registration tests | ~80 |
| 19 | `tests/core/runtime/test_managed_session.py` | ManagedSession adapter tests | ~100 |
| 20 | `tests/core/runtime/test_managed_worker.py` | ManagedWorker adapter tests | ~100 |
| 21 | `tests/core/runtime/test_global_migration.py` | Backward compat tests for 7 global shims | ~100 |

### Modified Files (7 — expanded from 5 by audit findings)

| # | File | Change | Risk |
|---|------|--------|------|
| 1 | `src/nexusagent/core/agent.py` | Add RuntimeContext shims for `_current_session`, `_ws_memory_dir`, `_tools_registered`; Agent accepts optional RuntimeContext | HIGH |
| 2 | `src/nexusagent/core/session/session.py` | Set `context.current_session_id` alongside `_current_session.set()` | MEDIUM |
| 3 | `src/nexusagent/tools/register_all.py` | Read context fields alongside ContextVars | LOW |
| 4 | `src/nexusagent/tools/fs_base.py` | **ADDED by audit** — Shim `_workspace_root_var` to read from `RuntimeContext.workspace_root` | LOW |
| 5 | `src/nexusagent/tools/registry/policy.py` | **ADDED by audit** — Shim `_policy_context` to read from `RuntimeContext.policy_context`; ManagedSession owns lifecycle | LOW |
| 6 | `src/nexusagent/server/server.py` | lifespan creates Runtime → delegate init/shutdown | MEDIUM |
| 7 | `src/nexusagent/interfaces/cli.py` | Optional Runtime for `nexus run` path | LOW |

### Untouched (~100 files)

Core agent logic (`core/graph.py`, `core/orchestration.py`, `core/trust.py`), SessionBase, worker handler (`core/worker/handler.py`), NexusWorker (`core/worker/worker.py`), WorkerPool (`core/worker/pool.py`), SubAgentHandle, all 25+ individual tools, memory system (10+ files), LangGraph, TUI (widgets, app, streaming), NATS bus, config, DB, auth, hooks, remaining interfaces, ~60 test files.

---

## Seven Global Singletons — Migration Target

| # | Symbol | File | Type | RuntimeContext Field | Migration Pattern |
|---|--------|------|------|---------------------|-------------------|
| 1 | `_current_session` | `core/agent.py:450` | `ContextVar[Any]` | `current_session_id: str \| None` | Dual-path: set both ctx field + ContextVar; read from ctx if active |
| 2 | `_ws_memory_dir` | `core/agent.py:446` | `ContextVar[str]` | `workspace_memory_dir: str \| None` | Dual-path: set both ctx field + ContextVar; read from ctx if active |
| 3 | `_tools_registered` | `core/agent.py:18` | `bool` | `tool_initialized: bool` | ToolManager owns the bool; getter checks ctx first, falls back to module var |
| 4 | `_session_manager_instance` | `core/session/manager.py:268` | `SessionManager \| None` | (owned by `Runtime.session_manager`) | `get_session_manager()` returns Runtime's instance if active, else lazy singleton |
| 5 | `_manager` (HookManager) | `hooks/__init__.py:157` | `HookManager \| None` | `hook_manager` | Runtime creates HookManager → stores on ctx; old `get_hook_manager()` checks ctx first |
| 6 | `_workspace_root_var` | `tools/fs_base.py:53` | `ContextVar[Path]` | `workspace_root: Path \| None` | **Added by audit.** Dual-path like `_current_session` |
| 7 | `_policy_context` | `tools/registry/policy.py:16` | `ContextVar[dict]` | `policy_context: dict \| None` | **Added by audit.** Owned by ManagedSession lifecycle |

---

## RuntimeContext Fields (Final)

```python
@dataclass
class RuntimeContext:
    """Explicit dependency injection container."""
    
    # System identity
    config: ConfigSchema
    
    # Tool system (set by ToolManager)
    tool_registry: ToolRegistry | None = None
    tool_roles: dict[str, list[str]] | None = None
    tool_initialized: bool = False
    
    # Session identity (G1 — migrated from _current_session)
    current_session_id: str | None = None
    workspace_memory_dir: str | None = None     # G2 — migrated from _ws_memory_dir
    
    # Workspace path jail (G6 — migrated from _workspace_root_var)
    workspace_root: Path | None = None
    
    # Tool policy (G7 — migrated from _policy_context; owned by ManagedSession)
    policy_context: dict | None = None
    
    # Sub-system references (set by Runtime)
    bus: AgentBus | None = None
    db_manager: DBManager | None = None
    hook_manager: HookManager | None = None     # G5 — migrated from hooks._manager
```

---

## Shutdown Error Isolation Pattern

```python
async def shutdown(self) -> None:
    self.state = LifecycleState.TERMINATING
    
    # Step 1: Stop workers
    try:
        await self._worker_manager.shutdown()
    except Exception as e:
        logger.warning("Worker shutdown failed (continuing): %s", e)
    
    # Step 2: Close sessions
    try:
        await self._session_manager.shutdown()
    except Exception as e:
        logger.warning("Session shutdown failed (continuing): %s", e)
    
    # Step 3: Close NATS
    try:
        if self._context.bus:
            await self._context.bus.close()
    except Exception as e:
        logger.warning("Bus close failed (continuing): %s", e)
    
    # Step 4: Close DB
    try:
        if self._context.db_manager:
            await self._context.db_manager.close()
    except Exception as e:
        logger.warning("DB close failed (continuing): %s", e)
    
    self.state = LifecycleState.TERMINATED
```

---

## ManagedSession Policy Context Lifecycle

```python
class ManagedSession(LifecycleMixin):
    async def initialize(self) -> None:
        self._state = LifecycleState.INITIALIZING
        # Policy context is session-scoped — set here, cleared on shutdown
        if self._context is not None and self._session.policy is not None:
            self._context.policy_context = self._session.policy
        self._state = LifecycleState.RUNNING
    
    async def shutdown(self) -> None:
        self._state = LifecycleState.TERMINATING
        if self._context is not None:
            self._context.policy_context = None  # clear on session end
        await self._session.close()
        self._state = LifecycleState.TERMINATED
```

---

## Acceptance Criteria

- [ ] AC1: `RuntimeContext` can be created with all 7 global fields + config accessible
- [ ] AC2: `LifecycleState` rejects all invalid transitions (e.g., CREATED → TERMINATED)
- [ ] AC3: `LifecycleMixin` ABC cannot be instantiated without implementing all abstract members
- [ ] AC4: `Runtime.initialize()`: CREATED → INITIALIZING → RUNNING (3-step: DB → NATS → ToolManager)
- [ ] AC5: `Runtime.shutdown()`: RUNNING → TERMINATING → TERMINATED (error-isolated, each step try/caught)
- [ ] AC6: `ToolManager.ensure_registered()` works with and without RuntimeContext
- [ ] AC7: `ManagedSession` wraps Session, reports lifecycle state, delegates send/close/event_stream
- [ ] AC8: `ManagedWorker` wraps SubAgentHandle, reports lifecycle state, delegates wait/cancel
- [ ] AC9: **All 7 globals** have backward-compat shims that fall back to module-level state when Runtime is inactive
- [ ] AC10: Server starts and stops via `Runtime` without changing REST or WebSocket behavior
- [ ] AC11: Pre-migration test baseline matches post-migration (33 passing across 5 targeted suites)
- [ ] AC12: 3 ADRs (0009, 0010, 0011) committed
- [ ] AC13: Server stops cleanly — no hung tasks, no uncaught exceptions in shutdown
- [ ] AC14: `current_context()` returns `None` when no Runtime is active (safe fallback)
- [ ] AC15: `Session.send()` works identically with and without RuntimeContext
- [ ] **AC16 (new):** `_workspace_root_var` shim in `fs_base.py` reads from `RuntimeContext.workspace_root` when active
- [ ] **AC17 (new):** `_policy_context` shim in `policy.py` reads from `RuntimeContext.policy_context` when active; ManagedSession owns the lifecycle

---

## Audit Resolution Matrix

| Finding | Source | Resolution | Applied To |
|---------|--------|-----------|------------|
| G7 scope: 5 → 7 globals | Forward | Added `_workspace_root_var` + `_policy_context` | Goals, File Manifest, RuntimeContext fields, AC9, AC16-17 |
| RuntimeContext gets 2 more fields | Forward | `workspace_root: Path \| None`, `policy_context: dict \| None` | RuntimeContext dataclass + ADR 0010 |
| Step 7: "5 globals" → "7 globals" | Forward | Updated all references | This document |
| `settings` not in scope | Reverse (R2) | Deferred to Phase 2+ | Risk Register |
| `test_singletons.py` awareness | Reverse (R3) | Doc'd: `set_session_manager()` bypasses Runtime | Compatibility Rules |
| `create_task()` ContextVar boundary | Reverse (R4) | Mitigated: RuntimeContext stored as attribute, not ContextVar | Compatibility Rules + Design Notes |
| Policy context is session-scoped | Reverse (R5) | ManagedSession owns `policy_context` lifecycle | Rule 7, ManagedSession section, AC17 |
| Shutdown error isolation | Reverse (R6) | Each step individually try/caught | Rule 8, Shutdown Pattern section, AC5 |
| RAM-limited test baseline | Reverse (R7) | Targeted test runs per step | Risk Register |
| Lack of policy_context lifecycle docs | Reverse (R5) | New section: ManagedSession Policy Context Lifecycle | This document |

---

## Design Notes Addressing Audit Gaps

### create_task() Boundary (R4 Resolution)

`RuntimeContext` survives `asyncio.create_task()` boundaries because:
1. **Primary mechanism:** RuntimeContext is passed as a constructor argument to components (e.g., `ManagedSession(session, context=ctx)`) and stored as `self._context`. Attribute access survives task boundaries.
2. **Secondary mechanism (fallback):** `current_context()` ContextVar provides a convenience read path for non-Runtime-aware code during the transition period.
3. **Tertiary mechanism (legacy):** Old module-level ContextVars remain active. Code that uses `_current_session.get()` directly (not through Runtime) continues to work.

This is a temporary three-layer architecture. After Phase 4, all consumers will use explicit RuntimeContext passing.

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

## Key Risks (Updated with Audit Findings)

| Risk | Mitigation | Source |
|------|-----------|--------|
| Circular imports between `runtime/` and existing modules | `runtime/` imports existing modules, NOT vice versa. Lazy imports in function bodies. | Design |
| Test env doesn't create Runtime — old path still used | 7 global shims fall back to module-level state when no RuntimeContext active | Design |
| RAM pressure (389MB) slows full test suite | Run targeted tests per step; full suite only on explicit request | R7 |
| Server lifespan change crashes startup | Maintain legacy lifespan as backup path | R3 |
| ContextVar shims miss a code path | Exhaustive grep for all 7 ContextVar references before and after migration | Design |
| `create_task()` boundaries break ContextVar reads | RuntimeContext stored as component attribute (not ContextVar) — survives task boundaries | R4 |
| `test_singletons.py` getter tests assume module-level | `set_session_manager()` always sets module-level instance (bypasses Runtime) | R3 |
| `settings` singleton remains global | Intentional — config is read-only, thread-safe, cross-cutting. Not migrating until Phase 2+ | R2 |

---

**Document version:** 2.0 (audit-corrected)  
**Total new code:** ~1,600 lines (+100 from audit additions)  
**Total modified code:** ~250 lines (+50 from 2 additional files)  
**New tests:** ~100-130 (+20 from global migration tests)  
**Zero new dependencies**  
**7 global singletons targeted** (up from 5)  
**7 modified files** (up from 5)  
**17 acceptance criteria** (up from 15)
