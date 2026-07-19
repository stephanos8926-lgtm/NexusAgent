# Phase 1 Gap Analysis — Minimum Bridge

> **Date:** 2026-07-19  
> **From:** Current State (`docs/architecture/current-state.md`)  
> **To:** Target State (`docs/architecture/target-state.md`)  
> **Purpose:** Define the exact scope, steps, and boundaries of Phase 1 migration

---

## Table of Contents

1. [Gap Summary](#gap-summary)
2. [Gap Catalog](#gap-catalog)
3. [Execution Plan](#execution-plan)
4. [Files to Create](#files-to-create)
5. [Files to Modify](#files-to-modify)
6. [Files to Leave Alone](#files-to-leave-alone)
7. [Test Strategy](#test-strategy)
8. [Rollback Strategy](#rollback-strategy)
9. [Risk Register](#risk-register)
10. [Verification Gates](#verification-gates)

---

## Gap Summary

Phase 1 introduces the **Runtime kernel** — a new architectural layer that sits below the existing system and provides explicit lifecycle, dependency injection, execution boundaries, and identity tracking.

**Core insight:** The existing system is NOT being rewritten. A new layer is being **grafted underneath** it, connected via adapters.

### What Phase 1 Delivers

| Capability | Current | Target |
|-----------|---------|--------|
| **Lifecycle model** | Components exist or don't — no states | 7-state machine for all core components |
| **Dependency injection** | `from module import settings` — global singleton | `RuntimeContext` — explicit container |
| **Session identity** | `_current_session` ContextVar in `core.agent` | `RuntimeContext.current_session_id` |
| **Worker identity** | No identity — `NexusWorker` singleton | `ManagedWorker` with ID and lifecycle |
| **Tool registration guard** | `_tools_registered` module bool | `ToolManager.ensure_registered()` method |
| **Runtime entry point** | Three independent startup paths | `Runtime.initialize()` centralized |
| **Graceful shutdown** | Distributed `finally` blocks | `Runtime.shutdown()` orderly teardown |

### What Phase 1 Does NOT Deliver

| Capability | Reason |
|-----------|--------|
| Agent rewrite | Current Agent works — Phase 4 target |
| Session rewrite | Current Session works — adapt into ManagedSession |
| Memory system changes | Works — Phase 9 target |
| New event system | Current NATS bus works — Phase 3 target |
| Policy/capability model | Phase 8 target |
| DAG engine | Phase 6 target |
| POL | Phase 7 target |
| Planner | Phase 5 target |
| WorkerPool rewrite | Migrate into WorkerManager — same pattern, new owner |

---

## Gap Catalog

### Gap G1 — No Lifecycle Abstraction

**Current:** Components have implicit existence. ToolRegistry exists because `from .core import registry` executed. Session exists because code called `Session()`. Worker started because `lifespan()` called `worker.start()`. No component can report what state it's in.

**Target:** Every runtime component implements `LifecycleMixin` with observable state and health.

**Bridge:** Create `runtime/lifecycle.py` with:
- `LifecycleState` enum (7 states)
- `LifecycleMixin` ABC (state, initialize, shutdown, health)
- `HealthStatus` dataclass (healthy, degraded, failed + details)

**Files:**
- CREATE: `src/nexusagent/runtime/lifecycle.py`

---

### Gap G2 — No Dependency Injection Container

**Current:** 20+ module-level singletons with implicit initialization order. Dependencies are imported globally, not passed. Initialization order is load-time dependent (import side effects).

**Target:** `RuntimeContext` dataclass holds all shared dependencies. Components receive context at init time.

**Bridge:** Create `runtime/context.py` with RuntimeContext dataclass that consolidates the 5 highest-impact globals:

| Global | Target Field | Migration |
|--------|-------------|-----------|
| `core.agent._tools_registered` | `context.tool_initialized` | ToolManager sets this; Agent reads from context |
| `core.agent._current_session` | `context.current_session_id` | Session sets this; tools read from context |
| `core.agent._ws_memory_dir` | `context.workspace_memory_dir` | Worker/CLI set this; register_all reads from context |
| `core.session.manager._session_manager_instance` | `runtime.session_manager` | Runtime owns SessionManager |
| `hooks.__init__._manager` | `context.hook_manager` | Runtime provides HookManager |

**Files:**
- CREATE: `src/nexusagent/runtime/context.py`

---

### Gap G3 — No Runtime Entry Point

**Current:** Three independent entry points:
1. `server/server.py:run()` → uvicorn (lifespan does its own init)
2. `interfaces/cli.py:main()` → Click (creates everything ad-hoc)
3. `interfaces/tui/app.py:NexusApp` → Textual (connects to server)

**Target:** A single `Runtime(config)` that manages initialization and shutdown. Each entry point creates a Runtime and delegates to it.

**Bridge:** Create `runtime/runtime.py` with `Runtime` class that:
1. Creates RuntimeContext
2. Initializes subsystem managers (ToolManager, SessionManager, WorkerManager)
3. Manages lifecycle state transitions
4. Provides `initialize()` and `shutdown()` sequences
5. Exposes `context`, `session_manager`, `worker_manager`, `tool_manager`

**Files:**
- CREATE: `src/nexusagent/runtime/runtime.py`
- CREATE: `src/nexusagent/runtime/__init__.py`

---

### Gap G4 — No ManagedSession Wrapper

**Current:** `Session` class (707 lines) combines session state, agent execution, memory management, event streaming, and approval gates. `SessionManager` is a global singleton.

**Target:** `ManagedSession` wraps `Session` with lifecycle tracking and identity. `Runtime.session_manager` owns the collection.

**Bridge:** Create `runtime/session.py` with:
- `SessionMetadata` dataclass (id, created_at, last_active, working_dir)
- `ManagedSession` class implementing LifecycleMixin:
  - Wraps existing `Session` instance via adapter pattern
  - Exposes lifecycle state, health
  - Delegates `send()`, `close()`, `event_stream()` to inner Session
- `RuntimeSessionManager` class:
  - Identical interface to existing `SessionManager`
  - Owned by Runtime, not module-level singleton
  - Wraps current `SessionManager` implementation

**Files:**
- CREATE: `src/nexusagent/runtime/session.py`
- (existing SessionManager stays — will be replaced via adapter)

---

### Gap G5 — No ManagedWorker Wrapper

**Current:** Two worker abstractions:
1. `NexusWorker` — NATS-subscribed daemon (singleton, in-process)
2. `WorkerPool` — local sub-agent pool (singleton, in-process)
Both lack identity and lifecycle tracking beyond "running/not-running."

**Target:** `ManagedWorker` wraps workers with identity, lifecycle, and metadata. `Runtime.worker_manager` owns the collection.

**Bridge:** Create `runtime/worker.py` with:
- `WorkerMetadata` dataclass (id, type, status, started_at)
- `ManagedWorker` class implementing LifecycleMixin:
  - Wraps `SubAgentHandle` for pool workers
  - Wraps `NexusWorker` for NATS worker
  - Tracks identity and lifecycle
- `RuntimeWorkerManager` class:
  - Owned by Runtime
  - Wraps current `WorkerPool` + `NexusWorker` patterns

**Files:**
- CREATE: `src/nexusagent/runtime/worker.py`

---

### Gap G6 — Tool Registration Guard is a Module Bool

**Current:** `core/agent.py` has:
```python
_tools_registered: bool = False
_tools_registered_lock = threading.RLock()
```
These are guarded by a free function `_ensure_tools_registered()` that checks and sets the module-level bool. Every `Agent.__init__()` and `Agent.__call__()` path calls this.

**Target:** `ToolManager.ensure_registered()` method that checks `context.tool_initialized` instead. Agent reads tool initialized state from `ToolManager` on the Runtime.

**Bridge (minimum):**
1. Create `ToolManager` class wrapping the existing registration logic
2. Add `tool_initialized` field to `RuntimeContext`
3. Agent class checks `context.tool_initialized` instead of module-level bool
4. Keep backward compat: `_ensure_tools_registered()` calls `RuntimeContext` if available, else falls back to module bool

**Files:**
- MODIFY: `src/nexusagent/core/agent.py` (add RuntimeContext-aware check)
- (ToolManager lives in runtime/tools.py)

---

### Gap G7 — ContextVar Cross-Module Leaks

**Current:** `core/agent.py` exports `_current_session` and `_ws_memory_dir` ContextVars. Modules like `session/session.py`, `register_all.py`, and `tools/fs_base.py` import these directly from `core.agent`.

```python
# In session/session.py:
from nexusagent.core.agent import _current_session
_current_session.set(self)

# In tools/register_all.py:
from nexusagent.core.agent import _current_session, _ws_memory_dir
session = _current_session.get()
ws = _ws_memory_dir.get()
```

**Target:** ContextVars live in `RuntimeContext` and are accessed through the Runtime. Tools and sessions get context from a Runtime reference, not from `core.agent` imports.

**Bridge (minimum):**
1. Add `current_session_id: str | None` and `workspace_memory_dir: Path | None` to RuntimeContext
2. Create backward-compat shims in `core/agent.py` that read from RuntimeContext if available
3. Session sets `context.current_session_id` instead of `_current_session`
4. Tools read `context.current_session_id` instead of `_current_session.get()`

**Files:**
- MODIFY: `src/nexusagent/core/agent.py` (add shims + RuntimeContext awareness)
- MODIFY: `src/nexusagent/core/session/session.py` (set context field instead of ContextVar)
- MODIFY: `src/nexusagent/tools/register_all.py` (read context field instead of ContextVar)

---

### Gap G8 — No Unified Startup/Shutdown Sequence

**Current:** Server startup is imperative code in `lifespan()`. CLI startup is scattered in `cli.py`. Shutdown is fragmented (finally blocks, atexit handlers, implicit GC).

**Target:** `Runtime.initialize()` and `Runtime.shutdown()` provide the canonical startup/shutdown sequence. Entry points call these, not ad-hoc init code.

**Bridge:**
1. `Runtime.initialize()` sequence:
   - `state = INITIALIZING`
   - Create RuntimeContext
   - Init DB
   - Connect NATS bus
   - Init ToolManager (load MCP tools)
   - Create SessionManager
   - Create WorkerManager
   - Start health monitoring
   - `state = RUNNING`

2. `Runtime.shutdown()` sequence:
   - `state = TERMINATING`
   - Stop WorkerManager (cancel all workers)
   - Shutdown SessionManager (close all sessions)
   - Close NATS bus
   - Close DB
   - `state = TERMINATED`

3. Adapter: Server lifespan creates Runtime → initializes → yields → shutdowns
4. Adapter: CLI commands create Runtime → initialize → work → shutdown

**Files:**
- CREATE: `src/nexusagent/runtime/runtime.py` (initialize/shutdown)
- MODIFY: `src/nexusagent/server/server.py` (use Runtime in lifespan)
- MODIFY: `src/nexusagent/interfaces/cli.py` (use Runtime for local commands)

---

### Gap G9 — No Runtime Tests

**Current:** Zero tests for runtime lifecycle, context, or managed components.

**Target:** Full test coverage for:
- Lifecycle state transitions (valid + invalid)
- RuntimeContext creation and field access
- Runtime.initialize() and Runtime.shutdown()
- ManagedSession lifecycle
- ManagedWorker lifecycle
- Backward compatibility (existing Session still works without Runtime)

**Bridge:** Create `tests/core/runtime/` directory:

**Files:**
- CREATE: `tests/core/runtime/test_lifecycle.py`
- CREATE: `tests/core/runtime/test_runtime_context.py`
- CREATE: `tests/core/runtime/test_runtime.py`
- CREATE: `tests/core/runtime/test_managed_session.py`
- CREATE: `tests/core/runtime/test_managed_worker.py`

---

### Gap G10 — No ADRs for Phase 1 Decisions

**Current:** 8 ADRs exist (`docs/adrs/0001-0008`), none covering runtime architecture decisions.

**Target:** ADRs for:
1. Lifecycle model choice (7-state vs alternatives)
2. DI container design (RuntimeContext dataclass vs DI framework)
3. Adapter vs rewrite decision
4. Singleton migration order and strategy
5. Test strategy (full coverage for new code, backward compat for existing)

**Files:**
- CREATE: `docs/adrs/0009-runtime-lifecycle-model.md`
- CREATE: `docs/adrs/0010-runtime-dependency-injection.md`
- CREATE: `docs/adrs/0011-phase-1-adapter-strategy.md`

---

## Execution Plan

### Ordering Rationale

The migration must build **bottom-up**:
1. First create the abstractions (LifecycleMixin, RuntimeContext)
2. Then create the container (Runtime class)
3. Then wrap existing components (ManagedSession, ManagedWorker)
4. Then migrate consumers (server.py, cli.py)
5. Then remove the old globals
6. Tests at every step

### Step-by-Step

```
Step 0 — Create package skeleton
──────────────────────────────────
  CREATE: src/nexusagent/runtime/__init__.py (package init, exports)

Step 1 — Lifecycle abstraction
──────────────────────────────────
  CREATE: src/nexusagent/runtime/lifecycle.py
    - LifecycleState enum
    - LifecycleMixin ABC
    - HealthStatus dataclass
  TEST: test_lifecycle.py

Step 2 — DI container
──────────────────────────────────
  CREATE: src/nexusagent/runtime/context.py
    - RuntimeContext dataclass (tool_registry, tool_roles, tool_initialized,
      current_session_id, workspace_memory_dir, bus, db, hook_manager)
    - Helper: current_context() → Optional[RuntimeContext]
    - Helper: set_current_context(ctx) (for ContextVar bridge)
  TEST: test_runtime_context.py

Step 3 — Runtime kernel
──────────────────────────────────
  CREATE: src/nexusagent/runtime/runtime.py
    - Runtime class with lifecycle
    - initialize() sequence
    - shutdown() sequence
  TEST: test_runtime.py

Step 4 — ToolManager
──────────────────────────────────
  CREATE: src/nexusagent/runtime/tools.py
    - ToolManager class implementing LifecycleMixin
    - ensure_registered() — wraps current _ensure_tools_registered()
    - load_mcp_tools() — wraps register_mcp_tools()
    - Integrate with RuntimeContext
  MODIFY: Wait — this is wired into Runtime.initialize()
  TEST: Part of runtime tests

Step 5 — Session adapter
──────────────────────────────────
  CREATE: src/nexusagent/runtime/session.py
    - SessionMetadata dataclass
    - ManagedSession (wraps Session, implements LifecycleMixin)
    - RuntimeSessionManager (wraps SessionManager, LifecycleMixin)
  TEST: test_managed_session.py
  VERIFY: Existing session tests still pass (test_session.py)

Step 6 — Worker adapter
──────────────────────────────────
  CREATE: src/nexusagent/runtime/worker.py
    - WorkerMetadata dataclass
    - ManagedWorker (wraps SubAgentHandle, implements LifecycleMixin)
    - RuntimeWorkerManager (wraps WorkerPool, LifecycleMixin)
  TEST: test_managed_worker.py
  VERIFY: Existing worker tests still pass (test_worker_pool.py)

Step 7 — Migrate global state (top 5)
──────────────────────────────────
  MODIFY: src/nexusagent/core/agent.py
    - _current_session → shim reading RuntimeContext
    - _ws_memory_dir → shim reading RuntimeContext
    - _ensure_tools_registered → checks RuntimeContext.tool_initialized first
    - Agent.__init__ accepts optional RuntimeContext

  MODIFY: src/nexusagent/core/session/session.py
    - Sets context.current_session_id instead of _current_session.set()

  MODIFY: src/nexusagent/tools/register_all.py
    - Reads context.current_session_id instead of _current_session.get()
    - Reads context.workspace_memory_dir instead of _ws_memory_dir.get()

  VERIFY: test_session_manager.py, test_session.py pass

Step 8 — Server adapter
──────────────────────────────────
  MODIFY: src/nexusagent/server/server.py
    - lifespan creates Runtime → Runtime.initialize()
    - lifespan shutdown → Runtime.shutdown()
    - SessionManager accessed via Runtime, not global getter
  VERIFY: test_server.py, test_websocket.py

Step 9 — CLI adapter (optional in Phase 1)
──────────────────────────────────
  MODIFY: src/nexusagent/interfaces/cli.py
    - `nexus run` creates Runtime for local tasks
    - Runtime provides WorkerPool via worker_manager
  VERIFY: test_cli_run.py

Step 10 — ADRs
──────────────────────────────────
  CREATE: docs/adrs/0009-runtime-lifecycle-model.md
  CREATE: docs/adrs/0010-runtime-dependency-injection.md
  CREATE: docs/adrs/0011-phase-1-adapter-strategy.md

Step 11 — Final verification
──────────────────────────────────
  Verify all existing tests pass
  Verify server starts and stops cleanly
  Verify session creation and message flow
  Verify worker task execution
```

---

## Files to Create

| File | Purpose | Step |
|------|---------|------|
| `src/nexusagent/runtime/__init__.py` | Package skeleton, exports | 0 |
| `src/nexusagent/runtime/lifecycle.py` | LifecycleState, LifecycleMixin, HealthStatus | 1 |
| `src/nexusagent/runtime/context.py` | RuntimeContext dataclass | 2 |
| `src/nexusagent/runtime/runtime.py` | Runtime class (initialize/shutdown) | 3 |
| `src/nexusagent/runtime/tools.py` | ToolManager | 4 |
| `src/nexusagent/runtime/session.py` | ManagedSession, RuntimeSessionManager | 5 |
| `src/nexusagent/runtime/worker.py` | ManagedWorker, RuntimeWorkerManager | 6 |
| `tests/core/runtime/__init__.py` | Test package | 1+ |
| `tests/core/runtime/test_lifecycle.py` | Lifecycle state machine tests | 1 |
| `tests/core/runtime/test_runtime_context.py` | Context creation and access tests | 2 |
| `tests/core/runtime/test_runtime.py` | Runtime init/shutdown tests | 3 |
| `tests/core/runtime/test_managed_session.py` | ManagedSession adapter tests | 5 |
| `tests/core/runtime/test_managed_worker.py` | ManagedWorker adapter tests | 6 |
| `docs/adrs/0009-runtime-lifecycle-model.md` | Lifecycle design decision | 10 |
| `docs/adrs/0010-runtime-dependency-injection.md` | DI container design decision | 10 |
| `docs/adrs/0011-phase-1-adapter-strategy.md` | Adapter pattern decision | 10 |

**Total new files: ~20**

---

## Files to Modify

| File | Changes | Risk | Priority |
|------|---------|------|----------|
| `src/nexusagent/core/agent.py` | Add RuntimeContext shims for `_current_session`, `_ws_memory_dir`, `_tools_registered`; Agent accepts optional RuntimeContext | HIGH | P1 |
| `src/nexusagent/core/session/session.py` | Set `context.current_session_id` instead of (or in addition to) `_current_session.set()` | MEDIUM | P1 |
| `src/nexusagent/tools/register_all.py` | Read context fields instead of ContextVars | LOW | P1 |
| `src/nexusagent/server/server.py` | lifespan creates Runtime → delegate init/shutdown | MEDIUM | P2 |
| `src/nexusagent/interfaces/cli.py` | Optional Runtime for `nexus run` path | LOW | P3 |

**Total modified: ~5 files**

---

## Files to Leave Alone

| File | Reason |
|------|--------|
| `core/session/session_base.py` | Works — wrapped by ManagedSession indirectly |
| `core/worker/handler.py` | Works — `_run_agent_task()` stays |
| `core/worker/worker.py` | Works — adapted by ManagedWorker |
| `core/worker/pool.py` | Works — adapted by WorkerManager |
| `core/graph.py` | Not touched until Phase 4 |
| `core/subagent.py` | Works — adapted by ManagedWorker |
| `core/orchestration.py` | Not touched until Phase 5 |
| `core/trust.py` | Works — Phase 8 target |
| `infrastructure/bus.py` | Works — adapted via RuntimeContext |
| `infrastructure/config.py` | Works — Runtime uses it |
| `infrastructure/db/` | Works — adapted via RuntimeContext |
| `infrastructure/auth.py` | Works — not in Phase 1 scope |
| `llm/` | Not touched |
| `memory/` | Not touched (Phase 9) |
| `tools/*.py` (individual tools) | Not touched |
| `tools/registry/` | Works — adapted via RuntimeContext |
| `tools/tool_specs.py` | Not touched |
| `widgets/` | TUI — not touched |
| `interfaces/tui/` | Not touched (uses server) |
| `interfaces/web_ui.py` | Not touched |
| `server/routes.py` | Works — connects through Server lifespan |
| `server/sdk.py` | Not touched |
| `server/websocket.py` | Works — uses SessionManager (which will be Runtime-owned) |
| `hooks/__init__.py` | Works — adapted via RuntimeContext |

**Total untouched: ~90% of codebase**

---

## Test Strategy

### Principles

1. **New code has tests** — Every new file in `runtime/` must have corresponding tests
2. **Existing tests must pass** — No regression allowed
3. **Test backward compat** — Old code paths (direct singletons) still work
4. **Test in isolation** — Runtime tests don't need NATS, DB, or external services

### Test Coverage Targets

| Component | Tests | Type |
|-----------|-------|------|
| `LifecycleState` | Valid + invalid transitions | Unit |
| `LifecycleMixin` | ABC enforcement | Unit |
| `RuntimeContext` | Creation, field access, defaults | Unit |
| `Runtime` | init sequence, shutdown sequence | Integration (mocked) |
| `ToolManager` | ensure_registered flow | Integration (mocked) |
| `ManagedSession` | Lifecycle, wrap/unwrap Session | Integration |
| `ManagedWorker` | Lifecycle, wrap SubAgentHandle | Integration |
| `core.agent` shims | Both RuntimeContext and no-RuntimeContext paths | Unit |
| Server lifespan | Runtime integration | Integration |

### Existing Test Baseline

Before starting Phase 1, record the exact test counts:
```bash
cd ~/Workspaces/NexusAgent
python3 -m pytest tests/ --tb=short --no-header -q 2>&1 | tail -1
```

After each step, verify:
```bash
python3 -m pytest tests/core/runtime/ --tb=short -q          # new tests
python3 -m pytest tests/test_session.py --tb=short -q         # existing session
python3 -m pytest tests/test_agent_events.py --tb=short -q    # existing agent
```

---

## Rollback Strategy

### Per-Step Rollback

Each step in the execution plan is a **self-contained commit**. If a step breaks:

```bash
git revert <commit> --no-edit
```

### Full Phase 1 Rollback

```bash
# If the entire phase needs to be reversed:
git log --oneline | grep "phase-1:" | tail -1   # find first commit
git revert <first-commit>..HEAD --no-edit        # batch revert
```

### What preserves rollback safety

1. **Adapters, not rewrites** — The existing `Session`, `NexusWorker`, `WorkerPool`, and `SessionManager` classes remain intact. Only the Runtime layer is new.
2. **Shims, not deletion** — Global state is not deleted. Module-level bools and ContextVars gain shims that prefer RuntimeContext but fall back to old behavior.
3. **`git revert` is safe** — Because adapters wrap rather than replace, reverting a Runtime commit leaves the old code path working.

---

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Circular imports from runtime/ packages | Medium | High | Import RuntimeContext lazily in agent.py; runtime/ imports existing code directly (not vice versa) |
| R2 | ContextVar shims miss a code path | Medium | Medium | Search all `_current_session.get()`/`.set()` references; add tests for each consumer |
| R3 | Server lifespan change crashes startup | Low | Critical | Test with mock first; maintain legacy lifespan path as fallback |
| R4 | Test env doesn't create Runtime — old path still used | Low | Medium | Add fallback in shims: if no RuntimeContext, use old module-level state |
| R5 | Workers start using Runtime before adapters complete | Low | Medium | Keep old singleton path active until adapter is committed |
| R6 | RAM pressure (340MB free) slows test suite | Medium | Low | Run targeted tests per step, not full suite; skip TUI and NATS tests |
| R7 | `asyncio.create_task()` breaks ContextVar bridge | Medium | Low | Document that ContextVar → RuntimeContext bridge may not survive create_task(); use shim fallback |

---

## Verification Gates

### Gate 1 — Before Implementation (Current State Confirmed)

- [ ] `git log --oneline -5` shows `18a4c31` (`docs: update session state...`) as HEAD
- [ ] `python3 -m pytest tests/test_session.py tests/test_session_manager.py -q --tb=short` passes
- [ ] `python3 -m pytest tests/test_trust.py tests/test_agent_events.py -q --tb=short` passes
- [ ] Server can be imported: `python3 -c "import nexusagent; print('OK')"`

### Gate 2 — After Step 3 (Runtime kernel exists)

- [ ] `Runtime()` can be created and initialized (test environment)
- [ ] Lifecycle states transition correctly
- [ ] RuntimeContext fields are accessible
- [ ] All existing tests still pass

### Gate 3 — After Step 7 (Global state migrated)

- [ ] Agent creates with RuntimeContext — sets `context.current_session_id`
- [ ] Tools read `context.current_session_id` instead of ContextVar
- [ ] `_ensure_tools_registered()` works both with and without RuntimeContext
- [ ] All existing tests still pass

### Gate 4 — After Step 8 (Server uses Runtime)

- [ ] Server starts: `python3 -m nexusagent.server` (dry run with timeout)
- [ ] Server stops cleanly (no hung tasks, no exception in shutdown)
- [ ] WebSocket session creates and sends messages (test_server.py)
- [ ] All existing tests still pass

### Gate 5 — Phase 1 Complete

- [ ] `Runtime.initialize()` → `Runtime.shutdown()` sequence works end-to-end
- [ ] 3+ new ADRs created for design decisions
- [ ] ~20 new files with test coverage
- [ ] 5 modified files with backward-compatible changes
- [ ] Pre-migration test baseline matches post-migration (no regressions)
- [ ] `docs/architecture/current-state.md` updated with Phase 1 results

---

**Document version:** 1.0  
**Total estimated new code:** ~1,500 lines  
**Total estimated modified code:** ~200 lines  
**Estimated test count added:** 80-120 new tests  
**Dependency change:** zero (no new packages)  
**Migration pattern:** 100% adapter-based — nothing deleted
