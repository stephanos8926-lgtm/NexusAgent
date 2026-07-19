# Phase 1 — Runtime Foundation

## Objective

Separate NexusAgent execution from individual agent implementations.

## Goals

Create:

- **Runtime kernel** — the core execution environment
- **Session manager** — lifecycle for interactive sessions
- **Worker manager** — lifecycle for autonomous workers
- **Lifecycle interfaces** — standard state transitions for all runnable components

## Current Problem

Agent behavior currently owns too much responsibility. The `Agent` class and `Session` runtime are tightly coupled, with hidden global state (`_REGISTRY`, `_ROLE_TOOLS`, module-level locks) and no clear separation between the orchestration layer and the execution layer.

## Target Architecture

```
Runtime
    |
    +-- Session Manager
    +-- Worker Manager
    +-- Tool Manager
    +-- Memory Manager
    +-- Policy Manager
```

## Implementation Steps

### Step 1 — Create `runtime` package

```
src/nexusagent/runtime/
    __init__.py
    runtime.py     — Runtime kernel
    session.py     — Session lifecycle
    worker.py      — Worker lifecycle
    lifecycle.py   — State machine interfaces
    context.py     — RuntimeContext (dependency injection)
```

### Step 2 — Introduce lifecycle states

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

### Step 3 — Remove hidden global state

| Current (global) | Target (RuntimeContext) |
|------------------|------------------------|
| `_REGISTRY` | `context.tools.registry` |
| `_ROLE_TOOLS` | `context.tools.roles` |
| `_tools_registered` | `context.tools.initialized` |
| `_ws_memory_dir` | `context.memory.workspace` |
| `_current_session` | `context.session.current` |
| Module-level locks | `context.*.lock` |

### Step 4 — Create dependency injection boundaries

The `Runtime` receives its dependencies explicitly:

```python
class Runtime:
    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolRegistry,
        memory: MemoryManager,
        policy: PolicyEngine,
        event_bus: EventBus,
    ):
        ...
```

Not through global imports or module-level singletons.

## Completion Criteria

- [ ] Agents execute through the `Runtime` kernel, not directly
- [ ] Lifecycle state is observable for every component
- [ ] Sessions are fully isolated from each other
- [ ] Workers have unique identity and traceable lifecycle