# ADR 0011 — Phase 1 Adapter Strategy

> **Decision:** 2026-07-19  
> **Status:** Accepted  
> **Decider:** Lucien  
> **Applies to:** Phase 1 — Runtime Foundation

---

## Context

Phase 1 introduces a Runtime kernel that sits "underneath" the existing NexusAgent system. The existing system is working (680+ tests passing). The migration must not break it.

The challenge: how to introduce Runtime abstractions without rewriting or deleting the existing implementations?

## Decision

Use the **Adapter pattern** throughout Phase 1. Existing classes are wrapped by new Runtime-aware classes that implement `LifecycleMixin` and delegate to the original.

### What Gets Adapters

| Existing Class | Adapter | Delegation |
|---------------|---------|------------|
| `core/session/session.py:Session` | `runtime/session.py:ManagedSession` | `ManagedSession.session.send()`, `ManagedSession.session.close()` |
| `core/session/manager.py:SessionManager` | `runtime/session.py:RuntimeSessionManager` | Wraps `SessionManager`; Runtime owns the instance |
| `core/worker/pool.py:WorkerPool` | `runtime/worker.py:RuntimeWorkerManager` | Wraps `WorkerPool`; Runtime owns the instance |
| `core/subagent.py:SubAgentHandle` | `runtime/worker.py:ManagedWorker` | Wraps `SubAgentHandle`; tracks lifecycle |
| `core/agent.py:Agent` | (wrapped by Session — not directly adapted in Phase 1) | Phase 4 target |

### What Gets Shimmed (Not Adapted)

Some globals are too deeply embedded to wrap cleanly. These get **backward-compatible shims**:

| Global | Shim | Behavior |
|--------|------|----------|
| `_current_session` (ContextVar) | `context.current_session_id` | If RuntimeContext active, read/write from context. Otherwise use old ContextVar. |
| `_ws_memory_dir` (ContextVar) | `context.workspace_memory_dir` | Same dual-path pattern |
| `_tools_registered` (module bool) | `context.tool_initialized` | ToolManager checks context; fallback to module bool |
| `get_session_manager()` | `Runtime.session_manager` | If Runtime active, return its manager. Otherwise lazy-init the singleton. |

### Adapter Pattern Template

```python
class ManagedSession(LifecycleMixin):
    """Runtime-aware Session wrapper."""

    def __init__(self, session_id: str, session: Session, context: RuntimeContext):
        self._state = LifecycleState.CREATED
        self.session_id = session_id
        self._session = session      # <<< wrapped instance
        self._context = context
        self.metadata = SessionMetadata(
            id=session_id,
            created_at=datetime.now(UTC),
        )

    @property
    def state(self) -> LifecycleState:
        return self._state

    async def initialize(self) -> None:
        self._state = LifecycleState.INITIALIZING
        # Session is already initialized by SessionManager — we track it
        self._state = LifecycleState.RUNNING

    async def shutdown(self) -> None:
        self._state = LifecycleState.TERMINATING
        await self._session.close()
        self._state = LifecycleState.TERMINATED

    def health(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self._state.value,
            "alive": self._state == LifecycleState.RUNNING,
        }

    # Delegation methods
    async def send(self, *args, **kwargs):
        return await self._session.send(*args, **kwargs)

    async def event_stream(self):
        return self._session.event_stream()
```

## Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **Adapter (chosen)** | Zero risk to existing code; per-commit rollback; clear boundary | Some delegation boilerplate; two names for same thing | ✅ Best for Phase 1 |
| **Rewrite existing classes** | Clean code; no adapters to maintain | High risk; breaks everything; long period of broken tests | Rejected — violates migration principle #1 |
| **Facade pattern** | Single unified interface | Hides complexity rather than managing it; doesn't solve lifecycle tracking | Rejected — lifecycle is the point |
| **Multi-version classes** (v1/v2) | Clear migration path | Naming nightmare; import confusion | Rejected — adapters are the standard approach |
| **Do nothing** | Safe | No progress on architecture | Rejected — defeats purpose of Phase 1 |

## Tradeoffs

- **+** Zero regression risk — existing code paths unchanged
- **+** Per-commit rollback — revert any step without breaking the system
- **+** Clear migration boundary — adapter is the bridge between "old" and "new"
- **+** Testable in isolation — test ManagedSession without Session internals
- **−** Two classes for one concept (Session + ManagedSession)
- **−** Delegation boilerplate (send(), close(), event_stream() pass-throughs)
- **−** Adapters must be kept in sync with the underlying class interface

## Phase-Out Strategy

Adapters are NOT permanent. As subsequent phases modify the wrapped classes:
- **Phase 2 (Task State Machine):** `Session` gains task identity — `ManagedSession` adds task tracking
- **Phase 4 (LangGraph Workers):** `ManagedWorker` becomes the primary worker interface; old `WorkerPool` is replaced
- **Phase 9 (Memory Evolution):** Session → Runtime adapter may be simplified

Each future phase should remove the adapter and update the underlying class to implement `LifecycleMixin` directly. The adapter strategy is a **temporary bridge**, not the final architecture.

### Deletion Criteria

An adapter can be removed when:
1. The underlying class implements `LifecycleMixin` directly
2. All consumers use the Runtime-managed instance (not module-level getters)
3. The class is only instantiated through Runtime managers

## Migration Order (Gap G6-G7)

```
Step 5: ManagedSession wraps Session
         RuntimeSessionManager wraps SessionManager
         └── Session stays as-is
         └── SessionManager stays as-is
         └── RuntimeSessionManager adds lifecycle

Step 6: ManagedWorker wraps SubAgentHandle
         RuntimeWorkerManager wraps WorkerPool
         └── WorkerPool stays as-is
         └── RuntimeWorkerManager adds identity + lifecycle

Step 7: Global state shims
         └── Module bools get RuntimeContext fallback
         └── ContextVars get RuntimeContext fallback
         └── Agent.__init__ accepts optional RuntimeContext
```
