# Target State — NexusAgent Runtime Architecture

> **Date:** 2026-07-19  
> **Scope:** Phase 1 target — the runtime kernel  
> **Purpose:** Define the execution foundation for all future phases  
> **Based on:** `docs/architecture/migration/CHIEF-ARCHITECT-DIRECTIVE.md` and Phase 0 documents

---

## Architectural Vision

The target is not a single agent. The target is an **agent runtime environment** where multiple specialized agents operate inside controlled execution boundaries.

```
┌─────────────────────────────────────────────────────────┐
│                    NexusAgent Runtime                      │
│                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Session     │  │ Worker      │  │ Tool             │  │
│  │ Manager     │  │ Manager     │  │ Manager          │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬─────────┘  │
│         │                │                  │            │
│  ┌──────┴────────────────┴──────────────────┴─────────┐  │
│  │              RuntimeContext                          │  │
│  │              (Dependency Injection Container)        │  │
│  └──────────────────────┬──────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────┴──────────────────────────────┐  │
│  │              Lifecycle Manager                        │  │
│  │         (State transitions for all components)       │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              Event Backbone (NATS)                    │  │
│  │   (typed events: task.*, session.*, worker.*, ...)   │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 1 Target — Runtime Kernel

Phase 1 establishes the **operating system kernel** for NexusAgent. It does not build applications or intelligence — it creates the boundaries within which future intelligence operates.

### What the Runtime Owns

| Responsibility | Rationale |
|---------------|-----------|
| **Lifecycle management** | Every component has explicit CREATED → RUNNING → TERMINATED states |
| **Coordination** | Runtime coordinates sessions, workers, and tools |
| **Dependency injection** | Dependencies are passed explicitly, not imported globally |
| **Execution boundaries** | Sessions are isolated from each other; workers are isolated from sessions |
| **Context propagation** | `RuntimeContext` carries identity, config, and state — not ContextVars |
| **Event routing** | System events flow through the Runtime, not through ad-hoc singletons |

### What the Runtime Does NOT Own

| Non-Responsibility | Where It Belongs |
|-------------------|-----------------|
| **Planning** | Future Phase 5 — Planner |
| **Policy decisions** | Future Phase 7 — POL |
| **Autonomous reasoning** | Future Phase 4 — Workers |
| **DAG execution** | Future Phase 6 — DAG Engine |
| **Complex memory** | Future Phase 9 — Memory Evolution |
| **Business rules** | Future Phase 8 — Capability Model |

---

## Component Design

### 1. Runtime Kernel — `runtime/runtime.py`

```python
class Runtime:
    """Central execution kernel — owns lifecycle, coordination, and dependencies.
    
    The Runtime is the root of the component hierarchy. It is created at
    application startup and destroyed at shutdown. All system components
    are children of the Runtime.
    """

    def __init__(self, config: ConfigSchema):
        self.config = config
        self.state = LifecycleState.CREATED
        self.context: RuntimeContext | None = None
        self.session_manager: SessionManager | None = None
        self.worker_manager: WorkerManager | None = None
        self.tool_manager: ToolManager | None = None
        self.event_bus: Bus | None = None

    async def initialize(self) -> None:
        """Startup sequence: init DB → connect bus → init managers."""
        self.state = LifecycleState.INITIALIZING
        self.context = RuntimeContext(self.config)
        ...
        self.state = LifecycleState.RUNNING

    async def shutdown(self) -> None:
        """Graceful shutdown sequence."""
        self.state = LifecycleState.TERMINATING
        ...
        self.state = LifecycleState.TERMINATED
```

### 2. Lifecycle States — `runtime/lifecycle.py`

Every runtime component follows the same state machine:

```
CREATED
    ↓
INITIALIZING
    ↓
RUNNING
    ↓
  ┌───┴───┐
  │       │
PAUSED   FAILED
  │       │
  └───┬───┘
      ↓
  COMPLETED
      ↓
  TERMINATED
```

```python
class LifecycleState(StrEnum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"
    TERMINATED = "terminated"

class LifecycleMixin(ABC):
    """Abstract base for all components with observable lifecycle."""

    @property
    @abstractmethod
    def state(self) -> LifecycleState: ...

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def shutdown(self) -> None: ...

    @abstractmethod
    def health(self) -> dict[str, Any]: ...
```

### 3. RuntimeContext — `runtime/context.py`

The dependency injection container. Every component gets its dependencies through this object — not through global imports.

```python
@dataclass
class RuntimeContext:
    """Explicit dependency injection container.
    
    Replaces module-level singletons and ContextVars.
    Passed to every component at initialization time.
    """

    config: ConfigSchema
    
    # Tool system
    tool_registry: ToolRegistry
    tool_roles: dict[str, list[str]]
    tool_initialized: bool
    
    # Session identity
    current_session_id: str | None
    
    # Memory paths
    workspace_memory_dir: Path | None
    
    # Sub-systems (will evolve in future phases)
    bus: AgentBus | None = None
    db_manager: DBManager | None = None
    hook_manager: HookManager | None = None
```

### 4. Session Manager — `runtime/session.py`

```python
class ManagedSession(LifecycleMixin):
    """Runtime-aware session with explicit lifecycle.
    
    Wraps the existing Session class via adapter pattern.
    """

    session_id: str
    state: LifecycleState
    session: Session      # Existing Session class (adapter target)
    metadata: SessionMetadata
    created_at: datetime
    last_active: datetime

    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def health(self) -> dict: ...
```

The SessionManager under Runtime has the same interface but is **owned** by Runtime, not by a module-level singleton:

```python
class SessionManager(LifecycleMixin):
    """Owned by Runtime — manages session lifecycle."""

    def __init__(self, context: RuntimeContext):
        self.context = context
        self._sessions: dict[str, ManagedSession] = {}
        ...
```

### 5. Worker Manager — `runtime/worker.py`

```python
class ManagedWorker(LifecycleMixin):
    """Runtime-aware worker with explicit identity and lifecycle."""

    worker_id: str
    state: LifecycleState
    worker_type: WorkerType     # LOCAL | NATS | SUBAGENT
    metadata: WorkerMetadata
    started_at: datetime | None

    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def health(self) -> dict: ...
```

```python
class WorkerManager(LifecycleMixin):
    """Owned by Runtime — manages worker lifecycle."""

    def __init__(self, context: RuntimeContext):
        self.context = context
        self._workers: dict[str, ManagedWorker] = {}
        ...
```

### 6. Tool Manager — `runtime/tools.py`

```python
class ToolManager(LifecycleMixin):
    """Owned by Runtime — manages tool registration and access."""

    def __init__(self, context: RuntimeContext):
        self.context = context
        self.registry: ToolRegistry
        ...

    def ensure_registered(self) -> None:
        """Replace _ensure_tools_registered() global bool."""
        ...

    async def load_mcp_tools(self) -> None:
        """Replace module-level MCP discovery."""
        ...
```

---

## Migration Pattern — Adapter, Not Rewrite

The target uses **adapters** to wrap existing implementations, not rewrites:

```
Current System                    Migration Layer                  Target Runtime
─────────────────                 ───────────────                 ──────────────
Session (core/session)  ───────►  ManagedSession.adapter   ────►  SessionManager
                                                                  (runtime/ owned)

Agent (core/agent)      ───────►  (wrapped by Session)     ────►  (Phase 4+ owns this)

NexusWorker             ───────►  ManagedWorker.adapter    ────►  WorkerManager
                                                                  (runtime/ owned)

WorkerPool              ───────►  (migrate into             ────►  WorkerManager
                                 WorkerManager)

_tools_registered       ───────►  ToolManager               ────►  context.tools
_current_session                 .ensure_registered()              .initialized
_ws_memory_dir          ───────►  RuntimeContext              ────►  context.session
                                                                         .current_id
                                                                         .workspace_memory_dir

get_session_manager()   ───────►  Runtime.session_manager
get_bus()                        .get / .get_or_create
get_worker()
get_worker_pool()       ───────►  Runtime.worker_manager
                                 .get / .spawn

HookManager singleton   ───────►  Runtime.context.hook_manager
                                 (no global needed)
```

---

## Dependency Flow (Target)

```
Application Entry Point (server, CLI, TUI)
    │
    ├── Creates Runtime(config)
    │       │
    │       ├── Runtime.initialize()
    │       │       ├── Creates RuntimeContext
    │       │       ├── Creates ToolManager → ensures_registered
    │       │       ├── Creates SessionManager
    │       │       ├── Creates WorkerManager
    │       │       ├── Creates Bus connection
    │       │       └── Creates DB connection
    │       │
    │       ├── Runtime.session_manager.get_or_create()
    │       │       └── Session receives context (not global imports)
    │       │
    │       ├── Runtime.worker_manager.spawn()
    │       │       └── Worker receives context
    │       │
    │       └── Runtime.shutdown()
    │               └── Graceful shutdown all managers
    │
    └── (entry point uses Runtime as the single API)
```

---

## What Phase 1 Does NOT Change

The following remain **unchanged** during Phase 1 (wrapped through adapters):

| Component | Rationale |
|-----------|-----------|
| `Session.send()` | Core message loop — works, don't touch |
| `SessionBase` memory management | Works, adapt later |
| `Agent` class | Deep coupling — Phase 4 target |
| `run_agent_task()` | Entry point for workers — adapt later |
| Tool implementations | 25+ tools — stable |
| `ToolRegistry` | Already partially migrated — good foundation |
| `ConfigSchema` | Works — adapt initialization |
| `AgentBus` | Works — adapt into Runtime context |
| `HybridMemoryManager` | Works — Phase 9 target |
| `NexusApp` (TUI) | UI — adapt endpoint |
| CLI subcommands | Adapt to use Runtime where needed |
| Tests | Must continue passing — adapt test fixtures |

---

## Key Design Decisions (Pre-Migration ADRs)

These are recorded as **ADRs** but summarized here for architectural context:

| Decision | Choice | Alternatives Considered |
|----------|--------|------------------------|
| Lifecycle model | 7-state (CREATED→INITIALIZING→RUNNING→PAUSED/FAILED→COMPLETED→TERMINATED) | 3-state (start/stop), 5-state |
| DI container | `RuntimeContext` dataclass — explicit, typed, immutable after init | Pydantic Settings, dependency-inject framework |
| Adapter pattern | Wrapper around existing classes | Facade, Proxy |
| Session isolation | Per-session RuntimeContext shallow copy | Full clone, shared |
| Singleton migration | Move singletons INTO Runtime, one at a time | Big-bang replacement |
| Lifecycle inheritance | `LifecycleMixin` ABC | Protocol, Trait mixin |

---

## Completion Criteria (Phase 1) — ✅ ALL COMPLETE

- [x] Agents execute through `Runtime` kernel abstractions (not directly via `run_agent_task()` free function)
- [x] Lifecycle state is observable for every runtime component
- [x] Sessions have identity (not just ContextVar)
- [x] Workers have identity (not just process-less singleton)
- [x] Execution context is explicit (`RuntimeContext` passed to components)
- [x] Global state migration plan executed for top-5 singletons:
  - [x] `_current_session` → `RuntimeContext.current_session_id`
  - [x] `_ws_memory_dir` → `RuntimeContext.workspace_memory_dir`
  - [x] `_tools_registered` → `ToolManager.ensure_registered()`
  - [x] `_session_manager_instance` → `Runtime.session_manager`
  - [x] `_manager` (HookManager) → `Runtime.context.hook_manager`
- [x] Existing tests pass (104 core runtime + 680 baseline: 684+ total)
- [x] ADRs created for all significant decisions (0009, 0010, 0011)
- [x] `docs/architecture/target-state.md` kept in sync with implementation
- [x] CLI adapter wired (`__main__.py` uses `create_server_app()`)
- [x] Integration tests for Runtime subsystems (20 new tests)
- [x] Server lifespan integrated (Runtime-backed create_server_app)
- [x] Plugin dispatchers fixed for worktree-worker (13 handlers)

**Commit:** `889efd2` (foundation) + `b2ce23e` (CLI adapter + integration tests) + `c3b32ef` (Jules PR merge) + `17c1f23` (fixes)  
**Pushed:** master — `17c1f23`  
**Test status:** 104/104 runtime tests passing

---

## Future Phase Roadmap (Post-Phase 1)

| Phase | Title | Depends On |
|-------|-------|------------|
| 2 | Durable Task State Machine | Phase 1 |
| 3 | Event-Driven Core (typed event schema) | Phase 1 |
| 4 | LangGraph Worker Runtime | Phase 1, 2, 3 |
| 5 | Planner & Orchestrator | Phase 4 |
| 6 | DAG Execution Engine | Phase 5 |
| 7 | POL Control Plane | Phase 6 |
| 8 | Capability Security Model | Phase 7 |
| 9 | Memory Evolution (4-layer) | Phase 8 |
| 10 | Observability & Reliability | Phase 9 |
| 11 | Production Readiness | Phase 10 |

---

**Document version:** 1.0  
**Target phase:** Phase 1 — Runtime Foundation
