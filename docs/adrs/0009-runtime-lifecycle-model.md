# ADR 0009 — Runtime Lifecycle Model

> **Decision:** 2026-07-19  
> **Status:** Accepted  
> **Decider:** Lucien  
> **Applies to:** Phase 1 — Runtime Foundation

---

## Context

NexusAgent components (sessions, workers, agents) currently have no explicit lifecycle. A component either "exists" (constructed and running) or "doesn't exist." This makes it impossible to:
- Query whether a component is healthy
- Perform ordered shutdown
- Detect and recover from failures
- Track component state for monitoring and debugging

Phase 1 introduces a Runtime kernel that needs a lifecycle model for all managed components.

## Decision

Adopt a **7-state lifecycle machine** for all runtime components:

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

### State Descriptions

| State | Meaning | Valid Transitions |
|-------|---------|-------------------|
| `CREATED` | Component constructed but not started | → INITIALIZING |
| `INITIALIZING` | Setup in progress (async) | → RUNNING, → FAILED |
| `RUNNING` | Component is operational | → PAUSED, → FAILED, → TERMINATING |
| `PAUSED` | Temporarily suspended | → RUNNING, → FAILED |
| `FAILED` | Unrecoverable error | → TERMINATING |
| `COMPLETED` | Normal completion (workers) | → TERMINATING |
| `TERMINATED` | Resources released | (terminal) |

### Implementation

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

## Alternatives Considered

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| **3-state** (start/stop/error) | Simple, low overhead | No PAUSED or recovery states; cannot distinguish "completed" from "failed" | Rejected — too coarse for worker lifecycle |
| **5-state** (add FAILED + COMPLETED) | Covers common cases | No PAUSED for temporary suspension; no INITIALIZING for async setup | Rejected — no async init safety |
| **Agent-specific lifecycle** (from deepagents) | Reuse existing model | Tied to deepagents internals; inconsistent across components | Rejected — must be universal |
| **Protocol-based** (no ABC) | Lighter coupling | No compile-time enforcement of lifecycle contract | Rejected — ABC provides safer interface |

## Tradeoffs

- **+** Explicit state prevents invalid operations (e.g., calling `send()` on a `FAILED` session)
- **+** Ordered shutdown prevents resource leaks
- **+** Health monitoring becomes trivially queryable
- **−** 7 states may be over-engineered for simple components (tools, simple utilities)
- **−** Requires disciplined state transitions from implementors

## Future Impact

This lifecycle model will be used by every future phase:
- **Phase 2:** Task state machine (12+ states, superset of this model)
- **Phase 4:** LangGraph Worker runtime extends `LifecycleMixin`
- **Phase 7:** POL uses lifecycle state for intervention decisions
- **Phase 10:** Monitoring reads lifecycle state for dashboards

The 7-state model is designed to be the **base** for task states, which will have additional sub-states on top.
