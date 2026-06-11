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

## Documentation

### Getting Started
- [Installation](installation.md) — Install NexusAgent
- [Quick Start](quickstart.md) — Get up and running fast
- [Configuration](configuration.md) — Configure your setup
- [Getting Started Guide](getting_started.md) — Detailed first-setup walkthrough
- [Local Development](local_development.md) — Contributor workflow guide
- [Environment & Execution](env_execution_guide.md) — Execution environment reference

### Architecture
- [Architecture Overview](architecture/overview.md) — System components and design
- [Tool System](architecture/tools.md) — Tool registry, policies, and role manifests
- [Policy System](architecture/policies.md) — Permissive/restricted/strict access control
- [Multi-Agent](architecture/multi-agent.md) — Sub-agent spawning and parallelism

### Codebase
- [Codebase Map](CODEBASE_MAP.md) — Complete source inventory, data flow, API reference, and issues

### ADRs (Architecture Decision Records)
- [ADRs Index](adrs/index.md)
- [ADR 0001: Telemetry System](adrs/0001-telemetry-system-design.md)
- [ADR 0002: Project Structure](adrs/0002-project-structure-build-modes.md)
- [ADR 0003: Branding & Config](adrs/0003-project-branding-config.md)
- [ADR 0004: Documentation Standards](adrs/0004-documentation-standards.md)

### Plans
- [Assessment & Roadmap](plans/2026-07-12-assessment-and-roadmap.md) — Current strategic roadmap
- [TUI Parity Sprint](plans/2026-06-11-tui-parity-sprint.md) — Recent sprint plan

### Research
- [Tool Parity](research/TOOL-PARITY-FINAL.md)
- [TUI Aesthetics](research/TUI-AESTHETICS-FINAL.md)

### Reports
- [Audit Report](AUDIT_REPORT.md)
- [Competitive Analysis](competitive-analysis-2026-06-06.md)
- [Implementation Plan](implementation-plan-2026-07-09.md)

### Contributing
- [Contributing Guide](CONTRIBUTING.md)

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
