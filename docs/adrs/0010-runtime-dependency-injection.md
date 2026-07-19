# ADR 0010 — Runtime Dependency Injection

> **Decision:** 2026-07-19  
> **Status:** Accepted  
> **Decider:** Lucien  
> **Applies to:** Phase 1 — Runtime Foundation

---

## Context

NexusAgent currently uses 20+ module-level singletons for shared state (registry, config, bus, session manager, hook manager, etc.). These are accessed via direct `import` across the codebase:

```python
# Current pattern — everywhere
from nexusagent.core.session import session_manager
from nexusagent.infrastructure.config import settings
from nexusagent.hooks import get_hook_manager
from nexusagent.core.agent import _current_session
```

This creates:
- Implicit initialization order (import side effects)
- No clear ownership (who creates what?)
- No isolation (test contamination via module state)
- No traceability (where is this dependency set?)

Phase 1 needs a mechanism to provide dependencies explicitly.

## Decision

Use a **`RuntimeContext` dataclass** as the dependency injection container. Components receive their dependencies through this object rather than importing them globally.

### Design

```python
@dataclass
class RuntimeContext:
    """Explicit dependency injection container.
    
    All fields are set at initialization time and are read-only afterwards.
    Components created by the Runtime receive this context and access
    dependencies through it.
    """

    # System identity
    config: ConfigSchema
    
    # Tool system
    tool_registry: ToolRegistry | None = None
    tool_roles: dict[str, list[str]] | None = None
    tool_initialized: bool = False
    
    # Session identity  
    current_session_id: str | None = None
    workspace_memory_dir: Path | None = None
    
    # Sub-system references (set at Runtime init)
    bus: AgentBus | None = None
    db_manager: DBManager | None = None
    hook_manager: HookManager | None = None
```

### Access Pattern

```python
# Components owned by Runtime receive context
class SessionManager:
    def __init__(self, context: RuntimeContext):
        self._context = context
        self._context.tool_registry  # Access tools
        self._context.bus            # Access NATS

# Non-Runtime code uses backward-compat helper
from nexusagent.runtime.context import current_context
ctx = current_context()
if ctx is not None:
    session_id = ctx.current_session_id
else:
    session_id = _current_session.get()  # old path
```

### Thread Safety

`RuntimeContext` is a frozen dataclass after initialization — no setters, no mutation. Shared mutable state (session map, worker map) lives inside the manager classes owned by Runtime, which use the same locking patterns as current code.

## Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **dataclass (chosen)** | Simple, typed, zero-dependency, immutable, testable | No lifecycle hooks; no lazy resolution | ✅ Best fit for Phase 1 |
| **Pydantic BaseSettings** | Env override built-in, validation | Heavy for DI; designed for config, not DI container | Rejected — config already uses Pydantic |
| **`dependency-injector` package** | Full DI framework with lifecycle | New dependency; over-engineered for current needs; learning curve | Rejected — Phase 1 is zero new deps |
| **Manual constructor injection** | Pure Python, explicit | No container to pass between components; each component must thread deps | Rejected — RuntimeContext IS constructor injection plus a container |
| **Module-level getters (status quo)** | Familiar, works today | Implicit, untestable, no ownership | Rejected — this is what we're migrating from |

## Tradeoffs

- **+** Zero new dependencies
- **+** Fully typed (IDE support, mypy validation)
- **+** Backward compatible — old getters still work via `current_context()` fallback
- **+** Testable — create a mock `RuntimeContext` in test fixtures
- **−** Not a full DI framework (no auto-wiring, no scoped lifetimes)
- **−** Context must be threaded through or accessed via helper; no true inversion of control
- **−** Future phases may need a more sophisticated container (re-evaluate at Phase 4 or 7)

## Future Impact

- **Phase 4 (Workers):** Add `worker_manager` field to `RuntimeContext`
- **Phase 5 (Planner):** Add `planner` field
- **Phase 7 (POL):** Add `policy_engine` field
- **Phase 9 (Memory):** Add `memory_manager` field
- The dataclass grows with each phase — must be intentionally curated to avoid bloat

Each new dependency added to `RuntimeContext` requires an ADR justifying why it belongs at the runtime level vs. being a component-level dependency.
