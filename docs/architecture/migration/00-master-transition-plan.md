# NexusAgent Architectural Transition Plan

## Mission

Transform NexusAgent from an agent framework into a distributed autonomous agent runtime.

The target system must support:

- interactive WebSocket coding sessions
- durable long-horizon workers
- DAG-based task execution
- centralized orchestration
- policy enforcement
- autonomous recovery
- persistent organizational memory

## Current State

NexusAgent currently provides:

- LLM provider abstraction
- tools framework
- MCP support
- WebSocket sessions
- research-style agents
- LangGraph-compatible execution
- memory infrastructure
- **🆕 Runtime kernel (Phase 1 ✅)** — 7-state lifecycle, DI container, server integration

## Target Architecture

```
                    NexusAgent Runtime
                           |
                         POL
                           |
                    Event Backbone
                           |
       +------------------+------------------+
       |                                     |
 Interactive Sessions              Autonomous Workers
       |                                     |
 WebSocket Agents                    LangGraph Agents
       |                                     |
       +------------------+------------------+
                          |
                    Memory System
```

## Migration Principles

1. **Preserve** existing functionality.
2. **Introduce abstractions** before implementations.
3. **Avoid large rewrites** — prefer evolution over replacement.
4. **Maintain backward compatibility** at every step.
5. **Make state explicit** — no hidden globals.
6. **Make events first-class** — events as the nervous system.

## Phase Overview

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Runtime foundation | ✅ Delivered (2026-07-19) |
| 2 | Durable task execution | ⬜ Specified, not implemented |
| 3 | Event-driven architecture | ⬜ Specified, not implemented |
| 4 | LangGraph worker runtime | ⬜ Specified, not implemented |
| 5 | Planner & orchestrator | ⬜ Specified, not implemented |
| 6 | DAG execution engine | ⬜ Specified, not implemented |
| 7 | POL control plane | ⬜ Specified, not implemented |
| 8 | Capability security model | ⬜ Specified, not implemented |
| 9 | Memory evolution (4-layer) | ⬜ Specified, not implemented |
| 10 | Observability & reliability | ⬜ Specified, not implemented |
| 11 | Production readiness | ⬜ Specified, not implemented |

## Next Phase: Phase 2 — Durable Task Execution

**Dependency:** Phase 1 runtime foundation is the gating dependency. It's done.

**Gap:** Every task and worker in the system currently operates ephemerally — no checkpointing, no recovery, no durability. The system is built for interactive use, not autonomous long-horizon operation.

**What Phase 2 delivers:**
- Task entity with defined lifecycle (CREATED → PLANNING → EXECUTING → VERIFYING → COMPLETED)
- State transition validator (enforcing valid transitions)
- Persistent task state in SQLite
- Checkpoint mechanism capturing execution state
- Recovery path (FAILED → RECOVERING)
- Worker that can be interrupted and restarted from last checkpoint

**Success criteria from the directive:** "A task can survive interruption and resume from persisted state."

**Implementation strategy:** Phase 2 is a good candidate for a consolidated Jules PR — it's well-scoped, has clear completion criteria, and benefits from sustained reasoning (checkpoint serialization, state machine design). Estimated: 1 PR, 5-8 source files.