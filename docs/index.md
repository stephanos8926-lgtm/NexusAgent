# NexusAgent

**Multi-agent orchestration framework with NATS messaging.**

NexusAgent is a lightweight, self-hosted agent platform that runs anywhere — from a Dell Optiplex to a Bobcat Miner. It features:

- **NATS-native**: Async messaging without Kafka's operational weight
- **Multi-interface**: CLI, TUI, Web UI, and API out of the box
- **Policy-aware tool system**: Progressive discovery with per-agent access control
- **Multi-agent parallelism**: Dynamic sub-agent spawning with memory slicing
- **Production-grade**: Circuit breakers, encrypted credentials, observability

## Quick Start

```bash
# Install
pip install -e .

# Run tests
make test

# Start dev server
make dev
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NexusAgent System                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   CLI    │  │   TUI    │  │  Web UI  │  │ REST API │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       └──────────────┴──────────────┴──────────────┘        │
│                          │                                  │
│                   ┌──────┴──────┐                           │
│                   │ Agent (Core)│                           │
│                   └──────┬──────┘                           │
│                          │                                  │
│       ┌──────────────────┼──────────────────┐              │
│       │                  │                  │              │
│  ┌────┴────┐      ┌─────┴─────┐     ┌─────┴─────┐        │
│  │  Tools  │      │   NATS    │     │    DB     │        │
│  │Registry │      │   Bus     │     │ (SQLite)  │        │
│  └─────────┘      └───────────┘     └───────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### Policy-Aware Tool System
Agents start with a minimal tool set and discover tools on demand. Three policy levels control access:

- **Permissive**: Auto-unlock on first call (user-spawned agents)
- **Restricted**: Enforced role boundaries (sub-agents)
- **Strict**: Locked to initial manifest (sandboxed)

### Multi-Agent Parallelism
Parent agents can spawn specialized sub-agents that run in parallel:

- Adaptive spawning based on runtime complexity metrics
- Memory slicing: only relevant context is transferred
- 3-tier conflict resolution for concurrent edits

### NATS JetStream Backbone
- 15MB binary vs Kafka's operational weight
- Built-in clustering and persistence
- JetStream KV for result storage
