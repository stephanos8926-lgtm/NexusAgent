# Synthesis — SPEC-007 Runtime Foundation

> **Date:** 2026-07-19  
> **Mode:** MEDIUM  
> **Prepared from:**  
>   - `docs/specs/SPEC-007-runtime-foundation-v1.md`  
>   - `docs/audits/forward-audit-spec-007.md`  
>   - `docs/audits/reverse-audit-spec-007.md`  
>   - `docs/adrs/0009-0011`

---

## Audit Results Summary

| Audit | Finding |
|-------|---------|
| **Forward** | All 15 ACs feasible. 4 spec corrections: add 2 more ContextVars to G7 (7 total, not 5). |
| **Reverse** | 7 gaps found. 0 blockers. 1 fixed (additional ContextVars), 4 documented/mitigated, 1 deferred, 1 observed. |

### Key Corrections from Audits

1. **G7 scope expanded**: 5 → **7 globals** — added `_workspace_root_var` (fs_base.py) and `_policy_context` (policy.py)
2. **RuntimeContext gains 2 more fields**: `workspace_root: Path | None`, `policy_context: dict | None`
3. **Policy context is session-scoped** — ManagedSession owns `policy_context` lifecycle, not Runtime
4. **Shutdown must error-isolate** each step (one failure shouldn't cascade)
5. **`test_singletons.py`** needs awareness of RuntimeContext for the getter redirect

---

## Final Implementation Plan

### Step 0 — Package Skeleton
**Files:** `runtime/__init__.py`  
**Tests:** none needed

### Step 1 — Lifecycle Abstraction
**Files:** `runtime/lifecycle.py`  
**Tests:** `test_lifecycle.py`  
**Key classes:** `LifecycleState`, `LifecycleMixin`, `HealthStatus`

### Step 2 — DI Container
**Files:** `runtime/context.py`  
**Tests:** `test_runtime_context.py`  
**Key classes:** `RuntimeContext` (7 global fields + config + bus + db + hooks)

### Step 3 — Runtime Kernel
**Files:** `runtime/runtime.py`  
**Tests:** `test_runtime.py`  
**Key classes:** `Runtime` with `initialize()` (3 steps) and `shutdown()` (3 steps, error-isolated)

### Step 4 — ToolManager
**Files:** `runtime/tools.py`  
**Tests:** `test_tool_manager.py`  
**Wraps:** `_ensure_tools_registered()`, `register_all()`, `register_mcp_tools()`

### Step 5 — Session Adapter
**Files:** `runtime/session.py`  
**Tests:** `test_managed_session.py`  
**Classes:** `SessionMetadata`, `ManagedSession`, `RuntimeSessionManager`  
**Wraps:** `Session`, `SessionManager`

### Step 6 — Worker Adapter
**Files:** `runtime/worker.py`  
**Tests:** `test_managed_worker.py`  
**Classes:** `WorkerMetadata`, `ManagedWorker`, `RuntimeWorkerManager`  
**Wraps:** `SubAgentHandle`, `WorkerPool`

### Step 7 — Migrate 7 Global Singletons
**Files modified:**
- `core/agent.py` — 3 shims (`_current_session`, `_ws_memory_dir`, `_tools_registered`)
- `core/session/session.py` — set `context.current_session_id` alongside ContextVar
- `tools/register_all.py` — read `context.*` fields alongside ContextVars
- `tools/fs_base.py` — `_workspace_root_var` shim
- `tools/registry/policy.py` — `_policy_context` shim

**Tests:** `test_global_migration.py`

### Step 8 — Server Adapter
**Files modified:** `server/server.py`  
**Change:** lifespan creates `Runtime` → delegates init/shutdown

### Step 9 — CLI Adapter (optional)
**Files modified:** `interfaces/cli.py`  
**Change:** `nexus run` uses Runtime for local tasks

### Step 10 — ADRs Already Written
ADRs 0009, 0010, 0011 committed

---

## Test Plan

| Step | New Tests | Verify Existing |
|------|-----------|-----------------|
| 1 | `test_lifecycle.py` — state transitions, ABC enforcement | — |
| 2 | `test_runtime_context.py` — creation, field access | — |
| 3 | `test_runtime.py` — init/shutdown, lifecycle transitions | — |
| 4 | `test_tool_manager.py` — registration, dual-path | `test_mcp_loading.py` |
| 5 | `test_managed_session.py` — wrap, delegate, lifecycle | `test_session.py` |
| 6 | `test_managed_worker.py` — wrap, delegate, lifecycle | `test_worker_pool.py` |
| 7 | `test_global_migration.py` — shim fallback | `test_singletons.py`, `test_agent_events.py` |
| 8 | — | `test_server.py`, `test_websocket.py` |
| 9 | — | `test_cli_run.py` |

---

## Risk Register (Final)

| Risk | Mitigation | Trigger | Owner |
|------|-----------|---------|-------|
| Circular import between runtime/ and existing | runtime/ never reverse-imports (local imports only) | ImportError test | Design |
| ContextVar shims miss code path | Exhaustive grep of all 7 ContextVar refs before/after | Test failure | Test |
| Server lifespan change breaks startup | Backup: keep old lifespan code path | Gate 4 failure | Server |
| Test env no Runtime → old path used | Dual-path shim guarantees fallback | `test_global_migration.py` | Design |
| Asyncio create_task loses ContextVar | RuntimeContext stored as attribute on component | Cross-task access works | Architecture |
| Full test suite OOM on 4GB RAM | Targeted test per step | 389MB free | Operations |

---

## Acceptance Criteria (Updated) — ✅ ALL COMPLETE

- [x] AC1: `RuntimeContext` creation (7 fields + config)
- [x] AC2: `LifecycleState` invalid transition rejection
- [x] AC3: `LifecycleMixin` ABC enforcement
- [x] AC4: `Runtime.initialize()`: CREATED → INITIALIZING → RUNNING
- [x] AC5: `Runtime.shutdown()`: RUNNING → TERMINATING → TERMINATED (error-isolated)
- [x] AC6: `ToolManager.ensure_registered()` dual-path (Runtime + legacy)
- [x] AC7: `ManagedSession` wraps Session + lifecycle
- [x] AC8: `ManagedWorker` wraps SubAgentHandle + lifecycle
- [x] AC9: **7** global shims + backward-compat fallback
- [x] AC10: Server starts/stops via Runtime (create_server_app + lifespan)
- [x] AC11: Pre-migration test baseline matches post-migration
- [x] AC12: 3 ADRs committed (0009, 0010, 0011)
- [x] AC13: Clean server shutdown
- [x] AC14: `current_context()` returns None safely
- [x] AC15: `Session.send()` works with/without RuntimeContext
- [x] AC16: CLI adapter wires `create_server_app()` into `__main__.py`
- [x] AC17: Integration tests for all Runtime subsystems (104 tests)
- [x] AC18: Jules PR #7 merged — server lifespan + wire-up
- [x] AC19: Worktree plugin dispatch handlers fixed (`**kwargs`)
- [x] AC20: Mistral Vibe CLI wired for cloud task dispatch

---

## Files Summary

| Action | Count | Detail |
|--------|-------|--------|
| **Create** | ~20 | `runtime/` package, tests, ADRs |
| **Modify** | 7 | agent.py, session.py, register_all.py, fs_base.py, policy.py, server.py, cli.py |
| **Leave alone** | ~103 | 90% of codebase untouched |
| **Est. new code** | ~1,600 lines | (1500 + 100 for additional ContextVars) |
| **Est. modified** | ~250 lines | (200 + 50 for additional shims) |
| **New tests** | 80-120 | 6 test files |

---

## Ready for sign-off.

**SPEC-007 passes both audits.** 2 corrections applied (additional ContextVars). 15 acceptance criteria defined. 10-step execution plan with per-step rollback. Zero new dependencies.

**Give the word and I start with Step 0.**
