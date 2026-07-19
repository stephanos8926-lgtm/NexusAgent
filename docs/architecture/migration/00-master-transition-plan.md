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
| 1 | Runtime foundation | ⬜ Specified |
| 2 | Durable task execution | ⬜ Not yet specified |
| 3 | Event-driven architecture | ⬜ Specified |
| 4 | Planner and orchestrator | ⬜ Not yet specified |
| 5 | POL control plane | ⬜ Not yet specified |
| 6 | Security and governance | ⬜ Not yet specified |
| 7 | Production hardening | ⬜ Not yet specified |